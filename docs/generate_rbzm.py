#!/usr/bin/env python3
"""Generate the RBZM KiCad symbol library and paired-header footprint."""

import argparse
from pathlib import Path


NAME = "RBZM_Raybox_Zero_Module"
LIBRARY = "Anton"
PITCH = 2.54
STRIP_SPACING = 16 * PITCH

# Physical order within each bank: west (odd), east (even), then next row.
BANKS = (
    ("L", "Left", """
        KEY GND DEBUG GND INC_X INC_Y GEN_TEXb REG
        HBLANK/GPOUT0 VBLANK/GPOUT1 DIAG/GPOUT2 VISIBLE GND RBZ_VDD GND CLK
        GND RESET_N RBZM_ID RB_READY RESERVED0 GND GND +5V
        GND +1V8 GND +1V2 RESERVED1 RESERVED2 GND RESERVED3
    """.split()),
    ("R", "Right", """
        RBZ_VDD GND CTRL_REG_CSb VEC_CSb RBZM_SPI_MOSI RBZM_SPI_SCK HK_SDO HK_CSb
        TEX_IO3 TEX_IO2 TEX_IO1 TEX_IO0 TEX_SCK TEX_CSb GND GND
        BLUE0 BLUE1 GREEN0 GREEN1 RED0 RED1 VSYNC_N HSYNC_N
        SER_TX SER_RX/OPT_URST RESERVED4 GND +3V3 GND RESERVED5 GND
    """.split()),
)
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
        f'{STRIP_SPACING:.2f} mm spacing" (at 0 0 0) {HIDDEN_FONT})',
    ]
    for unit, (bank, side, signals) in enumerate(BANKS, 1):
        lines.extend((
            f'(symbol "{NAME}_{unit}_1"',
            f'(text "{side} ({bank})" (at 0 -24.77 0) {FONT})',
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
        f'{STRIP_SPACING:.2f} mm between strip centers")',
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


if __name__ == "__main__":
    main()
