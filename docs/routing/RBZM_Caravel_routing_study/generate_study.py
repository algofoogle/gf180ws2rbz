#!/usr/bin/env python3
"""Rebuild the RBZM placement study; Python 3 standard library only.

Inputs preserve header and QFN pad centres in millimetres.  This is a geometric
connectivity study, not an autorouter, DRC result or PCB design.
"""
from pathlib import Path
from collections import Counter
from itertools import combinations
from xml.sax.saxutils import escape
import argparse, csv, json, math, copy, hashlib

ROOT = Path(__file__).resolve().parent
ANGLES = (0, 45, 90)
EXTENSION_MM = 5.0
COLORS = {'controls':'#a145aa','blanking':'#a06a00','clock_reset':'#b22735',
          'control_spi':'#087d70','texture':'#146dd1','video':'#d27116',
          'service':'#6e5bc6','power':'#cc2233','ground':'#305eaf'}
LABELS = {'controls':'Demo / debug','blanking':'Blanking / diagnostics',
          'clock_reset':'Clock / reset','control_spi':'Shared control SPI',
          'texture':'Texture QSPI','video':'RGB / sync','service':'Caravel service',
          'power':'Supply guides','ground':'Ground guides'}

def rotate(p, angle):
    a=math.radians(angle);x,y=p
    return (x*math.cos(a)-y*math.sin(a),x*math.sin(a)+y*math.cos(a))

def pin_normal(q):
    return (-1,0) if q<=16 else (0,1) if q<=32 else (1,0) if q<=48 else (0,-1)

def tip_xy(data,q,angle):
    """5 mm beyond the 9 mm package body edge; retain tangential pad coordinate."""
    p=list(data['qfn'][str(q)]['xy'])
    if q==65:return rotate(p,angle)
    nx,ny=pin_normal(q)
    if nx:p[0]=nx*(data['body_mm']/2+EXTENSION_MM)
    if ny:p[1]=ny*(data['body_mm']/2+EXTENSION_MM)
    return rotate(p,angle)

def header_set(data, reverse=False):
    hs={h['pin']:dict(h) for h in data['headers']}
    if reverse:
        for p,n in zip(range(17,23),['RED0','RED1','GREEN0','GREEN1','BLUE0','BLUE1']):
            hs[f'R{p}']['name']=n
    return hs

def pinout_variant(data,mode='official'):
    """Official RBZM-1 is the default; old proposal is comparison-only."""
    if mode=='official':return data
    if mode!='archived':raise ValueError(mode)
    d=copy.deepcopy(data)
    old=json.loads((ROOT/'inputs/mapping_proposal_2026-11-16.json').read_text())
    d['headers']=old['headers'];d['_pinout']='archived'
    return d


def connections(data, angle, reverse=False, power=False):
    hs=header_set(data,reverse);byname={h['name']:h for h in hs.values()}
    result=[]
    for e in data['edges']:
        e=dict(e);e['header']=byname[e['net']]['pin']
        e['pad_xy']=rotate(data['qfn'][str(e['qfn'])]['xy'],angle)
        e['a']=tip_xy(data,e['qfn'],angle)
        e['b']=hs[e['header']]['xy'];result.append(e)
    if power:
        for n,pad in data['qfn'].items():
            name=pad['name'];g=('ground' if name.startswith('vss') or n=='65' else 'power' if name.startswith(('vdd','vcc')) else None)
            if not g:continue
            a=tip_xy(data,int(n),angle)
            candidates=[h for h in hs.values() if h['name']==('GND' if g=='ground' else 'RBZ_VDD')]
            h=min(candidates,key=lambda h:math.dist(a,h['xy']))
            result.append(dict(net='GND' if g=='ground' else 'RBZ_VDD',qfn=int(n),header=h['pin'],group=g,a=a,b=h['xy']))
    return result

def intersection(a,b,c,d):
    rx,ry=b[0]-a[0],b[1]-a[1];sx,sy=d[0]-c[0],d[1]-c[1]
    den=rx*sy-ry*sx
    if abs(den)<1e-9:return None
    cx,cy=c[0]-a[0],c[1]-a[1]
    t=(cx*sy-cy*sx)/den;u=(cx*ry-cy*rx)/den
    if 1e-6<t<1-1e-6 and 1e-6<u<1-1e-6:return (a[0]+t*rx,a[1]+t*ry)

def metrics(edges,angle,data):
    crosses=[];pairs=Counter();nets=Counter()
    for a,b in combinations(edges,2):
        if a['net']==b['net']:continue
        p=intersection(a['a'],a['b'],b['a'],b['b'])
        if p:
            crosses.append({'xy':p,'nets':[a['net'],b['net']],'qfn':[a['qfn'],b['qfn']]})
            pairs[' / '.join(sorted((a['group'],b['group'])))]+=1
            nets[a['net']]+=1;nets[b['net']]+=1
    # Free-wire versus fixed extensions: include all 64 leads, even local/unused pads.
    lead_hits=[]
    qnets={e['qfn']:e['net'] for e in connections(data,angle)}
    for e in edges:
        for q in range(1,65):
            if q==e['qfn'] or qnets.get(q)==e['net']:continue
            pad=data['qfn'][str(q)]['xy'];n=pin_normal(q)
            start=rotate((n[0]*data['body_mm']/2 if n[0] else pad[0],n[1]*data['body_mm']/2 if n[1] else pad[1]),angle)
            hit=intersection(e['a'],e['b'],start,tip_xy(data,q,angle))
            if hit:lead_hits.append(dict(xy=hit,net=e['net'],qfn=e['qfn'],fixed_qfn=q))
    # Coarse flag for free-wire chords passing through the physical package.
    transits=[]
    for e in edges:
        length=math.dist(e['a'],e['b']);hit=False
        for k in range(1,101):
            t=k/100
            if t*length<.75:continue
            p=rotate((e['a'][0]+t*(e['b'][0]-e['a'][0]),e['a'][1]+t*(e['b'][1]-e['a'][1])),-angle)
            if max(abs(p[0]),abs(p[1]))<4.5:hit=True;break
        if hit:transits.append(f"Q{e['qfn']} → {e['header']} {e['net']}")
    return dict(crossings=len(crosses),fixed_crossings=len(lead_hits),fixed_crossing_points=lead_hits,length_mm=round(sum(math.dist(e['a'],e['b']) for e in edges),1),
                pairs=dict(pairs.most_common()),nets=dict(nets.most_common()),crossing_points=crosses,
                body_transits=transits)

def text(x,y,s,size=.65,anchor='middle',color='#273448',weight='400',extra=''):
    return f'<text x="{x:.4f}" y="{y:.4f}" font-size="{size}" text-anchor="{anchor}" fill="{color}" font-weight="{weight}" {extra}>{escape(str(s))}</text>'

def wire_path(e,angle,curved):
    a,b=e['a'],e['b']
    if not curved:return f'M {a[0]} {a[1]} L {b[0]} {b[1]}'
    q=e['qfn'];n=(-1,0) if q<=16 else (0,1) if q<=32 else (1,0) if q<=48 else (0,-1)
    n=rotate(n,angle);bend=2.2+(q%4)*.15
    if curved==2:
        # A longer wire gets a longer straight departure and a stiffer tangent.
        # Its first cubic control point stays on the outward pin axis, so it
        # cannot immediately peel sideways into an adjacent 0.5 mm-pitch lead.
        length=math.dist(a,b)
        run=min(2.8,max(.8,length*.07))
        stiffness=min(12.0,max(4.0,length*.30))
        start=(a[0]+n[0]*run,a[1]+n[1]*run)
        c=(start[0]+n[0]*stiffness,start[1]+n[1]*stiffness)
        d=(b[0]+(1 if b[0]<0 else -1)*min(6,max(2,length*.15)),b[1])
        return f'M {a[0]} {a[1]} L {start[0]} {start[1]} C {c[0]} {c[1]} {d[0]} {d[1]} {b[0]} {b[1]}'
    c=(a[0]+n[0]*bend,a[1]+n[1]*bend)
    d=(b[0]+(3.0 if b[0]<0 else -3.0),b[1])
    return f'M {a[0]} {a[1]} C {c[0]} {c[1]} {d[0]} {d[1]} {b[0]} {b[1]}'

def svg(data,angle,reverse=False,curved=True,groups=None,show_crossings=False,power=False):
    hs=header_set(data,reverse);edges=connections(data,angle,reverse,power)
    if groups is not None:edges=[e for e in edges if e['group'] in groups]
    st=metrics([e for e in edges if e['group'] not in ('power','ground')],angle,data)
    title=f'{angle}° clockwise · {("Archived proposal" if data.get("_pinout")=="archived" else "Official RBZM-1")} · '+('R–G–B trial' if reverse else 'B–G–R baseline')
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1420" viewBox="-43 -32.5 86 67.8">',
         '<style>text{font-family:Arial,sans-serif} .halo{paint-order:stroke;stroke:white;stroke-width:.16px;stroke-linejoin:round} .wire{fill:none;stroke-width:.075;opacity:.72} .wire:hover{stroke-width:.23;opacity:1} .hidden{display:none}</style>',
         '<rect x="-43" y="-32.5" width="86" height="67.8" fill="#fff"/>',
         text(0,-30.5,'RBZM–CARAVEL / PHYSICAL CONNECTION STUDY',1.02,weight='700'),
         text(0,-28.8,title,.85),text(0,-27.4,'Top view • fixed leads extend 5 mm beyond each body edge • route from their tips',.61),
         '<rect x="-25" y="-25" width="50" height="50" rx="1" fill="#f8fbfc" stroke="#718394" stroke-width=".15"/>']
    for x in range(-20,25,5):out.append(f'<path d="M{x} -25V25 M-25 {x}H25" stroke="#dce5ea" stroke-width=".025"/>')
    for x in (-20.32,20.32):out.append(f'<rect x="{x-3.04}" y="-20.82" width="6.08" height="41.64" fill="#e9edf0" stroke="#a7b2bc" stroke-dasharray=".5 .4" stroke-width=".06"/>')
    out.append(f'<g transform="rotate({angle})"><rect x="-4.5" y="-4.5" width="9" height="9" fill="#d7e0e8" stroke="#526478" stroke-width=".10"/><rect x="-3.825" y="-3.825" width="7.65" height="7.65" fill="#bdc9d4" stroke="#526478" stroke-width=".03"/><circle cx="-3.75" cy="-3.75" r=".26" fill="#293a4d"/></g>')
    active={e['qfn']:e for e in edges}
    for q in range(1,65):
        pad=rotate(data['qfn'][str(q)]['xy'],angle);tip=tip_xy(data,q,angle)
        e=active.get(q);color=COLORS[e['group']] if e else '#aeb9c4'
        attrs=f'class="wire extension" data-net="{escape(e["net"])}" data-group="{e["group"]}"' if e else 'class="extension"'
        out.append(f'<path {attrs} d="M{pad[0]} {pad[1]} L{tip[0]} {tip[1]}" fill="none" stroke="{color}" stroke-width=".055"><title>QFN {q} → {e["header"] if e else "local"}: fixed 5 mm extension</title></path>')
        out.append(f'<circle cx="{tip[0]}" cy="{tip[1]}" r=".075" fill="{color}"/>')
    # One explicit lead-length dimension in local coordinates, rotated with package.
    out.append(f'<g transform="rotate({angle})"><path d="M4.5 -4.15V-5.05 M9.5 -4.15V-5.05 M4.5 -4.9H9.5" stroke="#526478" stroke-width=".045" fill="none"/>'+text(7,-5.13,'5 mm',.43)+'</g>')
    if show_crossings and not curved:
        for p in st['crossing_points']:
            x,y=p['xy'];out.append(f'<circle cx="{x}" cy="{y}" r=".17" fill="#e63851" opacity=".5"/>')
    for e in edges:
        net=escape(e['net'],{'"':'&quot;'});g=e['group'];d=wire_path(e,angle,curved)
        out.append(f'<path class="wire" data-net="{net}" data-group="{g}" d="{d}" stroke="{COLORS[g]}"><title>QFN {e["qfn"]} → {e["header"]}: {escape(e["net"])}</title></path>')
    # Pads are above wires. Side pad size/orientation comes from the original footprint.
    net_by_q={e['qfn']:e for e in edges}
    for n,p in data['qfn'].items():
        q=int(n)
        if q==65:continue
        x,y=p['xy'];w,h=p['size'];a=rotate(p['xy'],angle)
        col=COLORS[net_by_q[q]['group']] if q in net_by_q else '#64748b'
        out.append(f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" transform="rotate({angle})" fill="{col}" stroke="white" stroke-width=".015"><title>QFN {q}: {escape(p["name"])}</title></rect>')
        norm=(-1,0) if q<=16 else (0,1) if q<=32 else (1,0) if q<=48 else (0,-1)
        r=rotate((x+norm[0]*.8,y+norm[1]*.8),angle)
        out.append(text(*r,q,.37,extra='class="halo" dominant-baseline="central"'))
    out += [text(0,-.45,'GFMPW1',.9,weight='700'),text(0,.55,'9 × 9 mm',.65),text(0,1.4,'EP65 = GND',.5)]
    for h in hs.values():
        x,y=h['xy'];pin=h['pin'];name=h['name'];active=next((e for e in edges if e['header']==pin),None)
        col=COLORS[active['group']] if active else '#61788a'
        if name=='GND':col=COLORS['ground']
        elif name in ('RBZ_VDD','+5V','+3V3','+1V8','+1V2'):col=COLORS['power']
        # Wrap the complete header pad (including its pin number and label) so
        # its white interior and text participate in net hover/click handling.
        if active:
            out.append(f'<g class="net-target header-target" data-net="{escape(name)}" data-group="{active["group"]}"><title>{pin}: {escape(name)}</title>')
        else:
            out.append(f'<g><title>{pin}: {escape(name)} — no direct signal connection in this view</title>')
        shape=f'<rect x="{x-.85}" y="{y-.85}" width="1.7" height="1.7" rx="{0 if pin in ("L1","R1") else .4}" fill="#fff" stroke="{col}" stroke-width=".10"/>'
        out.extend([shape,text(x,y+.17,pin,.43,color=col,weight='700')])
        # Two separate label lines per header row, with a faint leader to the exact pad.
        left=pin.startswith('L');odd=int(pin[1:])%2;tx=-25.9 if left else 25.9;ty=y+(-.43 if odd else .50)
        out.append(f'<path d="M{x+(-.85 if left else .85)} {y} L{tx+(.25 if left else -.25)} {ty-.12}" fill="none" stroke="{col}" stroke-width=".035" opacity=".6"/>')
        out.append(text(tx,ty,f'{pin}  {name}',.54,'end' if left else 'start',col,'700' if name in ('GND','RBZ_VDD') else '400',extra='class="halo"'))
        out.append('</g>')
    out += [text(-20.32,-23.35,'LEFT · L',.72,weight='700'),text(20.32,-23.35,'RIGHT · R',.72,weight='700'),
            '<path d="M-20.32 22V23.2H20.32V22" fill="none" stroke="#536779" stroke-width=".06"/>',text(0,22.95,'40.64 mm between strip centres',.62),
            '<path d="M-5 24.05H5 M-5 23.8V24.3 M5 23.8V24.3" stroke="#263a50" stroke-width=".12"/>',text(0,24.85,'10 mm scale',.5),
            text(0,27,f'Tip-to-header chords: {st["crossings"]} wire/wire crossings; {st["fixed_crossings"]} wire/fixed-lead crossings; {st["length_mm"]} mm',.64),
            text(0,28.25,'Free-wire counts exclude same-net fan-outs and power. Fixed-lead checks include all 64 peripheral leads.',.57),
            text(0,29.35,'Curves aid viewing only; metrics always use straight tip-to-header chords. No routing or clearance claim.',.57)]
    for i,(g,label) in enumerate(list(LABELS.items())[:7]):
        x=-32+(i%4)*17.5;y=31.3+(i//4)*1.4
        out.append(f'<path d="M{x} {y-.2}h1.6" stroke="{COLORS[g]}" stroke-width=".15"/>');out.append(text(x+2,y,label,.58,'start'))
    out.append('</svg>');return '\n'.join(out)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'output');args=parser.parse_args()
    data=json.loads((ROOT/'inputs/mapping.json').read_text())
    canonical=ROOT/'inputs/RBZM_pinout.json'
    if canonical.exists():
        source=json.loads(canonical.read_text());names={p['pin']:p['name'] for p in source['pins']}
        for h in data['headers']:h['name']=names[h['pin']]
        for e in data['edges']:e['header']=next(p for p,n in names.items() if n==e['net'])
        data['pinout_revision']=source['revision']
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    results=[]
    for angle in ANGLES:
        for reverse in (False,True):
            m=metrics(connections(data,angle,reverse),angle,data)
            results.append(dict(angle=angle,rgb_order='RGB' if reverse else 'BGR',**m))
    (out/'metrics.json').write_text(json.dumps(results,indent=2)+'\n')
    with (out/'metrics.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['clockwise_degrees','header_colour_order','straight_crossing_pairs','tip_to_header_chord_mm','body_transit_edges','wire_fixed_lead_crossings'])
        for r in results:w.writerow([r['angle'],r['rgb_order'],r['crossings'],r['length_mm'],len(r['body_transits']),r['fixed_crossings']])
    with (out/'pin_mapping.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['QFN_pin','Caravel_pad','RBZM_pin','RBZM_signal','group','qfn_pad_x_mm','qfn_pad_y_mm','tip_x_mm','tip_y_mm','header_x_mm','header_y_mm'])
        for e in sorted(connections(data,0),key=lambda e:e['qfn']):w.writerow([e['qfn'],data['qfn'][str(e['qfn'])]['name'],e['header'],e['net'],e['group'],*e['pad_xy'],*e['a'],*e['b']])
    for angle in (0,45,90):
        for rev in (False,True):
            name=f'{angle:03d}deg_'+('RGB_trial' if rev else 'BGR_baseline')
            (out/f'{name}.svg').write_text(svg(data,angle,rev))
            (out/f'{name}_straight.svg').write_text(svg(data,angle,rev,False))
            (out/f'{name}_video.svg').write_text(svg(data,angle,rev,False,{'video'},True))
    all_results=[]
    for mode in ('official','archived'):
        variant=pinout_variant(data,mode)
        for angle in ANGLES:
            for reverse in (False,True):
                m=metrics(connections(variant,angle,reverse),angle,variant)
                all_results.append(dict(pinout=mode,angle=angle,rgb_order='RGB' if reverse else 'BGR',**m))
        with (out/f'pin_mapping_{mode}.csv').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['RBZM_pin','signal','x_mm','y_mm'])
            for h in variant['headers']:w.writerow([h['pin'],h['name'],*h['xy']])
        for angle in ANGLES:
            name=f'{angle:03d}deg_{mode}_extra_curved'
            (out/f'{name}.svg').write_text(svg(variant,angle,curved=2))
    (out/'pinout_comparison_metrics.json').write_text(json.dumps(all_results,indent=2)+'\n')
    with (out/'pinout_comparison_metrics.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['pinout','clockwise_degrees','RGB_order','free_wire_crossings','wire_fixed_lead_crossings','tip_to_header_chord_mm'])
        for m in all_results:w.writerow([m['pinout'],m['angle'],m['rgb_order'],m['crossings'],m['fixed_crossings'],m['length_mm']])
    (out/'interactive.html').write_text(html(data,all_results))
    # Side-by-side artwork keeps both panels at the same physical scale.
    panels=[]
    for x,a in [(0,0),(1800,45),(3600,90)]:
        s=svg(data,a);s=s.replace('<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1420"',f'<svg x="{x}" y="0" width="1800" height="1420"',1)
        panels.append(s)
    (out/'comparison.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="5400" height="1420" viewBox="0 0 5400 1420">'+''.join(panels)+'</svg>')
    (ROOT/'README.md').write_text(report(data,results,all_results))
    print(json.dumps([{k:r[k] for k in ('angle','rgb_order','crossings','length_mm')} for r in results],indent=2))

def report(data,results,all_results):
    lines=[]
    for a in ANGLES:
        n=next(m for m in all_results if m['pinout']=='official' and m['angle']==a and m['rgb_order']=='BGR')
        o=next(m for m in all_results if m['pinout']=='archived' and m['angle']==a and m['rgb_order']=='BGR')
        lines.append(f"| {a}° | {n['crossings']} | {n['fixed_crossings']} | {o['crossings']} | {o['fixed_crossings']} |")
    return '''# RBZM–Caravel physical connection study

**Official interface: RBZM-1, adopted 19 November 2026.**

The former Alternate pinout is now the official default in this viewer, generator and mapping exports. The 16 November proposal remains available only as **Archived proposal**. These pinouts are electrically incompatible: R1/R15 exchange GND and RBZ_VDD. Do not directly mate different revisions.

## Use

Open [output/interactive.html](output/interactive.html) in a browser. It is entirely offline. Select Official RBZM-1 or Archived proposal; rotation 0°, 45° or 90° clockwise; normal/reversed RGB ordering; and straight, curved or extra-curved wires. The scrollable checklist supports arbitrary net combinations, whole-group toggles and partial-selection indicators. Hover a wire, RBZM pad/number/label or checklist entry to preview a net; click a wire or pad to toggle it. Selection persists across views.

Extra-curved mode adds a length-weighted straight departure of 0.8–2.8 mm and an outward Bézier handle of 4–12 mm. This reduces immediate sideways bending near the virtual pin tips. It is a display aid, not an obstacle-avoiding router.

## Physical model

The module is 50 × 50 mm. Fixed 2×16 headers use 2.54 mm pitch with 40.64 mm between strip centres. Both banks have odd contacts west of even contacts. The QFN body is 9 × 9 mm with actual source-footprint pad centres at 0.5 mm pitch. Pin 1 is at top-left on the west edge at 0°. Positive rotation is visually clockwise; the previous 45° and 90° placements are retained.

All 64 peripheral leads extend straight outward to tips 5.00 mm beyond the body edge. Tip coordinates at 0° therefore use ±9.50 mm on the relevant edge axis; the other coordinate retains pad pitch. Copper pad centres are at ±4.45 mm, so the drawn centre-to-tip line is 5.05 mm. EP65 remains a central ground pad, without an extension. The real KiCad footprint is not enlarged.

Free wires run from the fixed lead tips to the actual header pad centres. Geometry, power guides, pad colours and exported mappings all use the selected pinout. Official supply contacts are L14/R15, with R1 now GND. GEN_TEXb and REG remain direct connections; module-type-aware controller firmware handles their polarity differences.

## Crossing proxy

All metrics use straight free chords, regardless of display style. Same-net branches/shared endpoints are excluded. Free-wire/fixed-lead counts include intersections against all 64 fixed lead extensions. Counts are segment-pair crossings, not unique crossing locations, required vias, DRC results or proof of routability.

| Rotation | Official wire/wire | Official wire/fixed lead | Archived wire/wire | Archived wire/fixed lead |
|---|---:|---:|---:|---:|
'''+ '\n'.join(lines)+'''

The normal B–G–R colour-pair ordering is retained. Reversed RGB is a separate experimental display/mapping trial, not an adopted interface revision. Routing may detour around leads and the body, merge common-net trunks and change layers; this study does none of those things. Metrics exclude power/ground free guides, optional VISIBLE glue wiring and local boot-flash/buffer placement. Reserve real space for those parts and bypass capacitors.

## Outputs and regeneration

- `output/comparison.svg`: official 0°/45°/90° at identical scale.
- `output/metrics.json` and `.csv`: official pinout, both RGB-order trials.
- `output/pinout_comparison_metrics.json` and `.csv`: official versus archived.
- `output/pin_mapping.csv`: QFN-to-official-header signal branches.
- `output/pin_mapping_official.csv` and `_archived.csv`: all 64 contacts for each revision.
- `*_official_extra_curved.svg` and `*_archived_extra_curved.svg`: separate static views.
- `inputs/mapping.json`: official source data. `inputs/mapping_proposal_2026-11-16.json` is archived comparison data only.

Run `python3 generate_study.py` (standard library only). PNG previews optionally use Inkscape. All source footprint snapshots are under `inputs/`; chip-pad numbering comes from the Efabless QFN64 schematic and physical footprint. Original upstream URLs remain in `mapping.json`.

The official RBZM guide and KiCad library have been updated alongside this study; this folder does not modify an existing user project automatically.
'''

def html(data,results):
    variants={mode:pinout_variant(data,mode) for mode in ('official','archived')}
    views={f'{mode}_{a}_{int(r)}_{c}':svg(variant,a,r,c,power=True) for mode,variant in variants.items() for a in ANGLES for r in (False,True) for c in (0,1,2)}
    template='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>RBZM–Caravel routing study</title>
<style>
body{margin:0;font:15px system-ui;color:#1c3044;background:#eef3f7}header{padding:18px 24px;background:#163248;color:white}h1{margin:0 0 6px;font-size:25px}.controls{padding:14px 20px;background:white;position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:12px;align-items:center}select,input,button{font:inherit}main{display:grid;grid-template-columns:minmax(700px,1fr) 370px;gap:12px;padding:12px}#canvas{overflow:auto;background:white;height:82vh}#canvas svg{display:block;width:100%;height:auto;min-width:900px}aside{background:white;padding:16px;overflow:auto;max-height:78vh}h2{font-size:18px}td,th{text-align:left;padding:5px;border-bottom:1px solid #dde5ec;font-size:13px}table{border-collapse:collapse;width:100%}.note{font-size:13px;color:#526377}#inspect{padding:10px;background:#eef3f7;min-height:45px;font-size:13px;overflow-wrap:anywhere}button{cursor:pointer}.wire,.net-target{cursor:pointer}.header-target rect{pointer-events:all}.net-actions{display:flex;gap:8px;margin-bottom:10px}.net-list{max-height:340px;overflow-y:auto;border:1px solid #ced8e0;border-radius:5px;padding:6px}.net-group{border-bottom:1px solid #e3e9ee;padding:5px 0}.net-group:last-child{border:0}.group-title{display:flex;gap:6px;align-items:center;font-weight:650;padding:4px;cursor:pointer}.net-children{padding-left:20px}.net-row{display:flex;gap:7px;align-items:flex-start;font-size:13px;padding:4px 2px;cursor:pointer}.net-row:hover{background:#edf5fa}.net-row input,.group-title input{flex:none}.net-row span{overflow-wrap:anywhere}.header-target.preview rect{fill:#fff2b2}.header-target.off rect{stroke-opacity:.35}.header-target.off text{opacity:.45}.net-row.preview{background:#fff2b2} @media(max-width:1100px){main{grid-template-columns:1fr}aside{max-height:none}#canvas{height:auto}}
</style>
<header><h1>RBZM–Caravel physical connection study</h1><div>Fixed 5 mm outward leads • 50 × 50 mm module • direct GEN_TEXb / REG connections</div></header>
<div class="controls"><label>RBZM pinout <select id="pinout"><option value="official">Official RBZM-1</option><option value="archived">Archived proposal — not compatible</option></select></label><label>QFN rotation <select id="angle">__ANGLES__</select></label><label>Header RGB order <select id="rgb"><option value="0">B–G–R baseline</option><option value="1">R–G–B trial</option></select></label><label>Wires <select id="curved"><option value="1">Curved for readability</option><option value="0">Straight metric geometry</option><option value="2">Extra-curved — stiff departure</option></select></label><label>Zoom <input id="zoom" type="range" min="75" max="250" value="100" step="25"></label><button id="save">Download current SVG</button></div>
<main><div id="canvas"></div><aside><h2>Inspect nets</h2><div class="net-actions"><button id="all">Show all signals</button><button id="none">Hide all</button></div><div id="nets" class="net-list" aria-label="Visible nets grouped by function"></div><p class="note">Check any combination. Parent checkboxes toggle whole groups; a dash means some children are selected. Hover a wire, pad square or list entry to preview its complete net. Click a wire or pad to toggle that net. Selections persist across view changes.</p><p id="inspect" aria-live="polite">Hover a wire, pad or checklist entry to inspect its connections.</p><h2>Geometric comparison</h2><div id="stats"></div><p class="note">Metrics always use all 39 signal branches, even when nets are hidden. Counts compare straight chords, never required vias or routed lengths. Fixed-lead counts include all 64 peripheral leads.</p><h2>Highest crossover groups</h2><div id="pairs"></div><h2>Three orientations</h2><div id="angles"></div><h2>Scope</h2><p class="note">0° places pin 1 at top-left, on the west edge. Positive angles are clockwise. All leads extend 5 mm beyond the package edge; free wires start at their tips. Odd header pins are west of even pins on both banks. Official RBZM-1 is the adopted pinout, with RBZ_VDD on L14/R15 and GND on R1. The archived proposal is for comparison only and is electrically incompatible. RGB order can be tested independently. Extra-curved wires have a length-weighted straight departure and a longer tangent along the extended pin axis. Curve choices do not change the straight-chord metrics.</p><p class="note">Power and ground guides are optional. Header pads stay visible when nets are unchecked; hovering an unchecked pad temporarily previews its wires. Local boot flash, level shifter and VISIBLE gate placement are not assumed. RBZM_ID is open on Caravel. GEN_TEXb and REG connect directly as requested.</p></aside></main>
<script>
const VIEWS=__VIEWS__,METRICS=__METRICS__,DATA=__DATA__,COLORS=__COLORS__,LABELS=__LABELS__;
const $=s=>document.getElementById(s);
const model=new Map();
for(const e of DATA.edges)model.set(e.net,{group:e.group});
model.set('RBZ_VDD',{group:'power'});model.set('GND',{group:'ground'});
const enabled=new Set([...model].filter(([n,m])=>!['power','ground'].includes(m.group)).map(([n])=>n));
let hovered='';const children=new Map(),parents=new Map(),rows=new Map();
for(const [group,label] of Object.entries(LABELS)){
 const box=document.createElement('section');box.className='net-group';
 const heading=document.createElement('label');heading.className='group-title';heading.style.color=COLORS[group];
 const parent=document.createElement('input');parent.type='checkbox';parent.setAttribute('aria-label','Toggle '+label);parents.set(group,parent);
 heading.append(parent,document.createTextNode(label));box.append(heading);
 const list=document.createElement('div');list.className='net-children';box.append(list);$('nets').append(box);
 const members=[...model].filter(([n,m])=>m.group===group).map(([n])=>n).sort();children.set(group,members);
 parent.onchange=()=>{for(const n of members)parent.checked?enabled.add(n):enabled.delete(n);sync();paint()};
 for(const n of members){
  const row=document.createElement('label');row.className='net-row';const cb=document.createElement('input');cb.type='checkbox';cb.dataset.net=n;cb.checked=enabled.has(n);
  const name=document.createElement('span');name.textContent=n;row.append(cb,name);list.append(row);rows.set(n,{row,cb});
  cb.onchange=()=>{cb.checked?enabled.add(n):enabled.delete(n);sync();paint()};
  row.onmouseenter=()=>preview(n);row.onmouseleave=()=>preview('');
 }
}
function sync(){for(const [n,{cb}] of rows)cb.checked=enabled.has(n);for(const [g,cb] of parents){const ns=children.get(g),count=ns.filter(n=>enabled.has(n)).length;cb.checked=count===ns.length;cb.indeterminate=count>0&&count<ns.length}}
function describe(n){
 if(!n)return 'Hover a wire, pad or checklist entry to inspect its connections.';
 const qs=[...new Set(DATA.edges.filter(e=>e.net===n).map(e=>e.qfn))];
 const pads=[...$('canvas').querySelectorAll('.header-target')].filter(p=>p.dataset.net===n).map(p=>p.querySelector('title').textContent.split(':')[0]);
 return n+' — '+(qs.length?'QFN '+qs.join(', '):'Supply/ground guide')+' → '+[...new Set(pads)].join(', ');
}
function paint(){
 $('canvas').querySelectorAll('.wire').forEach(p=>{const n=p.dataset.net,on=enabled.has(n)||hovered===n;p.style.display=on?'':'none';p.style.opacity=hovered?(n===hovered?'1':'.10'):'.72';p.style.strokeWidth=hovered===n?'.19':(p.classList.contains('extension')?'.055':'.075')});
 $('canvas').querySelectorAll('.header-target').forEach(p=>{p.classList.toggle('preview',p.dataset.net===hovered);p.classList.toggle('off',!enabled.has(p.dataset.net))});
 for(const [n,{row}] of rows)row.classList.toggle('preview',n===hovered);
 $('inspect').textContent=describe(hovered);
}
function preview(n){hovered=n;paint()}
function toggle(n){enabled.has(n)?enabled.delete(n):enabled.add(n);sync();paint()}
function render(){
 const mode=$('pinout').value,a=+$('angle').value,r=+$('rgb').value,c=+$('curved').value;hovered='';$('canvas').innerHTML=VIEWS[`${mode}_${a}_${r}_${c}`];$('canvas').querySelector('svg').style.width=$('zoom').value+'%';
 const m=METRICS.find(m=>m.pinout===mode&&m.angle===a&&m.rgb_order===(r?'RGB':'BGR'));
 $('stats').innerHTML=`<b>${m.crossings}</b> free-wire crossing pairs<br><b>${m.fixed_crossings}</b> wire/fixed-lead crossings<br><b>${m.length_mm} mm</b> tip-to-header chord length`;
 $('pairs').innerHTML='<table>'+Object.entries(m.pairs).slice(0,7).map(([k,v])=>`<tr><td>${k.replaceAll('_',' ')}</td><td>${v}</td></tr>`).join('')+'</table>';
 $('angles').innerHTML='<table><tr><th>CW</th><th>BGR</th><th>RGB trial</th></tr>'+[0,45,90].map(a=>`<tr><td>${a}°</td>`+['BGR','RGB'].map(o=>`<td>${METRICS.find(m=>m.pinout===mode&&m.angle===a&&m.rgb_order===o).crossings}</td>`).join('')+'</tr>').join('')+'</table>';
 $('canvas').querySelectorAll('.wire,.net-target').forEach(p=>{p.onmouseenter=()=>preview(p.dataset.net);p.onmouseleave=()=>preview('');p.onclick=()=>toggle(p.dataset.net)});sync();paint();
}
for(const id of ['pinout','angle','rgb','curved','zoom'])$(id).oninput=render;
$('all').onclick=()=>{for(const [n,m] of model)if(!['power','ground'].includes(m.group))enabled.add(n);hovered='';sync();paint()};
$('none').onclick=()=>{enabled.clear();hovered='';sync();paint()};
$('save').onclick=()=>{const a=document.createElement('a'),s=$('canvas').querySelector('svg').cloneNode(true);s.setAttribute('width','1800');s.setAttribute('height','1420');s.style.width='';const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(s)],{type:'image/svg+xml'}));a.href=url;a.download=`RBZM_${$('pinout').value}_${$('angle').value}deg_${$('rgb').value==='1'?'RGB':'BGR'}.svg`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
render();
</script></html>'''
    for key,value in [('ANGLES',''.join(f'<option value="{a}" '+('selected' if a==0 else '')+f'>{a}° clockwise</option>' for a in ANGLES)),('VIEWS',json.dumps(views)),('METRICS',json.dumps(results)),('DATA',json.dumps(data)),('COLORS',json.dumps(COLORS)),('LABELS',json.dumps(LABELS))]:template=template.replace('__'+key+'__',value)
    return template

if __name__=='__main__':main()
