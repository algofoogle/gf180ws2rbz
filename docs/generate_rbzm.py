#!/usr/bin/env python3
"""Generate the RBZM KiCad symbol library and paired-header footprint."""

import argparse
import json
import csv
from pathlib import Path


NAME = "RBZM_Raybox_Zero_Module"
LIBRARY = "Anton"
PITCH = 2.54
STRIP_SPACING = 16 * PITCH

# Physical order within each bank: west (odd), east (even), then next row.
BANKS = (
    ('L', 'Left', ['KEY', 'GND', 'DEBUG', 'GND', 'REG', 'INC_X', 'GEN_TEXb', 'INC_Y', 'VBLANK/GPOUT1', 'HBLANK/GPOUT0', 'DIAG/GPOUT2', 'VISIBLE', 'GND', 'RBZ_VDD', 'GND', 'RESET_N', 'GND', 'CLK', 'RBZM_ID', 'RB_READY', 'RESERVED0', 'GND', 'GND', '+5V', 'GND', '+1V8', 'GND', '+1V2', 'RESERVED1', 'RESERVED2', 'GND', 'RESERVED3']),
    ('R', 'Right', ['GND', 'GND', 'RBZM_SPI_SCK', 'RBZM_SPI_MOSI', 'CTRL_REG_CSb', 'VEC_CSb', 'HK_CSb', 'HK_SDO', 'TEX_IO3', 'TEX_IO2', 'TEX_IO1', 'TEX_IO0', 'TEX_SCK', 'TEX_CSb', 'RBZ_VDD', 'GND', 'BLUE0', 'BLUE1', 'GREEN0', 'GREEN1', 'RED0', 'RED1', 'HSYNC_N', 'VSYNC_N', 'SER_RX/OPT_URST', 'SER_TX', 'RESERVED4', 'GND', '+3V3', 'GND', 'RESERVED5', 'GND']),
)
REVISION = "RBZM-1 (2026-11-19)"
PIN_METADATA = {'KEY': {'direction': 'NC', 'function': 'Mechanical key position', 'target': 'Both'}, 'GND': {'direction': 'Return', 'function': 'Common ground', 'target': 'Both'}, 'DEBUG': {'direction': 'In', 'function': 'Debug control', 'target': 'Both'}, 'INC_X': {'direction': 'In', 'function': 'Demo motion on X', 'target': 'Both'}, 'INC_Y': {'direction': 'In', 'function': 'Demo motion on Y', 'target': 'Both'}, 'GEN_TEXb': {'direction': 'In', 'function': 'Generated-texture control; WS low true, Caravel high true', 'target': 'Both'}, 'REG': {'direction': 'In', 'function': 'Registered-output control; WS high true, Caravel low true', 'target': 'Both'}, 'HBLANK/GPOUT0': {'direction': 'Out', 'function': 'Horizontal blanking or diagnostic', 'target': 'Both'}, 'VBLANK/GPOUT1': {'direction': 'Out', 'function': 'Vertical blanking or diagnostic', 'target': 'Both'}, 'DIAG/GPOUT2': {'direction': 'Out', 'function': 'Diagnostic output', 'target': 'Both, optional on WS'}, 'VISIBLE': {'direction': 'Out', 'function': 'Active-video indication', 'target': 'Both, optional'}, 'RBZ_VDD': {'direction': 'Power in', 'function': 'Selectable ASIC supply', 'target': 'Both'}, 'CLK': {'direction': 'In', 'function': 'System/pixel reference clock', 'target': 'Both'}, 'RESET_N': {'direction': 'In', 'function': 'Primary reset, low true', 'target': 'Both'}, 'RBZM_ID': {'direction': 'Sense', 'function': 'Passive module identification', 'target': 'Both'}, 'RB_READY': {'direction': 'Out', 'function': 'Module ready indication', 'target': 'Both, optional on WS'}, 'RESERVED0': {'direction': '—', 'function': 'Reserved contact', 'target': 'Future'}, '+5V': {'direction': 'Power in', 'function': 'Fixed auxiliary rail', 'target': 'Optional'}, '+1V8': {'direction': 'Power in', 'function': 'Fixed auxiliary rail', 'target': 'Future / optional'}, '+1V2': {'direction': 'Power in', 'function': 'Fixed auxiliary rail', 'target': 'Future / optional'}, 'RESERVED1': {'direction': '—', 'function': 'Reserved contact', 'target': 'Future'}, 'RESERVED2': {'direction': '—', 'function': 'Reserved contact', 'target': 'Future'}, 'RESERVED3': {'direction': '—', 'function': 'Reserved contact', 'target': 'Future'}, 'CTRL_REG_CSb': {'direction': 'In', 'function': 'WS CTRL or Caravel register SPI select', 'target': 'Both'}, 'VEC_CSb': {'direction': 'In', 'function': 'Vector SPI select', 'target': 'Caravel'}, 'RBZM_SPI_MOSI': {'direction': 'In', 'function': 'Shared control SPI data', 'target': 'Both'}, 'RBZM_SPI_SCK': {'direction': 'In', 'function': 'Shared control SPI clock', 'target': 'Both'}, 'HK_SDO': {'direction': 'Out', 'function': 'Dedicated housekeeping SPI return', 'target': 'Caravel'}, 'HK_CSb': {'direction': 'In', 'function': 'Housekeeping SPI select', 'target': 'Caravel'}, 'TEX_IO3': {'direction': 'In', 'function': 'Texture read-data bit 3', 'target': 'Both¹'}, 'TEX_IO2': {'direction': 'In', 'function': 'Texture read-data bit 2', 'target': 'Both'}, 'TEX_IO1': {'direction': 'In', 'function': 'Texture read-data bit 1', 'target': 'Both'}, 'TEX_IO0': {'direction': 'Bidir', 'function': 'Texture command data and read-data bit 0', 'target': 'Both'}, 'TEX_SCK': {'direction': 'Out', 'function': 'Texture flash clock', 'target': 'Both'}, 'TEX_CSb': {'direction': 'Out', 'function': 'Texture flash select, low true', 'target': 'Both'}, 'BLUE0': {'direction': 'Out', 'function': 'Blue LSB', 'target': 'Both'}, 'BLUE1': {'direction': 'Out', 'function': 'Blue MSB', 'target': 'Both'}, 'GREEN0': {'direction': 'Out', 'function': 'Green LSB', 'target': 'Both'}, 'GREEN1': {'direction': 'Out', 'function': 'Green MSB', 'target': 'Both'}, 'RED0': {'direction': 'Out', 'function': 'Red LSB', 'target': 'Both'}, 'RED1': {'direction': 'Out', 'function': 'Red MSB', 'target': 'Both'}, 'VSYNC_N': {'direction': 'Out', 'function': 'Vertical sync, low true', 'target': 'Both'}, 'HSYNC_N': {'direction': 'Out', 'function': 'Horizontal sync, low true', 'target': 'Both'}, 'SER_TX': {'direction': 'Out', 'function': 'Module UART transmit', 'target': 'Caravel / future'}, 'SER_RX/OPT_URST': {'direction': 'In²', 'function': 'Module UART receive or optional user reset', 'target': 'Caravel / future'}, 'RESERVED4': {'direction': '—', 'function': 'Reserved contact', 'target': 'Future'}, '+3V3': {'direction': 'Power in', 'function': 'Fixed auxiliary rail, e.g. boot flash', 'target': 'Both, as needed'}, 'RESERVED5': {'direction': '—', 'function': 'Reserved contact', 'target': 'Future'}}

ACTIVE_LOW = {
    "GEN_TEXb", "RESET_N", "CTRL_REG_CSb", "VEC_CSb",
    "HK_CSb", "TEX_CSb", "HSYNC_N", "VSYNC_N",
}
END_PINS = (1, 2, 31, 32)
FONT = "(effects (font (size 1.27 1.27)))"
HIDDEN_FONT = "(effects (font (size 1.27 1.27)) (hide yes))"


def row_y(pin):
    """Return the row coordinate in PCB orientation, positive downwards."""
    return ((pin - 1) // 2 - 7.5) * PITCH


def rectangle(x1, y1, x2, y2, width, fill="none"):
    return (
        f'(rectangle (start {x1} {y1}) (end {x2} {y2}) '
        f'(stroke (width {width}) (type default)) (fill (type {fill})))'
    )


def symbol_library():
    lines = [
        '(kicad_symbol_lib (version 20231120) (generator "rbzm")',
        f'(symbol "{NAME}"',
        '(pin_names (offset 0.762)) (in_bom yes) (on_board yes)',
        f'(property "Reference" "J" (at -22.86 25.4 0) {FONT})',
        f'(property "Value" "Raybox Zero Module (RBZM)" (at 0 25.4 0) {FONT})',
        f'(property "Footprint" "{LIBRARY}:{NAME}" (at 0 0 0) {HIDDEN_FONT})',
        f'(property "Description" "Raybox Zero Module interface, two 2x16 headers at '
        f'{STRIP_SPACING:.2f} mm spacing; {REVISION}" (at 0 0 0) {HIDDEN_FONT})',
    ]
    for unit, (bank, side, signals) in enumerate(BANKS, 1):
        lines.extend((
            f'(symbol "{NAME}_{unit}_1"',
            f'(text "{side} ({bank}) - RBZM-1" (at 0 -24.77 0) {FONT})',
            rectangle(-22.86, 22.86, 22.86, -22.86, 0.254),
            rectangle(-3.81, 22.86, 3.81, -22.86, 0.254),
        ))
        for pin in END_PINS:
            x = -1.9 if pin % 2 else 1.9
            y = 21.36 if pin <= 2 else -21.36
            lines.append(
                f'(text "{bank}{pin}" (at {x} {y} 0) (effects (font (size 0.9 0.9))))'
            )
        for pin, signal in enumerate(signals, 1):
            odd = pin % 2
            y = -row_y(pin)
            key = signal == "KEY"
            if key:
                lines.append(rectangle(-1.77, 19.55, -0.77, 18.55, 0.18, "outline"))
            else:
                x = -1.27 if odd else 1.27
                lines.append(
                    f'(circle (center {x} {y:.2f}) (radius 0.47) '
                    '(stroke (width 0.18) (type default)) (fill (type none)))'
                )
            electrical_type = "no_connect" if key else "passive"
            style = "inverted" if signal in ACTIVE_LOW else "line"
            x, angle = (-29.21, 0) if odd else (29.21, 180)
            lines.append(
                f'(pin {electrical_type} {style} (at {x} {y:.2f} {angle}) (length 6.35) '
                f'(name "{signal}" {FONT}) (number "{bank}{pin}" (effects (font (size 1 1)))))'
            )
        lines.append(")")
    return "\n".join([*lines, "))", ""])


def footprint():
    lines = [
        f'(footprint "{NAME}" (version 20240108) (generator "rbzm")',
        '(layer "F.Cu")',
        f'(descr "Two 2x16 {PITCH} mm through-hole strips, '
        f'{STRIP_SPACING:.2f} mm between strip centers; {REVISION}")',
        '(attr through_hole)',
        f'(property "Reference" "REF**" (at 0 -22 0) (layer "F.SilkS") {FONT})',
        f'(property "Value" "{NAME}" (at 0 22 0) (layer "F.Fab") {FONT})',
    ]
    for bank, _, signals in BANKS:
        center = (-1 if bank == "L" else 1) * STRIP_SPACING / 2
        for layer, dx, dy, width in (
            ("F.Fab", 2.54, 20.32, 0.1),
            ("F.CrtYd", 3.04, 20.82, 0.05),
            ("F.SilkS", 2.65, 20.43, 0.12),
        ):
            lines.append(
                f'(fp_rect (start {center - dx:.2f} {-dy}) (end {center + dx:.2f} {dy}) '
                f'(stroke (width {width}) (type default)) (fill none) (layer "{layer}"))'
            )
        for pin in END_PINS:
            offset, justify = (-0.5, "right") if pin % 2 else (0.5, "left")
            y = -21.7 if pin <= 2 else 21.7
            knockout = " knockout" if (bank, pin) == ("L", 1) else ""
            lines.append(
                f'(fp_text user "{bank}{pin}" (at {center + offset:.2f} {y} 0) '
                f'(layer "F.SilkS"{knockout}) '
                f'(effects (font (size 1 1) (thickness 0.12)) (justify {justify})))'
            )
        for pin in range(1, len(signals) + 1):
            x = center + (-PITCH / 2 if pin % 2 else PITCH / 2)
            shape = "rect" if pin == 1 else "oval"
            lines.append(
                f'(pad "{bank}{pin}" thru_hole {shape} (at {x:.2f} {row_y(pin):.2f}) '
                '(size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask"))'
            )
    return "\n".join([*lines, ")", ""])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    if any(len(signals) != 32 for _, _, signals in BANKS):
        raise ValueError("Each RBZM bank must define 32 signals")
    footprint_dir = args.output_dir / f"{LIBRARY}.pretty"
    footprint_dir.mkdir(parents=True, exist_ok=True)
    for path, contents in (
        (args.output_dir / "RBZM.kicad_sym", symbol_library()),
        (footprint_dir / f"{NAME}.kicad_mod", footprint()),
    ):
        path.write_text(contents, encoding="utf-8", newline="\n")
        print(path)

    records=[]
    for bank,side,names in BANKS:
        for i,name in enumerate(names,1):
            records.append(dict(pin=f'{bank}{i}',name=name,bank=bank,x_mm=(-1 if bank=='L' else 1)*STRIP_SPACING/2+(-PITCH/2 if i%2 else PITCH/2),y_mm=row_y(i),**PIN_METADATA[name]))
    (args.output_dir/'RBZM_pinout.json').write_text(json.dumps(dict(revision=REVISION,pins=records),indent=2)+'\n')
    with (args.output_dir/'RBZM_pinout.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)


if __name__ == "__main__":
    main()
