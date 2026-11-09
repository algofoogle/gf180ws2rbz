#!/usr/bin/env python3
"""Generate KiCad symbols for the Caravel-based Raybox Zero.

The output is a KiCad 8/9/10-compatible .kicad_sym library containing two
symbols:

  Caravel_Raybox_Zero_Blocks
    Unit A  RBZ I/O
    Unit B  RBZ Caravel
    Unit C  RBZ Power/ground

  Caravel_Raybox_Zero_Chip
    One package-oriented unit.  Viewed from the top, pin 1 is at the top of
    the west edge and pins 1..64 proceed anticlockwise around the package.

Run with no arguments to create ``caravel_raybox_zero.kicad_sym`` beside the
script, or pass an explicit output path:

    python generate_caravel_raybox_symbol.py -o my_symbols.kicad_sym
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


BLOCKS_SYMBOL_NAME = "Caravel_Raybox_Zero_Blocks"
CHIP_SYMBOL_NAME = "Caravel_Raybox_Zero_Chip"
DEFAULT_FOOTPRINT = (
    "Package_DFN_QFN:QFN-64-1EP_9x9mm_P0.5mm_EP7.65x7.65mm"
)


@dataclass(frozen=True)
class Pin:
    number: int
    name: str
    electrical: str
    side: str
    gap_before: int = 0
    shape: str = "line"


def pin(number: int, name: str, electrical: str, side: str,
        gap_before: int = 0, shape: str = "line") -> Pin:
    return Pin(number, name, electrical, side, gap_before, shape)


# Pin names lead with the function a board designer normally wants to see.
# A one-row gap before a pin starts a new functional group.
UNITS: tuple[tuple[str, tuple[Pin, ...]], ...] = (
    (
        "RBZ I/O",
        (
            # View-vector SPI slave: io[24:22].
            pin(60, "vec_cs_n/io[22]", "input", "left", shape="inverted"),
            pin(61, "vec_sclk/io[23]", "input", "left", shape="clock"),
            pin(62, "vec_mosi/io[24]", "input", "left"),
            # Register SPI slave: io[27:25].
            pin(2, "reg_cs_n/io[25]", "input", "left", 1, "inverted"),
            pin(3, "reg_sclk/io[26]", "input", "left", shape="clock"),
            pin(4, "reg_mosi/io[27]", "input", "left"),
            # Debug controls: io[30:28].
            pin(5, "debug_vec/io[28]", "input", "left", 1),
            pin(6, "debug_map/io[29]", "input", "left"),
            pin(7, "debug_trace/io[30]", "input", "left"),
            # Active-low registered-output enable: io[31].
            pin(8, "reg_outs_enb/io[31]", "input", "left", 1, "inverted"),
            # Demo mode controls: io[34:32].
            pin(11, "mode0_inc_px/io[32]", "input", "left", 1),
            pin(12, "mode1_inc_py/io[33]", "input", "left"),
            pin(13, "mode2_gen_tex/io[34]", "input", "left"),
            # VGA: io[15:8].
            pin(42, "hsync_n/io[8]", "output", "right", shape="inverted"),
            pin(43, "vsync_n/io[9]", "output", "right", shape="inverted"),
            pin(44, "rgb[0]/io[10]", "output", "right"),
            pin(45, "rgb[1]/io[11]", "output", "right"),
            pin(46, "rgb[2]/io[12]", "output", "right"),
            pin(48, "rgb[3]/io[13]", "output", "right"),
            pin(50, "rgb[4]/io[14]", "output", "right"),
            pin(51, "rgb[5]/io[15]", "output", "right"),
            # Texture QSPI master: io[21:16].  Keep the bus together even
            # though its individual pins have different directions.
            pin(53, "tex_cs_n/io[16]", "output", "right", 1, "inverted"),
            pin(54, "tex_sclk/io[17]", "output", "right"),
            pin(55, "tex_io0/io[18]", "bidirectional", "right"),
            pin(57, "tex_io1/io[19]", "input", "right"),
            pin(58, "tex_io2/io[20]", "input", "right"),
            pin(59, "tex_io3/io[21]", "input", "right"),
            # General-purpose diagnostic outputs: io[37:35].
            pin(14, "gpout[0]/io[35]", "output", "right", 1),
            pin(15, "gpout[1]/io[36]", "output", "right"),
            pin(16, "gpout[2]/io[37]", "output", "right"),
        ),
    ),
    (
        "RBZ Caravel",
        (
            # Housekeeping: io[4:0], kept together on one side.
            pin(31, "jtag/io[0]", "input", "left"),
            pin(32, "hk_sdo/miso/io[1]", "output", "left"),
            pin(33, "hk_sdi/mosi/io[2]", "input", "left"),
            pin(34, "hk_csb/cs_n/io[3]", "input", "left", shape="inverted"),
            pin(35, "hk_sck/io[4]", "input", "left", shape="clock"),
            # Management serial/reset overlays: io[6:5].
            pin(36, "opt_user_reset/ser_rx/io[5]", "input", "left", 1),
            pin(37, "ser_tx/io[6]", "output", "left"),
            # Management interrupt: io[7].
            pin(41, "irq/io[7]", "input", "left", 1),
            # Package reset and shared system clock, at the top right.
            pin(21, "RESETb", "input", "right", shape="inverted"),
            pin(22, "system_clk", "input", "right", shape="clock"),
            # Dedicated management firmware-flash pins 24..27.  In this
            # implementation IO0 is always MOSI/output and IO1 MISO/input.
            pin(24, "flash_csb", "output", "right", 1, "inverted"),
            pin(25, "flash_clk", "output", "right"),
            pin(26, "flash_io0/mosi", "output", "right"),
            pin(27, "flash_io1/miso", "input", "right"),
            # Standalone management GPIO.
            pin(28, "gpio", "bidirectional", "right", 1),
        ),
    ),
    (
        "RBZ Power/ground",
        (
            pin(9, "vdda2", "power_in", "left"),
            pin(17, "vddio", "power_in", "left"),
            pin(18, "vccd", "power_in", "left"),
            pin(30, "vdda", "power_in", "left"),
            pin(40, "vdda1", "power_in", "left"),
            pin(47, "vdda1", "power_in", "left"),
            pin(49, "vccd1", "power_in", "left"),
            pin(63, "vccd2", "power_in", "left"),
            pin(64, "vddio", "power_in", "left"),
            # Physical no-connect stands apart from the supply group.
            pin(19, "N/C", "no_connect", "left", 1),
            pin(1, "vssa2", "power_in", "right"),
            pin(10, "vssd2", "power_in", "right"),
            pin(20, "vssa", "power_in", "right"),
            pin(23, "vssd", "power_in", "right"),
            pin(29, "vssio", "power_in", "right"),
            pin(38, "vssa1", "power_in", "right"),
            pin(39, "vssd1", "power_in", "right"),
            pin(52, "vssa1", "power_in", "right"),
            pin(56, "vssio", "power_in", "right"),
            pin(65, "ThermalPad/GND", "power_in", "right"),
        ),
    ),
)

# Per-unit body half-width and half-height in millimetres.
UNIT_GEOMETRY = {
    1: (27.94, 27.94),
    2: (27.94, 20.32),
    3: (27.94, 16.51),
}


def q(value: str) -> str:
    """Quote a KiCad string."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def effects(size: float = 1.27, justify: str | None = None) -> str:
    justification = f" (justify {justify})" if justify else ""
    return f"(effects (font (size {size:g} {size:g})){justification})"


def property_line(name: str, value: str, x: float, y: float,
                  hidden: bool = False) -> str:
    hide = " (hide yes)" if hidden else ""
    return (
        f"    (property {q(name)} {q(value)} (at {x:g} {y:g} 0) "
        f"{effects()}{hide})"
    )


def render_pin(item: Pin, x: float, y: float) -> str:
    rotation = 0 if item.side == "left" else 180
    return "\n".join(
        (
            f"      (pin {item.electrical} {item.shape} (at {x:g} {y:g} {rotation}) "
            f"(length 5.08)",
            f"        (name {q(item.name)} {effects()})",
            f"        (number {q(str(item.number))} {effects()})",
            "      )",
        )
    )


def render_unit(unit_number: int, title: str, pins: tuple[Pin, ...]) -> str:
    left = [item for item in pins if item.side == "left"]
    right = [item for item in pins if item.side == "right"]
    row_count = max(
        len(left) + sum(item.gap_before for item in left),
        len(right) + sum(item.gap_before for item in right),
    )
    pitch = 2.54
    body_half_width, body_half_height = UNIT_GEOMETRY[unit_number]
    top_y = (row_count - 1) * pitch / 2
    pin_x = body_half_width + 5.08

    lines = [
        f"    (symbol {q(f'{BLOCKS_SYMBOL_NAME}_{unit_number}_1')}",
        f"      (rectangle (start {-body_half_width:g} {body_half_height:g}) "
        f"(end {body_half_width:g} {-body_half_height:g})",
        "        (stroke (width 0) (type default))",
        "        (fill (type background))",
        "      )",
        f"      (text {q(title)} (at 0 {body_half_height - 1.905:g} 0)",
        "        (effects (font (size 1.27 1.27) (bold yes)))",
        "      )",
    ]

    def add_side(side_pins: list[Pin], x: float) -> None:
        y = top_y
        for item in side_pins:
            y -= item.gap_before * pitch
            lines.append(render_pin(item, x, y))
            y -= pitch

    add_side(left, -pin_x)
    add_side(right, pin_x)
    lines.append("    )")
    return "\n".join(lines)


def render_package_pin(item: Pin, x: float, y: float, rotation: int) -> str:
    return "\n".join(
        (
            f"      (pin {item.electrical} {item.shape} "
            f"(at {x:g} {y:g} {rotation}) (length 5.08)",
            f"        (name {q(item.name)} {effects()})",
            f"        (number {q(str(item.number))} {effects()})",
            "      )",
        )
    )


def render_chip_unit() -> str:
    """Render a top-view, package-oriented QFN64 representation."""
    by_number = {
        item.number: item
        for _title, unit_pins in UNITS
        for item in unit_pins
    }
    # Add 200 mil (5.08 mm) at each side and 300 mil (7.62 mm) at both
    # top and bottom compared with the previous package-view body.
    body_half_width = 43.18
    body_half_height = 33.02
    pin_x = body_half_width + 5.08
    pin_y = body_half_height + 5.08
    pitch = 2.54
    first = 15 * pitch / 2

    lines = [
        f"    (symbol {q(f'{CHIP_SYMBOL_NAME}_1_1')}",
        f"      (rectangle (start {-body_half_width:g} {body_half_height:g}) "
        f"(end {body_half_width:g} {-body_half_height:g})",
        "        (stroke (width 0) (type default))",
        "        (fill (type background))",
        "      )",
        f"      (text {q('CARAVEL RAYBOX ZERO — QFN64 TOP VIEW')} "
        "(at 0 0 0)",
        "        (effects (font (size 1.27 1.27) (bold yes)))",
        "      )",
        # Pin-1 indicator near the top-left corner of the package body.
        f"      (circle (center {-body_half_width + 2.54:g} "
        f"{body_half_height - 2.54:g}) "
        f"(radius 1.27)",
        "        (stroke (width 0) (type default))",
        "        (fill (type none))",
        "      )",
    ]

    # West: pin 1 at the top, then 2..16 downwards.
    for index, number in enumerate(range(1, 17)):
        lines.append(
            render_package_pin(
                by_number[number], -pin_x, first - index * pitch, 0
            )
        )

    # South: pins 17..32 from west to east.
    for index, number in enumerate(range(17, 33)):
        lines.append(
            render_package_pin(
                by_number[number], -first + index * pitch, -pin_y, 90
            )
        )

    # East: pins 33..48 from south to north.
    for index, number in enumerate(range(33, 49)):
        lines.append(
            render_package_pin(
                by_number[number], pin_x, -first + index * pitch, 180
            )
        )

    # North: pins 49..64 from east to west.
    for index, number in enumerate(range(49, 65)):
        lines.append(
            render_package_pin(
                by_number[number], first - index * pitch, pin_y, 270
            )
        )

    # Put the exposed thermal pad low on the east edge, leaving three unused
    # pin positions below pin 33 so it remains visually distinct.
    pin33_y = -first
    lines.append(
        render_package_pin(by_number[65], pin_x, pin33_y - 4 * pitch, 180)
    )
    lines.append("    )")
    return "\n".join(lines)


def validate_pin_data() -> None:
    pins = [item for _title, unit in UNITS for item in unit]
    numbers = [item.number for item in pins]
    expected = list(range(1, 66))
    if sorted(numbers) != expected:
        missing = sorted(set(expected) - set(numbers))
        duplicates = sorted(number for number in set(numbers) if numbers.count(number) > 1)
        raise ValueError(f"invalid package pin coverage; missing={missing}, duplicates={duplicates}")
    valid_types = {"input", "output", "bidirectional", "power_in", "no_connect"}
    valid_shapes = {"line", "inverted", "clock"}
    for item in pins:
        if item.electrical not in valid_types:
            raise ValueError(f"pin {item.number}: invalid electrical type {item.electrical}")
        if item.side not in {"left", "right"}:
            raise ValueError(f"pin {item.number}: invalid side {item.side}")
        if item.gap_before < 0:
            raise ValueError(f"pin {item.number}: gap_before cannot be negative")
        if item.shape not in valid_shapes:
            raise ValueError(f"pin {item.number}: invalid graphical shape {item.shape}")
        if "mprj_io" in item.name:
            raise ValueError(f"pin {item.number}: use the shortened io prefix")
        if " /" in item.name or "/ " in item.name:
            raise ValueError(f"pin {item.number}: slash separators must not have spaces")


def validate_sexpr(text: str) -> None:
    """Catch quoting or parenthesis mistakes without requiring KiCad."""
    depth = 0
    quoted = False
    escaped = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("unexpected closing parenthesis")
    if quoted or depth:
        raise ValueError(f"unbalanced output: quoted={quoted}, parenthesis_depth={depth}")


def render_blocks_symbol() -> str:
    lines = [
        f"  (symbol {q(BLOCKS_SYMBOL_NAME)}",
        "    (pin_names (offset 1.016))",
        "    (exclude_from_sim no)",
        "    (in_bom yes)",
        "    (on_board yes)",
        "    (property \"Reference\" \"U\" (at -27.94 29.21 0) "
        + effects(justify="left") + ")",
        f"    (property \"Value\" {q(BLOCKS_SYMBOL_NAME)} (at 27.94 -29.21 0) "
        + effects(justify="right") + ")",
        property_line("Footprint", DEFAULT_FOOTPRINT, 0, 0, hidden=True),
        property_line(
            "Datasheet",
            "https://github.com/efabless/caravel_board/blob/main/hardware/breakout/"
            "caravel-M.2-card-QFN/caravel-M.2-card-QFN.kicad_sch",
            0,
            0,
            hidden=True,
        ),
        property_line(
            "Description",
            "Caravel GF180 QFN64 with Raybox Zero mux design 0; logical three-unit symbol",
            0,
            0,
            hidden=True,
        ),
    ]
    for unit_number, (title, pins) in enumerate(UNITS, start=1):
        lines.append(render_unit(unit_number, title, pins))
    lines.append("  )")
    return "\n".join(lines)


def render_chip_symbol() -> str:
    return "\n".join(
        (
            f"  (symbol {q(CHIP_SYMBOL_NAME)}",
            "    (pin_names (offset 1.016))",
            "    (exclude_from_sim no)",
            "    (in_bom yes)",
            "    (on_board yes)",
            "    (property \"Reference\" \"U\" (at -43.18 40.64 0) "
            + effects(justify="left") + ")",
            f"    (property \"Value\" {q(CHIP_SYMBOL_NAME)} "
            f"(at 45.72 40.64 0) {effects(justify='right')})",
            property_line("Footprint", DEFAULT_FOOTPRINT, 0, 0, hidden=True),
            property_line(
                "Datasheet",
                "https://github.com/efabless/caravel_board/blob/main/hardware/"
                "breakout/caravel-M.2-card-QFN/caravel-M.2-card-QFN.kicad_sch",
                0,
                0,
                hidden=True,
            ),
            property_line(
                "Description",
                "Caravel GF180 QFN64 with Raybox Zero mux design 0; "
                "package-oriented top-view symbol",
                0,
                0,
                hidden=True,
            ),
            render_chip_unit(),
            "  )",
        )
    )


def generate() -> str:
    validate_pin_data()
    lines = [
        "(kicad_symbol_lib",
        "  (version 20231120)",
        '  (generator "raybox_kicad_symbol_generator")',
        render_blocks_symbol(),
        render_chip_symbol(),
        ")",
        "",
    ]
    result = "\n".join(lines)
    validate_sexpr(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).with_name("caravel_raybox_zero.kicad_sym"),
        help="output KiCad symbol library (default: beside this script)",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    text = generate()
    output.write_text(text, encoding="utf-8", newline="\n")
    print(
        f"Wrote {output} (2 symbols: {BLOCKS_SYMBOL_NAME} with {len(UNITS)} "
        f"units, {CHIP_SYMBOL_NAME} with 1 unit; "
        f"{sum(len(unit) for _title, unit in UNITS)} package pins each)"
    )


if __name__ == "__main__":
    main()
