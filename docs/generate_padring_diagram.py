#!/usr/bin/env python3
"""Generate the Raybox Zero 1x0.5 die/pad diagram from its GDS file.

Requires only Python 3 for SVG output. If Inkscape is installed, pass
--png and/or --pdf to render those formats too.
"""
from pathlib import Path
import argparse, math, shutil, struct, subprocess
from xml.sax.saxutils import escape

REC = {
    0x05: "BGNSTR", 0x06: "STRNAME", 0x07: "ENDSTR", 0x08: "BOUNDARY",
    0x09: "PATH", 0x0A: "SREF", 0x0B: "AREF", 0x0C: "TEXT",
    0x0D: "LAYER", 0x0E: "DATATYPE", 0x0F: "WIDTH", 0x10: "XY",
    0x11: "ENDEL", 0x12: "SNAME", 0x13: "COLROW", 0x16: "TEXTTYPE",
    0x19: "STRING", 0x1A: "STRANS", 0x1B: "MAG", 0x1C: "ANGLE",
    0x03: "UNITS",
}

def real8(data):
    """Decode the eight-byte hexadecimal floating point used by GDSII."""
    if data == b"\0" * 8:
        return 0.0
    sign = -1 if data[0] & 0x80 else 1
    exponent = (data[0] & 0x7f) - 64
    mantissa = int.from_bytes(data[1:], "big") / (1 << 56)
    return sign * mantissa * (16 ** exponent)

def parse_gds(path):
    """Read the small subset of GDSII needed by this drawing."""
    data = Path(path).read_bytes()
    offset = 0
    dbu_m = None
    structures = []
    current_struct = None
    elem = None
    while offset < len(data):
        length, record_type, _data_type = struct.unpack(">HBB", data[offset:offset+4])
        if length < 4:
            raise ValueError(f"Invalid GDS record length {length} at byte {offset}")
        payload = data[offset+4:offset+length]
        offset += length
        name = REC.get(record_type, f"R{record_type:02x}")
        if name == "UNITS":
            dbu_m = real8(payload[8:16])
        elif name == "BGNSTR":
            current_struct = {"name": None, "elements": []}
            structures.append(current_struct)
        elif name == "STRNAME":
            current_struct["name"] = payload.rstrip(b"\0").decode("ascii", "replace")
        elif name in ("BOUNDARY", "PATH", "TEXT", "SREF", "AREF"):
            elem = {"kind": name.lower()}
        elif name == "LAYER" and elem is not None:
            elem["layer"] = struct.unpack(">h", payload)[0]
        elif name in ("DATATYPE", "TEXTTYPE") and elem is not None:
            elem["datatype"] = struct.unpack(">h", payload)[0]
        elif name == "XY" and elem is not None:
            values = struct.unpack(">" + "i" * (len(payload)//4), payload)
            elem["xy_dbu"] = list(zip(values[::2], values[1::2]))
        elif name == "WIDTH" and elem is not None:
            elem["width_dbu"] = struct.unpack(">i", payload)[0]
        elif name == "STRING" and elem is not None:
            elem["text"] = payload.rstrip(b"\0").decode("ascii", "replace")
        elif name == "SNAME" and elem is not None:
            elem["sname"] = payload.rstrip(b"\0").decode("ascii", "replace")
        elif name == "STRANS" and elem is not None:
            elem["strans"] = struct.unpack(">H", payload)[0]
        elif name in ("MAG", "ANGLE") and elem is not None:
            elem[name.lower()] = real8(payload)
        elif name == "COLROW" and elem is not None:
            elem["colrow"] = list(struct.unpack(">hh", payload))
        elif name == "ENDEL" and elem is not None:
            current_struct["elements"].append(elem)
            elem = None
    if dbu_m is None:
        raise ValueError("GDS file has no UNITS record")
    scale_um = dbu_m * 1e6
    for structure in structures:
        for item in structure["elements"]:
            if "xy_dbu" in item:
                item["xy_um"] = [[x*scale_um, y*scale_um] for x,y in item["xy_dbu"]]
            if "width_dbu" in item:
                item["width_um"] = item["width_dbu"] * scale_um
    return {"dbu_m": dbu_m, "dbu_um": scale_um, "structures": structures}

cli = argparse.ArgumentParser(description=__doc__)
cli.add_argument("gds", type=Path, help="input hierarchical GDSII file")
cli.add_argument("-o", "--output", type=Path, default=Path("wafer_space_1x0p5_padring"),
                 help="output basename (default: wafer_space_1x0p5_padring)")
cli.add_argument("--png", action="store_true", help="also render a full-resolution PNG using Inkscape")
cli.add_argument("--pdf", action="store_true", help="also render a PDF using Inkscape")
args = cli.parse_args()

# Geometry extracted from chip_top_4ab47b1-pads2c.gds:
# die boundary 0/0 = 3932 x 2531 um; every 81/10 pad marker = 60 x 60 um.
DIE_W_UM, DIE_H_UM, PAD_UM = 3932.0, 2531.0, 60.0
SCALE = 0.76
DIE_X, DIE_Y = 260.0, 420.0
DIE_W, DIE_H = DIE_W_UM * SCALE, DIE_H_UM * SCALE
W, H = 4850, 3060
# Keep the die diagram centred in its original left-hand panel; the expanded
# canvas area at right is reserved for the complete pad-coordinate table.
MID_X = DIE_X + DIE_W/2

# key, exact/qualified Wafer.Space name, x centre (um), y centre (um)
pads = []

def add(key, ws_name, x, y): pads.append({"key":key, "ws":ws_name, "x":x, "y":y})

# South, physical left-to-right.
south = [
    ("clk", "clk_PAD"), ("rst_n", "rst_n_PAD"),
    ("bidir_0", "bidir_PAD[0]"), ("bidir_1", "bidir_PAD[1]"),
    ("DVSS[0]", "DVSS[0] · VSS"), ("DVDD[0]", "DVDD[0] · VDD"),
    *[(f"bidir_{i}", f"bidir_PAD[{i}]") for i in range(2, 14)],
    ("DVSS[1]", "DVSS[1] · VSS"), ("DVDD[1]", "DVDD[1] · VDD"),
    *[(f"bidir_{i}", f"bidir_PAD[{i}]") for i in range(14, 18)],
]
south_x = [482.5, 611.5, 740.5, 869.5, 998.5, 1127.5] + [1256.5+129*i for i in range(12)] + [2804.5, 2933.5] + [3062.5+129*i for i in range(4)]
for (key,name),x in zip(south,south_x): add(key,name,x,58.0)

# East, physical bottom-to-top.
east = [("DVSS[2]", "DVSS[2] · VSS"), ("DVDD[2]", "DVDD[2] · VDD"), *[(f"bidir_{i}",f"bidir_PAD[{i}]") for i in range(18,26)], ("DVSS[3]", "DVSS[3] · VSS"), ("DVDD[3]", "DVDD[3] · VDD")]
east_y = [490.0,631.0] + [772.0+141*i for i in range(8)] + [1900.0,2041.0]
for (key,name),y in zip(east,east_y): add(key,name,3874.0,y)

# North, physical right-to-left in pin order 37..60.
north_pin_order = [
    *[(f"bidir_{i}",f"bidir_PAD[{i}]") for i in range(26,30)],
    ("DVDD[4]", "DVDD[4] · VDD"), ("DVSS[4]", "DVSS[4] · VSS"),
    *[(f"bidir_{i}",f"bidir_PAD[{i}]") for i in range(30,42)],
    ("DVDD[5]", "DVDD[5] · VDD"), ("DVSS[5]", "DVSS[5] · VSS"),
    *[(f"bidir_{i}",f"bidir_PAD[{i}]") for i in range(42,46)],
]
north_x_pin_order = [3449.5,3320.5,3191.5,3062.5,2933.5,2804.5] + [2675.5-129*i for i in range(12)] + [1127.5,998.5,869.5,740.5,611.5,482.5]
for (key,name),x in zip(north_pin_order,north_x_pin_order): add(key,name,x,2473.0)

# West, physical top-to-bottom. This is the reverse of PAD_WEST YAML order.
west = [
    ("VDD[0]", "VDD[0] · VDD"), ("VSS[0]", "VSS[0] · VSS"),
    *[(f"an_{i}",f"analog_PAD[{i}]") for i in range(4)],
    *[(f"in_{i}",f"input_PAD[{i}]") for i in range(4)],
    ("DVDD[6]", "DVDD[6] · VDD"), ("DVSS[6]", "DVSS[6] · VSS"),
]
west_y = [2041.0,1900.0] + [1759.0-141*i for i in range(4)] + [1195.0-141*i for i in range(4)] + [631.0,490.0]
for (key,name),y in zip(west,west_y): add(key,name,58.0,y)

assert len(pads) == 72

project = {
    "clk": ("CLK", "special"), "rst_n": ("RESET_N", "special"),
    "bidir_0": ("CTRL_SPI_SCK", "input"), "bidir_1": ("CTRL_SPI_MOSI", "input"),
    "bidir_2": ("CTRL_SPI_CS_N", "input"), "bidir_3": ("DEBUG", "input"),
    "bidir_4": ("DEC_X", "input"), "bidir_5": ("DEC_Y", "input"),
    "bidir_6": ("REG", "input"), "bidir_7": ("TEX_PMOD_TYPE", "input"),
    "bidir_8": ("TM1QSPI_CS_N", "output"), "bidir_9": ("TM1QSPI_IO0", "bidir"),
    "bidir_10": ("TM1QSPI_IO1", "input"), "bidir_11": ("TM1QSPI_SCK", "output"),
    "bidir_12": ("n/c", "unused_digital"), "bidir_13": ("GEN_TEXb", "input"),
    "bidir_14": ("TM1QSPI_IO2", "input"), "bidir_15": ("TM1QSPI_IO3", "input"),
    "bidir_16": ("RED[1]", "output"), "bidir_17": ("GREEN[1]", "output"),
    "bidir_18": ("BLUE[1]", "output"), "bidir_19": ("VSYNC_N", "output"),
    "bidir_20": ("RED[0]", "output"), "bidir_21": ("GREEN[0]", "output"),
    "bidir_22": ("BLUE[0]", "output"), "bidir_23": ("HSYNC_N", "output"),
    "bidir_24": ("HBLANK", "output"), "bidir_25": ("VBLANK", "output"),
    "bidir_26": ("HMAX", "output"), "bidir_27": ("VMAX", "output"),
}
for i in range(28,38): project[f"bidir_{i}"] = (f"VPOS[{i-28}]", "output")
for i in range(38,46): project[f"bidir_{i}"] = ("n/c", "unused_digital")
for i in range(4):
    project[f"in_{i}"] = ("n/c", "unused_digital")
    project[f"an_{i}"] = ("n/c", "unused_analog")
for i in range(7):
    project[f"DVSS[{i}]"] = ("GND", "gnd"); project[f"DVDD[{i}]"] = ("VDD", "power")
project["VSS[0]"] = ("GND", "gnd"); project["VDD[0]"] = ("VDD", "power")

fill_for = {"power":"#ef4444", "gnd":"#1e3a8a", "input":"#22c55e", "output":"#f59e0b", "bidir":"#d946ef", "special":"#86efac", "unused_digital":"url(#hatch-green)", "unused_analog":"url(#hatch-pink)"}
stroke_for = {"unused_digital":"#22c55e", "unused_analog":"#ec4899"}

def sx(x): return DIE_X + x*SCALE
def sy(y): return DIE_Y + (DIE_H_UM-y)*SCALE
def txt(x,y,value,size=22,anchor="middle",weight=500,fill="#162033",transform=""):
    tr=f' transform="{transform}"' if transform else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{fill}"{tr}>{escape(value)}</text>'
def pad_number(cx,cy,pin,pin1,unused):
    if pin1:
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="19" fill="#111827" stroke="#f8fafc" stroke-width="3"/>'+txt(cx,cy+7,"1",21,"middle",800,"#fff")
    return txt(cx,cy+7,str(pin),21,"middle",800,"#111827" if unused else "#fff")
def label_pair(x,y,ws,pname,anchor="middle",transform=""):
    # Project name is dominant and vertically centred on the pad centre.
    # The Wafer.Space/GDS name follows beneath it as secondary information.
    pcolour = "#4b5563" if pname == "n/c" else "#111827"
    tr = f' transform="{transform}"' if transform else ""
    # Pins 61/62 use true VDD/VSS rather than the digital DVDD/DVSS rails.
    # Underline only the leading rail name in their secondary labels.
    if ws in ("VDD[0] · VDD", "VSS[0] · VSS"):
        prefix=ws[:3]; rest=ws[3:]
        ws_markup=(f'<text x="{x:.1f}" y="{y+27:.1f}" text-anchor="{anchor}" font-size="18" font-weight="500" fill="#64748b"{tr}>'
                   f'<tspan style="text-decoration-line:underline;text-decoration-style:double">{prefix}</tspan><tspan>{escape(rest)}</tspan></text>')
    else:
        ws_markup=txt(x,y+27,ws,18,anchor,500,"#64748b",transform)
    return txt(x,y,pname,29,anchor,780,pcolour,transform)+ws_markup

svg=[f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect width="100%" height="100%" fill="#f8fafc"/>
<style>text{{font-family:Inter,Arial,sans-serif}} .pad{{stroke-width:2.5}}</style>
<defs>
<pattern id="hatch-green" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="10" height="10" fill="#dcfce7"/><rect width="3.5" height="10" fill="#22c55e"/></pattern>
<pattern id="hatch-pink" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="10" height="10" fill="#fce7f3"/><rect width="3.5" height="10" fill="#ec4899"/></pattern>
</defs>
<text x="{MID_X}" y="67" text-anchor="middle" font-size="50" font-weight="750" fill="#101827">Wafer.Space GF180 Run 2 — Raybox Zero 1×0.5 Padring</text>
<text x="{MID_X}" y="118" text-anchor="middle" font-size="28" fill="#475569">GDS-derived to-scale pad geometry · top view · TEX_PMOD_TYPE=1 mode</text>
<rect x="{DIE_X}" y="{DIE_Y}" width="{DIE_W}" height="{DIE_H}" fill="#e2e8f0" stroke="#0f172a" stroke-width="5"/>
''']

# Extract top-level Metal4 core bounds and placed Metal5 corner artwork from
# the supplied hierarchical GDS dump. Only chip_top's own 46/0 geometry is
# used for the core; Metal4 inside gf180mcu_ws_ip__... cells is excluded.
gds = parse_gds(args.gds)
structs = {s["name"]:s for s in gds["structures"]}
top = structs["chip_top"]
core_geoms = [e for e in top["elements"] if e["kind"] in ("boundary","path") and e.get("layer")==46 and e.get("datatype")==0]
core_x=[]; core_y=[]
for e in core_geoms:
    if e["kind"]=="boundary":
        core_x += [x for x,y in e["xy_um"]]; core_y += [y for x,y in e["xy_um"]]
    else:
        # GDS path type 0 has butt ends: width expands perpendicular to each
        # segment, but does not extend beyond its endpoints.
        half=abs(e.get("width_um",0))/2; pts=e["xy_um"]
        for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
            dx,dy=x1-x0,y1-y0; length=math.hypot(dx,dy)
            if not length: continue
            nx,ny=-dy/length*half,dx/length*half
            for x,y in ((x0+nx,y0+ny),(x0-nx,y0-ny),(x1+nx,y1+ny),(x1-nx,y1-ny)):
                core_x.append(x); core_y.append(y)
core = (min(core_x),min(core_y),max(core_x),max(core_y))
cx0,cy0,cx1,cy1 = core
core_svg_x,core_svg_y = sx(cx0),sy(cy1)
core_svg_w,core_svg_h = (cx1-cx0)*SCALE,(cy1-cy0)*SCALE
svg += [
    f'<rect x="{core_svg_x:.1f}" y="{core_svg_y:.1f}" width="{core_svg_w:.1f}" height="{core_svg_h:.1f}" fill="#eff6ff" fill-opacity="0.55" stroke="#2563eb" stroke-width="3" stroke-dasharray="14 9"/>',
    txt(core_svg_x+14,core_svg_y-12,"CORE · top-level Metal4 bounds",24,"start",700,"#1d4ed8"),
]

def transform_xy(x,y,ref):
    mag=ref.get("mag",1.0); a=math.radians(ref.get("angle",0.0)); flags=ref.get("strans",0)
    if flags & 0x8000: y=-y
    x,y=x*mag,y*mag
    xr=x*math.cos(a)-y*math.sin(a); yr=x*math.sin(a)+y*math.cos(a)
    ox,oy=ref["xy_um"][0]
    return xr+ox,yr+oy

corner_polys=[]
for ref in [e for e in top["elements"] if e["kind"]=="sref" and e.get("sname","").startswith("gf180mcu_ws_ip__")]:
    cell=structs[ref["sname"]]
    for e in cell["elements"]:
        if e["kind"]=="boundary" and e.get("layer")==81 and e.get("datatype")==0:
            corner_polys.append((ref["sname"],[transform_xy(x,y,ref) for x,y in e["xy_um"]]))
for cell_name,poly in corner_polys:
    pts=" ".join(f"{sx(x):.2f},{sy(y):.2f}" for x,y in poly)
    svg.append(f'<polygon points="{pts}" fill="#a16207" stroke="#713f12" stroke-width="0.8"/>')

# Pin numbers are assigned counter-clockwise from the southwest pad.
pin_by_key={}
for i,(key,_) in enumerate(south): pin_by_key[key]=i+1
for i,(key,_) in enumerate(east): pin_by_key[key]=25+i
for i,(key,_) in enumerate(north_pin_order): pin_by_key[key]=37+i
for i,(key,_) in enumerate(west): pin_by_key[key]=61+i

ps=PAD_UM*SCALE
for p in pads:
    key=p["key"]; pin=pin_by_key[key]; pname,kind=project[key]
    cx,cy=sx(p["x"]),sy(p["y"])
    svg.append(f'<rect class="pad" x="{cx-ps/2:.1f}" y="{cy-ps/2:.1f}" width="{ps:.1f}" height="{ps:.1f}" rx="3" fill="{fill_for[kind]}" stroke="{stroke_for.get(kind, "#0f172a")}"/>')
    svg.append(pad_number(cx,cy,pin,pin==1,kind.startswith("unused_")))
    if p["y"] < 100: # south; vertical, reading bottom-to-top
        lx,ly=cx,DIE_Y+DIE_H+24
        svg.append(label_pair(lx,ly,p["ws"],pname,"end",f"rotate(-90 {lx:.1f} {ly:.1f})"))
    elif p["y"] > 2400: # north
        lx,ly=cx,DIE_Y-24
        svg.append(label_pair(lx,ly,p["ws"],pname,"start",f"rotate(-90 {lx:.1f} {ly:.1f})"))
    elif p["x"] < 100: # west
        svg.append(label_pair(DIE_X-24,cy+10,p["ws"],pname,"end"))
    else: # east
        svg.append(label_pair(DIE_X+DIE_W+24,cy+10,p["ws"],pname,"start"))

svg += [txt(MID_X,1150,"RAYBOX ZERO",82,"middle",780,"#334155"),txt(MID_X,1220,"Die dimensions: 3932 µm × 2531 µm",32,"middle",600,"#64748b"),txt(MID_X,1275,"Pad opening (all 72 pads): 60 µm × 60 µm",28,"middle",650,"#475569"),txt(MID_X,1325,"Pad squares and centres taken directly from GDS layer 81/10",27,"middle",650,"#475569"),txt(MID_X,1375,"Pin sequence: 1 → 24 → 36 → 60 → 72",26,"middle",500,"#64748b")]

# True-scale 500 um marker. Its pixel length follows the same SCALE as the die.
bar_x,bar_y,bar_len=DIE_X+420,DIE_Y+DIE_H-260,500*SCALE
svg += [
    f'<line x1="{bar_x:.1f}" y1="{bar_y:.1f}" x2="{bar_x+bar_len:.1f}" y2="{bar_y:.1f}" stroke="#0f172a" stroke-width="5"/>',
    f'<line x1="{bar_x:.1f}" y1="{bar_y-13:.1f}" x2="{bar_x:.1f}" y2="{bar_y+13:.1f}" stroke="#0f172a" stroke-width="5"/>',
    f'<line x1="{bar_x+bar_len:.1f}" y1="{bar_y-13:.1f}" x2="{bar_x+bar_len:.1f}" y2="{bar_y+13:.1f}" stroke="#0f172a" stroke-width="5"/>',
    txt(bar_x+bar_len/2,bar_y-22,"500 µm",25,"middle",700,"#0f172a"),
]

legend=[("#ef4444","Power"),("#1e3a8a","GND"),("#22c55e","Input"),("#f59e0b","Output"),("#d946ef","Bidirectional"),("#86efac","CLK / RESET"),("url(#hatch-green)","Unused digital input"),("url(#hatch-pink)","Unused analog input")]
lx,ly=DIE_X,2795
for i,(fill,label) in enumerate(legend):
    row,col=divmod(i,4)
    x=lx+col*(DIE_W/4)
    y=ly+row*92
    border = "#22c55e" if fill == "url(#hatch-green)" else "#ec4899" if fill == "url(#hatch-pink)" else "#172033"
    svg.append(f'<rect x="{x}" y="{y-40}" width="58" height="43" rx="4" fill="{fill}" stroke="{border}" stroke-width="3"/>')
    svg.append(txt(x+76,y-4,label,31,"start",650,"#334155"))
svg.append(txt(MID_X,3015,"Wafer.Space labels were checked against the 72 text markers in the supplied GDS; supply indices come from the padring definition.",24,"middle",500,"#64748b"))

# Full pin table, sorted electrically from pin 1 through pin 72. Coordinates
# are pad-opening centres in micrometres relative to the die's southwest origin.
table_x,table_y=3660,300
# Compact widths: Raybox Zero is 60% and Wafer.Space is 40% of the
# corresponding widths in the previous table. Recovered room goes into
# taller rows and larger type rather than a wider table.
pin_w,x_w,y_w,raybox_w,wafer_w=54,80,80,184,156
table_w=pin_w+x_w+y_w+raybox_w+wafer_w
table_gap,row_h=24,70.6
svg.append(txt(table_x,185,"PAD COORDINATES",34,"start",780,"#101827"))
svg.append(txt(table_x,222,"Centre coordinates in µm from southwest die origin",22,"start",500,"#64748b"))
pad_rows=sorted(((pin_by_key[p["key"]],p) for p in pads),key=lambda item:item[0])
for half in range(2):
    bx=table_x+half*(table_w+table_gap)
    pin_x=bx
    x_right=bx+pin_w+x_w-7
    y_right=bx+pin_w+x_w+y_w-7
    raybox_x=bx+pin_w+x_w+y_w
    wafer_x=raybox_x+raybox_w
    svg.append(txt(bx,table_y-17,f'PINS {1+half*36}–{36+half*36}',26,"start",750,"#334155"))
    svg.append(f'<rect x="{bx}" y="{table_y}" width="{table_w}" height="48" rx="4" fill="#334155"/>')
    svg.append(txt(pin_x+7,table_y+32,"Pin",20,"start",750,"#ffffff"))
    svg.append(txt(x_right,table_y+32,"X",20,"end",750,"#ffffff"))
    svg.append(txt(y_right,table_y+32,"Y",20,"end",750,"#ffffff"))
    svg.append(txt(raybox_x+7,table_y+32,"Raybox Zero",20,"start",750,"#ffffff"))
    svg.append(txt(wafer_x+7,table_y+32,"Wafer.Space",20,"start",750,"#ffffff"))
    for local_idx,(pin,p) in enumerate(pad_rows[half*36:(half+1)*36]):
        y=table_y+48+local_idx*row_h
        pname,kind=project[p["key"]]
        bg="#ffffff" if local_idx%2==0 else "#eef2f7"
        svg.append(f'<rect x="{bx}" y="{y}" width="{table_w}" height="{row_h}" fill="{bg}" stroke="#cbd5e1" stroke-width="0.8"/>')
        raybox_colour = "#dc2626" if kind=="power" else "#0000FF" if kind=="gnd" else "#4b5563" if pname=="n/c" else "#111827"
        baseline=y+45
        raybox_size=18.5 if len(pname)>=13 else 20.5
        wafer_size=18.5 if len(p["ws"])>=14 else 20.5
        svg.append(txt(pin_x+7,baseline,str(pin),20.5,"start",750,"#111827"))
        svg.append(txt(x_right,baseline,f'{p["x"]:.1f}',20.5,"end",500,"#334155"))
        svg.append(txt(y_right,baseline,f'{p["y"]:.1f}',20.5,"end",500,"#334155"))
        svg.append(txt(raybox_x+7,baseline,pname,raybox_size,"start",750,raybox_colour))
        svg.append(txt(wafer_x+7,baseline,p["ws"],wafer_size,"start",500,"#64748b"))
svg.append('</svg>')

svg_path = args.output.with_suffix(".svg")
svg_path.parent.mkdir(parents=True, exist_ok=True)
svg_path.write_text("\n".join(svg), encoding="utf-8")
print(f"wrote {svg_path}")

if args.png or args.pdf:
    inkscape = shutil.which("inkscape")
    if not inkscape:
        raise SystemExit("Inkscape is required for --png or --pdf output")
    if args.png:
        png_path = args.output.with_suffix(".png")
        subprocess.run([
            inkscape, str(svg_path), "--export-type=png",
            f"--export-filename={png_path}", f"--export-width={W}",
        ], check=True)
        print(f"wrote {png_path}")
    if args.pdf:
        pdf_path = args.output.with_suffix(".pdf")
        subprocess.run([
            inkscape, str(svg_path), "--export-type=pdf",
            f"--export-filename={pdf_path}",
        ], check=True)
        print(f"wrote {pdf_path}")
