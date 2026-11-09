#!/usr/bin/env python3
"""Generate a Caravel QFN64 / Raybox Zero pinout diagram.

The physical pin names and numbers are extracted from U1's embedded KiCad
symbol.  Raybox Zero signal assignments are taken from the GF180
user_project_wrapper/top_design_mux implementation.

Example:
  python3 generate_caravel_raybox_diagram.py \
    caravel-M.2-card-QFN.kicad_sch -o caravel_raybox_zero_qfn64 --png --pdf
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape


def balanced(text: str, start: int) -> str:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
    raise ValueError("unterminated S-expression")


def read_caravel_pins(schematic: Path) -> dict[int, dict[str, str]]:
    text = schematic.read_text(encoding="utf-8")
    marker = '(symbol "Caravel_board:Caravel"'
    start = text.find(marker)
    if start < 0:
        raise ValueError("Caravel_board:Caravel symbol not found")
    symbol = balanced(text, start)
    pins: dict[int, dict[str, str]] = {}
    position = 0
    pin_re = re.compile(
        r"\(pin\s+(input|output|bidirectional|power_in|power_out|passive|"
        r"no_connect|tri_state|unspecified)\s+\w+"
    )
    while True:
        match = pin_re.search(symbol, position)
        if not match:
            break
        pin_block = balanced(symbol, match.start())
        position = match.start() + len(pin_block)
        name = re.search(r'\(name\s+"([^"]*)"', pin_block)
        number = re.search(r'\(number\s+"([^"]*)"', pin_block)
        if name and number and number.group(1).isdigit():
            pins[int(number.group(1))] = {
                "name": name.group(1), "electrical": match.group(1)
            }
    if set(pins) != set(range(1, 66)):
        raise ValueError(f"expected U1 pins 1..65, found {sorted(pins)}")
    return pins


# user_project_wrapper.v mapping for the two Raybox Zero mux choices (0 and 1).
# Tuple: display name, role.
RAYBOX_IO = {
    5: ("opt_user_reset", "input"),
    8: ("HSYNC_N", "output"),
    9: ("VSYNC_N", "output"),
    **{10 + i: (f"RGB[{i}]", "output") for i in range(6)},
    16: ("TEX_CS_N", "output"),
    17: ("TEX_SCLK", "output"),
    18: ("TEX_IO0", "bidir"),
    19: ("TEX_IO1", "input"),
    20: ("TEX_IO2", "input"),
    21: ("TEX_IO3", "input"),
    22: ("VEC_CS_N", "input"),
    23: ("VEC_SCLK", "input"),
    24: ("VEC_MOSI", "input"),
    25: ("REG_CS_N", "input"),
    26: ("REG_SCLK", "input"),
    27: ("REG_MOSI", "input"),
    28: ("DEBUG_VEC", "input"),
    29: ("DEBUG_MAP", "input"),
    30: ("DEBUG_TRACE", "input"),
    31: ("REG_OUTS_ENB", "input"),
    32: ("MODE0_INC_PX", "input"),
    33: ("MODE1_INC_PY", "input"),
    34: ("MODE2_GEN_TEX", "input"),
    35: ("GPOUT[0]", "output"),
    36: ("GPOUT[1]", "output"),
    37: ("GPOUT[2]", "output"),
}

COLORS = {
    "power": "#ef4444",
    "gnd": "#1d4ed8",
    "input": "#22c55e",
    "output": "#f59e0b",
    "bidir": "#d946ef",
    "special": "#86efac",
    "service": "#94a3b8",
    "unused": "url(#hatch-green)",
    "physical_nc": "#ffffff",
}

# Alternate Caravel-management functions multiplexed onto mprj_io[0:6].
# The role controls the coloured half of the diagonally split pad.
CARAVEL_ALT_IO = {
    0: ("JTAG", "input"),
    1: ("SDO", "output"),
    2: ("SDI", "input"),
    3: ("CSB", "input"),
    4: ("SCK", "input"),
    5: ("SER_RX", "input"),
    6: ("SER_TX", "output"),
}


def io_index(name: str) -> int | None:
    match = re.match(r"mprj_io\[(\d+)\]", name)
    return int(match.group(1)) if match else None


def classify(pin: dict[str, str]) -> tuple[str, str, str]:
    """Return project label, visual role, and short direction."""
    name = pin["name"]
    lower = name.lower()
    index = io_index(name)
    if index is not None:
        if index in RAYBOX_IO:
            label, role = RAYBOX_IO[index]
            return label.lower(), role, {"input": "IN", "output": "OUT", "bidir": "I/O"}[role]
        if index in CARAVEL_ALT_IO:
            _label, role = CARAVEL_ALT_IO[index]
            return "", role, {"input": "IN", "output": "OUT", "bidir": "I/O"}[role]
        # Plain mprj_io pins with no Raybox or alternate Caravel function are
        # genuine unused digital inputs in this design.
        return "n/c", "input", "—"
    if name == "clock":
        return "system_clk", "special", "IN"
    if name == "resetb":
        return "RESETb", "special", "IN"
    if name == "ThermalPad" or lower.startswith(("vss", "vssa")):
        return "GND", "gnd", "GND"
    if lower.startswith(("vdd", "vdda", "vccd")):
        return "VDD", "power", "PWR"
    if name == "N/C":
        return "", "physical_nc", "—"
    role = {
        "input": "input", "output": "output", "bidirectional": "bidir"
    }.get(pin["electrical"], "service")
    direction = {"input": "IN", "output": "OUT", "bidir": "I/O"}.get(role, "—")
    return "", role, direction


def pad_style(pin: dict[str, str]) -> str:
    """Return normal, unused, exclusive, dual, or physical_nc."""
    name = pin["name"]
    index = io_index(name)
    if index is not None:
        if index in CARAVEL_ALT_IO:
            return "dual"
        if index not in RAYBOX_IO:
            return "unused"
        return "normal"
    if name == "N/C":
        return "physical_nc"
    if name == "resetb":
        return "reset_split"
    if name in {"flash_csb", "flash_clk", "flash_io0", "flash_io1", "gpio"}:
        return "exclusive"
    return "normal"


def text(x, y, value, size=16, anchor="middle", weight=500, fill="#172033",
         transform="", cls=""):
    tr = f' transform="{transform}"' if transform else ""
    class_attr = f' class="{cls}"' if cls else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}"{tr}{class_attr}>'
            f'{escape(value)}</text>')


def make_svg(pins: dict[int, dict[str, str]]) -> str:
    width, height = 2600, 1480
    body_x, body_y, body = 400, 350, 600
    step, start_x = 36, 430
    # Centre the complete 16-pin side row in the straight package edge.  This
    # deliberately ignores the pin-1 chamfer, which is only a corner marker.
    start_y = body_y + (body - 15 * step) / 2
    pad_len, pad_thick = 58, 28

    out = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#f8fafc"/>
<style>
text{{font-family:Inter,Arial,sans-serif}} .pin{{stroke-width:2.3}} .hair{{stroke:#cbd5e1;stroke-width:1}}
</style>
<defs>
 <pattern id="hatch-green" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="9" height="9" fill="#dcfce7"/><rect width="3" height="9" fill="#22c55e"/></pattern>
</defs>
<text x="730" y="58" text-anchor="middle" font-size="48" font-weight="800" fill="#0f172a">RAYBOX ZERO — CARAVEL QFN64 PINOUT</text>
<text x="730" y="101" text-anchor="middle" font-size="25" fill="#475569">Top view · GF180 multi-project implementation · mux design ID 0 or 1</text>
<rect x="{body_x}" y="{body_y}" width="{body}" height="{body}" rx="13" fill="#dbe3ec" stroke="#0f172a" stroke-width="5"/>
<path d="M {body_x} {body_y+42} L {body_x+42} {body_y} L {body_x} {body_y}" fill="#f8fafc" stroke="#0f172a" stroke-width="3"/>
<text x="700" y="610" text-anchor="middle" font-size="45" font-weight="800" fill="#0f172a">CARAVEL</text>
<text x="700" y="650" text-anchor="middle" font-size="28" font-weight="700" fill="#334155">RAYBOX ZERO</text>
<text x="700" y="690" text-anchor="middle" font-size="20" fill="#475569">QFN-64-1EP · 9 × 9 mm · 0.5 mm pitch</text>
<rect x="575" y="735" width="250" height="150" rx="8" fill="#1d4ed8" stroke="#173a8a" stroke-width="3"/>
<text x="700" y="795" text-anchor="middle" font-size="27" font-weight="800" fill="white">65</text>
<text x="700" y="829" text-anchor="middle" font-size="21" font-weight="750" fill="white">THERMAL PAD</text>
<text x="700" y="859" text-anchor="middle" font-size="19" fill="white">GND · 7.65 × 7.65 mm</text>
''']

    def pin_rect(number, x, y, w, h, role, style):
        colour = COLORS[role]
        stroke = "#22c55e" if style == "unused" else "#334155"
        if style == "unused":
            out.append(f'<rect class="pin" x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="3" fill="url(#hatch-green)" stroke="{stroke}"/>')
        elif style in ("exclusive", "physical_nc"):
            out.append(f'<rect class="pin" x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="3" fill="white" stroke="{stroke}"/>')
        elif style == "dual":
            # White upper-left triangle denotes mprj_io; colour denotes the
            # alternate Caravel-management signal and its direction.
            user_fill = "#ffff00" if number == 36 else "white"
            out.append(f'<rect class="pin" x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="3" fill="{user_fill}" stroke="#334155"/>')
            out.append(f'<path d="M {x+w:.1f} {y:.1f} L {x+w:.1f} {y+h:.1f} L {x:.1f} {y+h:.1f} Z" fill="{colour}"/>')
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="3" fill="none" stroke="#334155" stroke-width="2.3"/>')
            if number == 36:
                out.append(text(x + 8, y + 13, "*", 17, "middle", 900, "#0f172a"))
        elif style == "reset_split":
            # Yellow denotes the package-level Caravel reset behaviour; light
            # green denotes the optional reset path into the muxed user designs.
            out.append(f'<rect class="pin" x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="3" fill="#ffff00" stroke="#334155"/>')
            out.append(f'<path d="M {x+w:.1f} {y:.1f} L {x+w:.1f} {y+h:.1f} L {x:.1f} {y+h:.1f} Z" fill="#86efac"/>')
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="3" fill="none" stroke="#334155" stroke-width="2.3"/>')
            out.append(text(x + 8, y + 13, "†", 15, "middle", 900, "#0f172a"))
        else:
            out.append(f'<rect class="pin" x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="3" fill="{colour}" stroke="{stroke}"/>')
        cx, cy = x + w / 2, y + h / 2
        dark_digits = style in ("unused", "physical_nc") or role == "special"
        if number == 1:
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="11.5" fill="#0f172a" stroke="white" stroke-width="2"/>')
            out.append(text(cx, cy + 5, "1", 14, weight=800, fill="white"))
        elif style == "exclusive":
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="10.5" fill="{colour}"/>')
            out.append(text(cx, cy + 5, str(number), 14, weight=800,
                            fill="#0f172a" if role == "special" else "white"))
        elif style in ("dual", "reset_split"):
            out.append(f'<text x="{cx:.1f}" y="{cy+5:.1f}" text-anchor="middle" font-size="14" font-weight="800" fill="#0f172a" stroke="white" stroke-width="3" paint-order="stroke">{number}</text>')
        else:
            out.append(text(cx, cy + 5, str(number), 14, weight=800,
                            fill="#0f172a" if dark_digits else "white"))

    def pair_horizontal(number, cx, cy, side):
        project, _role, _direction = classify(pins[number])
        wafer = pins[number]["name"]
        if side == "left":
            x, anchor = body_x - pad_len - 11, "end"
        else:
            x, anchor = body_x + body + pad_len + 11, "start"
        if project:
            fill = "#4b5563" if project == "n/c" else "#111827"
            out.append(text(x, cy - 3, project, 18, anchor, 800, fill))
            out.append(text(x, cy + 14, wafer, 13, anchor, 500, "#64748b"))
        else:
            out.append(text(x, cy + 5, wafer, 15, anchor, 600, "#475569"))

    def pair_vertical(number, cx, y, top):
        project, _role, _direction = classify(pins[number])
        wafer = pins[number]["name"]
        anchor = "start" if top else "end"
        transform = f"rotate(-90 {cx:.1f} {y:.1f})"
        if project:
            fill = "#4b5563" if project == "n/c" else "#111827"
            out.append(text(cx, y - 3, project, 17, anchor, 800, fill, transform))
            out.append(text(cx, y + 13, wafer, 12.5, anchor, 500, "#64748b", transform))
        else:
            out.append(text(cx, y + 4, wafer, 14, anchor, 600, "#475569", transform))

    # Left: pins 1..16, top to bottom.
    for index, number in enumerate(range(1, 17)):
        cy = start_y + index * step
        project, role, _ = classify(pins[number])
        pin_rect(number, body_x - pad_len, cy - pad_thick / 2, pad_len, pad_thick, role, pad_style(pins[number]))
        pair_horizontal(number, body_x - pad_len / 2, cy, "left")

    # Bottom: pins 17..32, left to right.
    for index, number in enumerate(range(17, 33)):
        cx = start_x + index * step
        project, role, _ = classify(pins[number])
        pin_rect(number, cx - pad_thick / 2, body_y + body, pad_thick, pad_len, role, pad_style(pins[number]))
        pair_vertical(number, cx, body_y + body + pad_len + 12, False)

    # Right: pins 33..48, bottom to top.
    for index, number in enumerate(range(33, 49)):
        cy = start_y + (15 - index) * step
        project, role, _ = classify(pins[number])
        pin_rect(number, body_x + body, cy - pad_thick / 2, pad_len, pad_thick, role, pad_style(pins[number]))
        pair_horizontal(number, body_x + body + pad_len / 2, cy, "right")

    # Top: pins 49..64, right to left.
    for index, number in enumerate(range(49, 65)):
        cx = start_x + (15 - index) * step
        project, role, _ = classify(pins[number])
        pin_rect(number, cx - pad_thick / 2, body_y - pad_len, pad_thick, pad_len, role, pad_style(pins[number]))
        pair_vertical(number, cx, body_y - pad_len - 12, True)

    # Two-row legend, kept to the diagram width.
    legend = [
        ("power", "Power"), ("gnd", "GND"), ("input", "Raybox input"),
        ("output", "Raybox output"), ("bidir", "Raybox bidir"),
        ("special", "Shared system clock"), ("unused", "Unused mprj_io"),
        ("exclusive", "Caravel-only function"), ("dual", "mprj_io / Caravel function"),
    ]
    lx, ly = 105, 1233
    out.append('<rect x="70" y="1204" width="1320" height="150" rx="12" fill="white" stroke="#cbd5e1" stroke-width="2"/>')
    for i, (role, label) in enumerate(legend):
        row, col = divmod(i, 3)
        x, y = lx + col * 430, ly + row * 46
        if role == "exclusive":
            out.append(f'<rect x="{x}" y="{y-20}" width="48" height="27" rx="3" fill="white" stroke="#334155" stroke-width="2"/>')
            out.append(f'<circle cx="{x+24}" cy="{y-6.5}" r="8" fill="#f59e0b"/>')
        elif role == "dual":
            out.append(f'<rect x="{x}" y="{y-20}" width="48" height="27" rx="3" fill="white" stroke="#334155" stroke-width="2"/>')
            out.append(f'<path d="M {x+48} {y-20} L {x+48} {y+7} L {x} {y+7} Z" fill="#22c55e"/>')
            out.append(f'<rect x="{x}" y="{y-20}" width="48" height="27" rx="3" fill="none" stroke="#334155" stroke-width="2"/>')
        elif role == "unused":
            out.append(f'<rect x="{x}" y="{y-20}" width="48" height="27" rx="3" fill="url(#hatch-green)" stroke="#22c55e" stroke-width="2"/>')
        else:
            out.append(f'<rect x="{x}" y="{y-20}" width="48" height="27" rx="3" fill="{COLORS[role]}" stroke="#334155" stroke-width="2"/>')
        out.append(text(x + 60, y + 1, label, 17, "start", 650, "#334155"))

    # Table: 1..32 in the left half, 33..65 in the right half.
    def table(x, numbers):
        widths = [42, 176, 212, 58]
        total = sum(widths)
        y0, header_h, row_h = 128, 36, 34
        out.append(f'<rect x="{x}" y="{y0}" width="{total}" height="{header_h + row_h * len(numbers)}" fill="white" stroke="#94a3b8" stroke-width="2"/>')
        out.append(f'<rect x="{x}" y="{y0}" width="{total}" height="{header_h}" fill="#1e293b"/>')
        headers = ["Pin", "Caravel / U1", "Raybox Zero", "Dir"]
        cursor = x
        for width_col, header in zip(widths, headers):
            out.append(text(cursor + (width_col / 2), y0 + 24, header, 15, "middle", 750, "white"))
            cursor += width_col
        for row, number in enumerate(numbers):
            y = y0 + header_h + row * row_h
            if row % 2:
                out.append(f'<rect x="{x}" y="{y}" width="{total}" height="{row_h}" fill="#f1f5f9"/>')
            project, role, direction = classify(pins[number])
            raybox = project or "—"
            ray_fill = COLORS[role] if role in ("power", "gnd") else ("#4b5563" if raybox == "n/c" else "#111827")
            out.append(text(x + widths[0] - 8, y + 23, str(number), 15, "end", 750, "#334155"))
            out.append(text(x + widths[0] + 7, y + 23, pins[number]["name"], 14.5, "start", 500, "#475569"))
            out.append(text(x + widths[0] + widths[1] + 7, y + 23, raybox, 14.5, "start", 750, ray_fill))
            out.append(text(x + total - 10, y + 23, direction, 14, "end", 700, "#475569"))
            cursor = x
            for width_col in widths[:-1]:
                cursor += width_col
                out.append(f'<line class="hair" x1="{cursor}" y1="{y}" x2="{cursor}" y2="{y+row_h}"/>')
            out.append(f'<line class="hair" x1="{x}" y1="{y+row_h}" x2="{x+total}" y2="{y+row_h}"/>')

    table(1500, range(1, 33))
    table(2002, range(33, 66))

    # Pin 21 reset note, with a matching split-colour key.
    out.append('<rect x="70" y="1359" width="25" height="18" rx="2" fill="#ffff00" stroke="#334155" stroke-width="1.8"/>')
    out.append('<path d="M 95 1359 L 95 1377 L 70 1377 Z" fill="#86efac"/>')
    out.append('<rect x="70" y="1359" width="25" height="18" rx="2" fill="none" stroke="#334155" stroke-width="1.8"/>')
    out.append(text(82.5, 1374, "†", 13, "middle", 900, "#0f172a"))
    out.append(text(105, 1374,
        "Pin 21 / RESETb: always resets Caravel; it directly resets the muxed user designs only when wb_rst_i propagation is enabled. Otherwise, restarted management firmware may reset them; mux/LA configuration selects the behaviour.",
        15, "start", 600, "#334155"))

    # Pin 36 optional user-reset note, keyed with the same bright yellow as its
    # mprj_io half so the relationship remains unambiguous.
    out.append('<rect x="70" y="1389" width="25" height="18" rx="2" fill="#ffff00" stroke="#334155" stroke-width="1.8"/>')
    out.append(text(82.5, 1404, "*", 14, "middle", 900, "#0f172a"))
    out.append(text(105, 1404,
        "Pin 36 / mprj_io[5] — opt_user_reset: optional active-high reset of all muxed user designs when LA[48]=0 and GPIO5 is a user input. Supplied Raybox firmware disables it; Caravel SER_RX shares the pad.",
        15, "start", 600, "#334155"))
    out.append(text(70, 1450,
        "U1/footprint: QFN-64-1EP_9×9mm_P0.5mm_EP7.65×7.65mm. Pin 65 is the exposed thermal pad, tied to GND on the reference board.",
        18, "start", 550, "#475569"))
    out.append(text(2535, 1450, "Physical pin order from efabless/caravel_board · Project mapping from algofoogle-multi-caravel (gf180)",
                    15, "end", 500, "#64748b"))
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schematic", type=Path, help="Caravel breakout .kicad_sch")
    parser.add_argument("-o", "--output", type=Path,
                        default=Path("caravel_raybox_zero_qfn64"),
                        help="output basename")
    parser.add_argument("--png", action="store_true", help="also render PNG")
    parser.add_argument("--pdf", action="store_true", help="also render PDF")
    args = parser.parse_args()
    pins = read_caravel_pins(args.schematic)
    svg_path = args.output.with_suffix(".svg")
    svg_path.write_text(make_svg(pins), encoding="utf-8")
    if args.png or args.pdf:
        inkscape = shutil.which("inkscape")
        if not inkscape:
            raise SystemExit("Inkscape is required for --png/--pdf")
        if args.png:
            subprocess.run([inkscape, str(svg_path), "--export-type=png",
                            f"--export-filename={args.output.with_suffix('.png')}",
                            "--export-width=5200"], check=True)
        if args.pdf:
            subprocess.run([inkscape, str(svg_path), "--export-type=pdf",
                            f"--export-filename={args.output.with_suffix('.pdf')}"], check=True)


if __name__ == "__main__":
    main()
