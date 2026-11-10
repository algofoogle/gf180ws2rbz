# Raybox Zero / Caravel useful links

An index of the main design sources, hardware references, code hot spots, and generated deliverables used while tracing the Wafer.Space and Caravel versions of Raybox Zero.

## Wafer.Space 1×0.5 ASIC

- [1×0.5 slot pad-ring definition (`slot_1x0p5.yaml`)](https://github.com/algofoogle/gf180ws2-raybox-zero/blob/main/librelane/slots/slot_1x0p5.yaml) — die dimensions and the ordered pad instances on all four edges.
- [Pad-ring generation script (`padring.py`)](https://github.com/algofoogle/gf180ws2-raybox-zero/blob/main/scripts/padring.py) — consumes the slot definition and establishes pad placement/orientation conventions.
- [1×0.5 COB mezzanine schematic](https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/blob/main/run-2/1x0p5-cob/mezzanine-1x0p5.kicad_sch) · [open in KiCanvas](https://kicanvas.org/?github=https%3A%2F%2Fgithub.com%2Fwafer-space%2Fchip-on-board-wire-bonded-pcbs%2Fblob%2Fmain%2Frun-2%2F1x0p5-cob%2Fmezzanine-1x0p5.kicad_sch) — the die-pad schematic symbol is reference `U102`.

## Caravel package and boards

- [Caravel QFN64 M.2-card schematic](https://github.com/efabless/caravel_board/blob/main/hardware/breakout/caravel-M.2-card-QFN/caravel-M.2-card-QFN.kicad_sch) · [open in KiCanvas](https://kicanvas.org/?github=https%3A%2F%2Fgithub.com%2Fefabless%2Fcaravel_board%2Fblob%2Fmain%2Fhardware%2Fbreakout%2Fcaravel-M.2-card-QFN%2Fcaravel-M.2-card-QFN.kicad_sch) — the `U1` symbol is the primary source for the physical QFN64 pin mapping.
- [Caravel GF180 5 V development-board schematic](https://github.com/efabless/caravel_board/blob/main/hardware/development/caravel-dev-gf180-v6-M.2/caravel-5V-dev-v6-M.2.kicad_sch) · [open in KiCanvas](https://kicanvas.org/?github=https%3A%2F%2Fgithub.com%2Fefabless%2Fcaravel_board%2Fblob%2Fmain%2Fhardware%2Fdevelopment%2Fcaravel-dev-gf180-v6-M.2%2Fcaravel-5V-dev-v6-M.2.kicad_sch) — also recognisable as **caravel-5V-dev-v6-M.2** within **caravel-dev-gf180-v6-M.2**; useful for the management SPI, firmware-flash, reset, clock, USB/FTDI, and board-level support circuitry.
- [Efabless `caravel_board` repository](https://github.com/efabless/caravel_board) — parent repository for the package-breakout and development-board hardware.
- [Caravel housekeeping flash utility (`caravel_hkflash.py`)](https://github.com/efabless/caravel_board/blob/main/firmware/chipignite/util/caravel_hkflash.py) — host-side firmware-flash programming through Caravel's housekeeping SPI path.
- [Caravel issue #26: SPI pass-through](https://github.com/efabless/caravel/issues/26) — historical context for the management SPI-slave-to-flash pass-through behaviour.

## Raybox Zero on Caravel: principal source files

- [Caravel user-project wrapper (`user_project_wrapper.v`)](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/user_project_wrapper.v) — top-level Caravel user-project wiring and Raybox Zero signal assignment.
- [Top design mux (`top_design_mux.v`)](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/mux/top_design_mux.v) — design selection, pad mapping, reset selection, and output-enable routing.
- [Raybox Zero FSM top level (`top_raybox_zero_fsm.v`)](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/raybox-zero-fsm/src/rtl/top_raybox_zero_fsm.v) — Raybox Zero ports, mode controls, output registration, and `gpout[*]` selection.
- [Caravel power-on I/O configuration (`user_defines.v`)](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/user_defines.v) — initial management/user ownership and direction of the `mprj_io` pads.
- [Raybox Zero test firmware (`trzf_test.c`)](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/firmware/trzf_test/trzf_test.c) — firmware setup for pad transfer, mux selection, reset, and `gpout` routing.
- [`gf180/firmware` directory](https://github.com/algofoogle/algofoogle-multi-caravel/tree/gf180/firmware) — related firmware examples and support code.

## Important code hot spots

### Verilog mapping and reset behaviour

- [`user_project_wrapper.v` lines 92–115](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/user_project_wrapper.v#L92-L115) — top-design-mux instance and logic-analyser control mapping.
- [`user_project_wrapper.v` lines 211–247](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/user_project_wrapper.v#L211-L247) — Raybox Zero signal wiring and the three `gpout` selectors.
- [`top_design_mux.v` lines 128–168](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/mux/top_design_mux.v#L128-L168) — synchronised mux controls and the available reset sources: Wishbone/system reset, `io_in[5]`, per-design reset, and automatic reset; design 0 is Raybox Zero.
- [`top_design_mux.v` lines 207–230](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/mux/top_design_mux.v#L207-L230) — design-0 physical `io_out` and `io_oeb` mapping, including VGA, texture/QSPI, general inputs, and `gpout[2:0]`.
- [`user_defines.v` line 55 at the examined revision](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/user_defines.v#L55) — power-on configuration of `mprj_io[5]`, which determines whether the optional external user-mux-reset route is initially usable.

### Raybox Zero modes, output registration, and `gpout`

- [`top_raybox_zero_fsm.v` lines 121–168](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/raybox-zero-fsm/src/rtl/top_raybox_zero_fsm.v#L121-L168) — registered-output and `gpout` instances.
- [`top_raybox_zero_fsm.v` lines 203–205](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/raybox-zero-fsm/src/rtl/top_raybox_zero_fsm.v#L203-L205) — mode mapping: `mode0_inc_px`, `mode1_inc_py`, and `mode2_gen_tex`.
- [`top_raybox_zero_fsm.v` lines 222–264](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/verilog/rtl/raybox-zero-fsm/src/rtl/top_raybox_zero_fsm.v#L222-L264) — complete `gpout[*]` source-selection table, including `tex_oeb0`, which exposes the `tex_io0` direction state.

### Firmware configuration sequence

- [`trzf_test.c` lines 21–43](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/firmware/trzf_test/trzf_test.c#L21-L43) — mux-control bitfields used by firmware.
- [`trzf_test.c` lines 66–75](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/firmware/trzf_test/trzf_test.c#L66-L75) — the two configuration-clock pulses used to commit mux configuration.
- [`trzf_test.c` lines 101–117](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/firmware/trzf_test/trzf_test.c#L101-L117) — selecting design 0 and choosing its reset policy.
- [`trzf_test.c` lines 119–155](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/firmware/trzf_test/trzf_test.c#L119-L155) — transferring pads `mprj_io[8:37]` to the user project with the required directions.
- [`trzf_test.c` lines 157–170](https://github.com/algofoogle/algofoogle-multi-caravel/blob/gf180/firmware/trzf_test/trzf_test.c#L157-L170) — explicit reset pulse and `gpout` selection.

### Management SPI and firmware flash

- [`caravel_hkflash.py` lines 22–33](https://github.com/efabless/caravel_board/blob/main/firmware/chipignite/util/caravel_hkflash.py#L22-L33) — programmer setup and housekeeping-SPI command definitions.
- [`caravel_hkflash.py` lines 185–192](https://github.com/efabless/caravel_board/blob/main/firmware/chipignite/util/caravel_hkflash.py#L185-L192) — releasing the Caravel CPU after programming.

## KiCad and KiCanvas references

- [KiCad Schematic Editor manual](https://docs.kicad.org/master/en/eeschema/eeschema.html) — symbol units, alternate representations, pin electrical types, and editor behaviour.
- [KiCad 10 Schematic Editor manual (PDF)](https://docs.kicad.org/10.0/en/eeschema/eeschema.pdf).
- [KiCad symbol-library file format](https://dev-docs.kicad.org/en/file-formats/sexpr-symbol-lib/) — `.kicad_sym` S-expression structure.
- [KiCad S-expression introduction](https://dev-docs.kicad.org/en/file-formats/sexpr-intro/index.html).
- [KiCad issue #6512](https://gitlab.com/kicad/code/kicad/-/issues/6512) and [issue #19983](https://gitlab.com/kicad/code/kicad/-/issues/19983) — relevant background on multi-unit symbols and shared symbol fields.
- [KiCanvas](https://kicanvas.org/) · [documentation](https://kicanvas.org/home/) · [source](https://github.com/theacodes/kicanvas) — browser-based viewing of KiCad schematics and boards.

## Generated deliverables

- [Caravel/Raybox Zero hardware-integration guide](https://chatgpt.com/library?file_id=libfile_fd14e39fd39881918834e80c9bdd7471&account_id=personal).
- [KiCad symbol generator (`generate_caravel_raybox_symbol.py`)](https://chatgpt.com/library?file_id=libfile_dbab681bda84819191f1b0f2785c812d&account_id=personal).
- [Generated KiCad symbol library (`caravel_raybox_zero.kicad_sym`)](https://chatgpt.com/library?file_id=libfile_fa2b6f09b73881919de7e9c6910810e2&account_id=personal) — contains the logical/block-oriented and package-oriented symbols.
- Caravel QFN64 diagram: [SVG](https://chatgpt.com/library?file_id=libfile_b2974fe16c3c81919a568cc06e0b18a8&account_id=personal), [PDF](https://chatgpt.com/library?file_id=libfile_a3b5d13b0bd481919abdfa6435095032&account_id=personal), [PNG](https://chatgpt.com/library?file_id=libfile_3cff5a0bdf308191ac9f5bb024f34e5d&account_id=personal), and [generator](https://chatgpt.com/library?file_id=libfile_8d6bdf1f3a5c8191a6c30a45254c7467&account_id=personal).
