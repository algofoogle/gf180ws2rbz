# Raybox Zero on GF180 Caravel: Hardware Integration, Boot, Clock and Reset Guide

## Purpose and scope

This note describes how to put the GF180 **Caravel** implementation of Raybox Zero (mux **design 0**) onto a PCB and bring it into a known operating state. It focuses on the differences from the standalone wafer.space 1×0.5 ASIC, especially the extra management-SoC, firmware, pad-multiplexing and reset layers introduced by Caravel.

The key conclusion is:

> The Caravel part does not become a usable Raybox Zero merely because its power, clock and package `RESETb` pins are connected. Management firmware must configure the clock, establish a known mux state, transfer the GPIO configuration, and explicitly reset/release design 0.

The source revision examined for the multi-project design is commit [`9871f786`](https://github.com/algofoogle/algofoogle-multi-caravel/tree/9871f786967d514317c7a2e1e2b2107cce685c2d). The Caravel RTL examined is commit [`2b51db49`](https://github.com/efabless/caravel-gf180mcu/tree/2b51db499eb77d4dea77789f0ec97326ecb912c6), and the QFN64 reference board is commit [`2812cfd3`](https://github.com/efabless/caravel_board/tree/2812cfd3896e2b1004b5f4559e0601c90cd18f55).

## System-level architecture

The relevant signal path is:

1. QFN64 power, `clock` and `resetb` pins start Caravel.
2. Caravel's management SoC boots firmware from an external SPI flash.
3. Firmware controls the user-project mux through Logic Analyzer (LA) outputs.
4. The mux selects design 0, generates the Raybox reset, and routes design 0's outputs to `mprj_io[37:8]`.
5. The Caravel GPIO configuration determines whether each physical pad is connected to the management SoC or the user project, and whether its electrical direction is controlled by the user design.

The mux control mapping is defined in [`user_project_wrapper.v` lines 75–127](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/user_project_wrapper.v#L75-L127):

| LA signal | Purpose |
|---|---|
| `LA[48]` | Active-low enable for `mprj_io[5]` as a reset source |
| `LA[52:49]` | Four-bit design selection; `0` selects Raybox Zero design 0 |
| `LA[53]` | Active-low enable for propagation of `wb_rst_i` into the user designs |
| `LA[54]` | Active-low enable for automatically holding unselected designs in reset |
| `LA[62:55]` | Individual active-high resets for designs 0–7 |
| `LA[63]` | Mux configuration clock |

The clock supplied to Raybox Zero is `wb_clk_i`, not `user_clock2` and not necessarily a transparent copy of QFN pin 22. The mux simply repeats `wb_clk_i` to every design ([`top_design_mux.v` lines 170–178](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/mux/top_design_mux.v#L170-L178)). Caravel derives that clock from its clock-control path.

## Power-up behavior

### What starts in a safe state

The project-specific [`user_defines.v`](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/user_defines.v#L41-L92) configures GPIOs 5–37 as **user-side inputs with no pull** at power-up. GPIOs 0–4 are special Caravel management/debug pins whose initial functions are fixed.

This safe-input policy prevents Raybox outputs from driving the PCB before firmware has selected a design and completed the pad transfer. It also means that external Raybox inputs must not be allowed to float merely because the ASIC powers up with its own pads configured as inputs.

The example firmware later writes GPIOs 8–37 as `GPIO_MODE_USER_STD_BIDIRECTIONAL` and requests `reg_mprj_xfer` ([`trzf_test.c` lines 119–155](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/firmware/trzf_test/trzf_test.c#L119-L155)). The mux's `io_oeb` bus then decides the actual input/output direction of the selected design's pins.

### What does **not** have a defined reset

The mux selection and three mux reset-policy controls use two-stage registers clocked by `LA[63]`. The RTL explicitly states that these registers have **no reset** and can persist across a full Caravel system reset ([`top_design_mux.v` lines 128–146](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/mux/top_design_mux.v#L128-L146)).

Consequences:

- A package reset must not be assumed to restore the mux to design 0.
- A cold power-up must not rely on the silicon power-up value of those mux registers.
- Firmware must present the desired mux-control bits and give `mux_conf_clk` **two rising edges**, because the controls pass through two flip-flops.
- Pressing package `RESETb` can restart firmware without changing the previously latched mux policy. Firmware must therefore re-establish the policy every time it boots.

The supplied `load_mux_state()` routine deliberately pulses the configuration clock twice ([`trzf_test.c` lines 66–75](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/firmware/trzf_test/trzf_test.c#L66-L75)).

## The complete Raybox reset equation

For design 0, the generated Raybox reset is:

```text
trzf_rst = design_reset[0]
         OR (auto_reset_enabled AND selected_design != 0)
         OR (system_reset_enabled AND wb_rst_i)
         OR (io5_reset_enabled AND mprj_io[5])
```

This is implemented directly in [`top_design_mux.v` lines 143–159](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/mux/top_design_mux.v#L143-L159).

There are therefore four ways design 0 can be held in reset:

1. **Explicit design reset:** assert `LA[55]`.
2. **Automatic unselected-design reset:** enable auto-reset and select a design other than 0.
3. **Caravel-system reset propagation:** enable the `wb_rst_i` path.
4. **Optional external user reset:** enable the `mprj_io[5]` path and drive that input high.

The first source is not part of the mux's double-flop configuration bank; it is a live LA control. The example firmware pulses `LA[55]` only after it has completed the GPIO transfer ([`trzf_test.c` lines 157–159](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/firmware/trzf_test/trzf_test.c#L157-L159)). This explicit pulse is important because design state otherwise need not be initialized merely by selecting the design.

Also note that `trzf_ena` is generated by the mux but is not used by the instantiated Raybox design. Selecting another design disconnects Raybox's outputs, but does not by itself stop or reset Raybox unless auto-reset or another reset source is enabled.

## Pin 21: `RESETb`

QFN pin 21 is Caravel's package-level, active-low reset input. In Caravel's clock/reset logic, the external reset is combined with power-on reset and the housekeeping reset source:

```verilog
resetb_async = porb & resetb & !ext_reset;
```

See [`caravel_clocking.v` lines 24–55](https://github.com/efabless/caravel-gf180mcu/blob/2b51db499eb77d4dea77789f0ec97326ecb912c6/verilog/rtl/caravel_clocking.v#L24-L55). The resulting Caravel reset is inverted to form `user_reset`, which reaches `user_project_wrapper` as `wb_rst_i` ([`mgmt_protect.v` lines 162–164](https://github.com/efabless/caravel-gf180mcu/blob/2b51db499eb77d4dea77789f0ec97326ecb912c6/verilog/rtl/mgmt_protect.v#L162-L164) and [`caravel_core.v` lines 364–389](https://github.com/efabless/caravel-gf180mcu/blob/2b51db499eb77d4dea77789f0ec97326ecb912c6/verilog/rtl/caravel_core.v#L364-L389)).

Pin 21 therefore has three practically relevant behaviors:

- It **always resets/restarts Caravel's management system**.
- It **directly resets Raybox Zero** only if firmware previously enabled `wb_rst_i` propagation by loading `LA[53]=0` into the mux control register.
- If that propagation is disabled, pin 21 can still reset Raybox **indirectly and later**: it restarts the management SoC, and the restarted firmware can reconfigure the mux and pulse `design_reset[0]`.

The supplied Raybox test firmware deliberately selects `MUX_SYSR_DIS`, so pin 21 does **not** directly feed the Raybox reset in that configuration. Its eventual effect on Raybox depends on successful firmware restart and execution.

### PCB treatment of pin 21

- Give `RESETb` a defined inactive state; do not leave it floating.
- Provide a test point, reset button/header, or supervisor connection.
- Treat it as the primary way to restart the whole Caravel system and rerun initialization.
- Do not advertise it as an unconditional, asynchronous Raybox-only reset unless the firmware policy is fixed to enable `wb_rst_i` propagation and that policy has already been loaded.
- Because the mux policy registers are themselves unreset, package `RESETb` is not a substitute for firmware reinitializing the mux.

## Pin 36: `mprj_io[5]`, `ser_rx`, and `opt_user_reset`

QFN pin 36 is a multiply-used pad:

- Caravel management UART receive, `ser_rx`, when that management function is selected.
- User-project input `mprj_io[5]` when the pad is assigned to the user project.
- Active-high reset for **all muxed user designs** when the mux's IO5-reset path is enabled.

The project-specific power-up definition for GPIO5 is `GPIO_MODE_USER_STD_INPUT_NOPULL` ([`user_defines.v` line 55](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/user_defines.v#L55)). This is why the pad can be made available as an external user-reset input without first changing its direction. However, the reset behavior still depends on the mux control having been loaded with `LA[48]=0` and clocked twice.

The supplied Raybox firmware instead sets `MUX_IO5R_DIS`, so pin 36 is **not a reset input** under that firmware image.

### PCB treatment of pin 36

- If `opt_user_reset` will be supported, use an external pull-down so it remains inactive during power-up, firmware boot and pad-mode transitions.
- Label it as optional/conditional rather than as the sole system reset.
- The input is active-high, unlike the standalone wafer.space ASIC's active-low `RESET_N`. A board intended to accept a common active-low reset signal needs an inverter or other polarity conversion before driving pin 36.
- Do not enable or drive the management UART receiver on the same pad while using it as `opt_user_reset`.
- If the function is not used, hold it at a defined low level or leave the pad solely in its chosen Caravel role according to the validated pad configuration.

Pin 36 is most useful as a fast post-boot reset of Raybox and the other muxed user designs. It is not a replacement for pin 21 because it cannot restart the management SoC and its reset behavior is not established until the mux configuration has been loaded.

## Selecting and starting Raybox Zero design 0

The supplied firmware implements the following sequence:

1. Start executing from Caravel's external management flash.
2. Configure the DLL/dividers to produce a 25 MHz user/Wishbone clock.
3. Configure both LA banks so the management SoC can drive the mux controls and Raybox LA inputs.
4. Clear the Raybox LA input bank.
5. Construct mux state `0x7F210000`:
   - select design 0;
   - hold all other designs in reset;
   - disable pin-36/IO5 reset propagation;
   - disable `wb_rst_i` propagation;
   - enable automatic reset of unselected designs.
6. Clock that state into the mux twice.
7. Configure `mprj_io[37:8]` as user-controlled bidirectional pads and complete `reg_mprj_xfer`.
8. Pulse `design_reset[0]` high and low.
9. Program the LA-controlled `gpout[2:0]` source selections.

The reference implementation is [`firmware/trzf_test/trzf_test.c`](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/firmware/trzf_test/trzf_test.c).

### Recommended production policy

For a board that should behave consistently like a dedicated Raybox appliance, firmware should do this on **every** boot and reset:

1. Establish a conservative clock first.
2. Drive all LA control values to known states.
3. Assert `design_reset[0]` while loading mux design 0 and while transferring the GPIO configuration.
4. Keep auto-reset enabled for unselected designs.
5. Decide explicitly whether pin 21 and/or pin 36 should propagate reset; do not inherit an old mux state.
6. Complete the GPIO transfer.
7. Configure Raybox mode and `gpout` selections.
8. Release `design_reset[0]` only after the clock and all external inputs are stable.
9. Signal “Raybox ready” through the dedicated Caravel `gpio`, a selected `gpout`, or an external supervisor-visible indicator.

Holding design 0 in reset throughout reconfiguration is safer than the test firmware's brief final reset pulse because it prevents partially configured activity from appearing at the pins.

## Clocking and QFN pin 22

QFN pin 22 is the Caravel `clock` input. It clocks both the management system and, through Caravel's clock-control path, the selected user design. It is a **CMOS clock input, not a two-pin crystal oscillator interface**.

The reference Caravel board uses a 10 MHz oscillator. The Raybox test firmware multiplies that by five and divides by two to obtain 25 MHz ([`trzf_test.c` lines 91–99](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/firmware/trzf_test/trzf_test.c#L91-L99)).

For a wafer.space-compatible system interface:

- Treat pin 22 as the board's system clock input.
- If the same external clock source is used for both ASIC versions, the Caravel firmware must either pass it through or deliberately synthesize the frequency expected by Raybox.
- Confirm the actual VGA timing produced by the chosen clock. The reference firmware's 25 MHz is close to, but not exactly, the conventional 25.175 MHz 640×480 pixel clock.
- Keep reset asserted, or keep design 0 explicitly reset, until the selected clock source is stable.

## Design 0 signal mapping on QFN64

The following table is the practical PCB mapping for Raybox design 0. The `rgb` bus is `BBGGRR`, so the individual colour assignments are shown explicitly.

| QFN pin | Caravel signal | Raybox function | Direction at PCB |
|---:|---|---|---|
| 2 | `mprj_io[25]` | `reg_cs_n` | Input |
| 3 | `mprj_io[26]` | `reg_sclk` | Input |
| 4 | `mprj_io[27]` | `reg_mosi` | Input |
| 5 | `mprj_io[28]` | `debug_vec` | Input |
| 6 | `mprj_io[29]` | `debug_map` | Input |
| 7 | `mprj_io[30]` | `debug_trace` | Input |
| 8 | `mprj_io[31]` | `reg_outs_enb` | Input |
| 11 | `mprj_io[32]` | `mode0_inc_px` (`mode[0]`): increment player X | Input |
| 12 | `mprj_io[33]` | `mode1_inc_py` (`mode[1]`): increment player Y | Input |
| 13 | `mprj_io[34]` | `mode2_gen_tex` (`mode[2]`): select generated textures | Input |
| 14 | `mprj_io[35]` | `gpout[0]` | Output |
| 15 | `mprj_io[36]` | `gpout[1]` | Output |
| 16 | `mprj_io[37]` | `gpout[2]` | Output |
| 21 | `resetb` | `RESETb` for Caravel; conditional relationship to Raybox | Input, active-low |
| 22 | `clock` | `system_clk` feeding Caravel and Raybox | Input |
| 36 | `mprj_io[5]` / `ser_rx` | `opt_user_reset` when enabled | Input, active-high |
| 42 | `mprj_io[8]` | `hsync_n` | Output |
| 43 | `mprj_io[9]` | `vsync_n` | Output |
| 44 | `mprj_io[10]` | `rgb[0]` = red bit 0 | Output |
| 45 | `mprj_io[11]` | `rgb[1]` = red bit 1 | Output |
| 46 | `mprj_io[12]` | `rgb[2]` = green bit 0 | Output |
| 48 | `mprj_io[13]` | `rgb[3]` = green bit 1 | Output |
| 50 | `mprj_io[14]` | `rgb[4]` = blue bit 0 | Output |
| 51 | `mprj_io[15]` | `rgb[5]` = blue bit 1 | Output |
| 53 | `mprj_io[16]` | `tex_cs_n` | Output |
| 54 | `mprj_io[17]` | `tex_sclk` | Output |
| 55 | `mprj_io[18]` | `tex_io0` | Bidirectional |
| 57 | `mprj_io[19]` | `tex_io1` | Input |
| 58 | `mprj_io[20]` | `tex_io2` | Input |
| 59 | `mprj_io[21]` | `tex_io3` | Input; currently unused internally |
| 60 | `mprj_io[22]` | `vec_cs_n` | Input |
| 61 | `mprj_io[23]` | `vec_sclk` | Input |
| 62 | `mprj_io[24]` | `vec_mosi` | Input |

The signal wiring comes from [`user_project_wrapper.v` lines 217–247](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/user_project_wrapper.v#L217-L247), while the output direction and selection are in [`top_design_mux.v` lines 207–230](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/mux/top_design_mux.v#L207-L230).

The expanded mode-pin names describe their active-high functions: `mode0_inc_px` advances the player/viewpoint X position, `mode1_inc_py` advances its Y position, and `mode2_gen_tex` selects internally generated textures instead of the external SPI texture source. The underlying RTL bus names remain `mode[0]`, `mode[1]` and `mode[2]`.

## `gpout[2:0]` diagnostic-output selections

Raybox exposes three programmable diagnostic outputs:

| Raybox output | QFN pin | Caravel pad | Selector LA bits |
|---|---:|---|---|
| `gpout[0]` | 14 | `mprj_io[35]` | `LA[12:9]` |
| `gpout[1]` | 15 | `mprj_io[36]` | `LA[16:13]` |
| `gpout[2]` | 16 | `mprj_io[37]` | `LA[20:17]` |

Each output has a four-bit selector. Selector values 2–15 have the same meaning for every `gpout`; values 0 and 1 are deliberately output-specific:

| Selector | `gpout[0]` | `gpout[1]` | `gpout[2]` | Notes |
|---:|---|---|---|---|
| 0 | `hblank` | `vblank` | `rbzero_reset` | Each output's primary signal |
| 1 | `hmax` | `vmax` | `i_clk` | Each output's alternate signal |
| 2 | `vinf` | `vinf` | `vinf` | Wall-tracer infinite-distance indication |
| 3 | `clk/4` | `clk/4` | `clk/4` | From a resettable two-bit divider |
| 4 | `hpos[0]` | `hpos[0]` | `hpos[0]` | Equivalent to a horizontal-position divide-by-two waveform |
| 5 | `hpos[1]` | `hpos[1]` | `hpos[1]` | Horizontal position bit 1 |
| 6 | `hpos[8]` | `hpos[8]` | `hpos[8]` | Horizontal position bit 8 |
| 7 | `hpos[9]` | `hpos[9]` | `hpos[9]` | Horizontal position bit 9 |
| 8 | `vpos[0]` | `vpos[0]` | `vpos[0]` | Vertical position bit 0 |
| 9 | `vpos[1]` | `vpos[1]` | `vpos[1]` | Vertical position bit 1 |
| 10 | `vpos[8]` | `vpos[8]` | `vpos[8]` | Vertical position bit 8 |
| 11 | `vpos[9]` | `vpos[9]` | `vpos[9]` | Vertical position bit 9 |
| 12 | `tex_oeb0` | `tex_oeb0` | `tex_oeb0` | Direction state for `tex_io0`: 0 = output enabled; 1 = input/high-impedance |
| 13 | `tex_in[0]` | `tex_in[0]` | `tex_in[0]` | Input-buffer value observed on `tex_io0` |
| 14 | `vec_csb` | `vec_csb` | `vec_csb` | View-vector SPI chip select |
| 15 | `reg_csb` | `reg_csb` | `reg_csb` | Register SPI chip select |

This table comes directly from the `gpout_mux` case statement in [`top_raybox_zero_fsm.v` lines 222–265](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/raybox-zero-fsm/src/rtl/top_raybox_zero_fsm.v#L222-L265). The output-specific primary/alternate connections are at [lines 135–169](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/raybox-zero-fsm/src/rtl/top_raybox_zero_fsm.v#L135-L169).

### Exposing the `tex_io0` direction state

Yes: select value **12** on any `gpout`. The signal is the actual `o_tex_oeb0` sent to the mux to control `mprj_io[18]`/QFN pin 55:

- Low means Raybox is enabling its output driver on `tex_io0`.
- High means the output driver is disabled and the pad is acting as an input.

For the closest possible real-time observation, use **`gpout[2]` on QFN pin 16**. `gpout[2]` is always unregistered, specifically to permit direct access to clock and reset-like signals. `gpout[0]` and `gpout[1]` follow the `reg_outs_enb` choice: when QFN pin 8 is low they are registered with a one-Raybox-clock delay; when it is high they are raw combinational outputs. See [`top_raybox_zero_fsm.v` lines 97–129](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/raybox-zero-fsm/src/rtl/top_raybox_zero_fsm.v#L97-L129).

Selector 13 is also useful alongside selector 12: it exposes the input-buffer reading of `tex_io0`. For example, `gpout[2]=tex_oeb0` and `gpout[1]=tex_in[0]` allow a logic analyser to correlate direction changes with the level actually present on the bidirectional pad.

### Programming the selectors from firmware

`user_project_wrapper` passes `LA[23:8]` into the selected design. Within Raybox:

```text
LA[8]      unused
LA[12:9]   gpout[0] selector
LA[16:13]  gpout[1] selector
LA[20:17]  gpout[2] selector
LA[23:21]  unused by these selectors
```

All three selectors therefore live in the management firmware's low LA output word, `LA0_CPU_OUT`. A safe masked update is:

```c
#define GPOUT_SEL_MASK  0x001FFE00u
#define GPOUT0_SEL(x)   (((uint32_t)(x) & 0xFu) << 9)
#define GPOUT1_SEL(x)   (((uint32_t)(x) & 0xFu) << 13)
#define GPOUT2_SEL(x)   (((uint32_t)(x) & 0xFu) << 17)

uint32_t la0 = LA0_CPU_OUT;
la0 &= ~GPOUT_SEL_MASK;
la0 |= GPOUT0_SEL(3)     // gpout[0] = clk/4
     | GPOUT1_SEL(13)    // gpout[1] = tex_io0 input-buffer value
     | GPOUT2_SEL(12);   // gpout[2] = tex_io0 OEb/direction
LA0_CPU_OUT = la0;
```

Before doing this, firmware must configure the corresponding LA bank as management-SoC outputs/user-project inputs, as the supplied test firmware already does. Unlike the design-selection controls in `LA[63:48]`, the `gpout` selectors do **not** use `mux_conf_clk`.

In the taped project configuration, the selectors are used directly. The wrapper contains an optional `REG_LA_INS` build path that would synchronize selector changes through two flip-flops, but that define is not enabled in the examined project configuration. If a derivative build enables it, allow two Raybox clocks after changing a selector before relying on the output.

The existing example chooses selectors 3, 4 and 1 respectively—`gpout[0]=clk/4`, `gpout[1]=hpos[0]`, and `gpout[2]=i_clk`—with the packed assignment shown in [`trzf_test.c` lines 161–170](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/firmware/trzf_test/trzf_test.c#L161-L170).

### Unused and management-overlaid GPIOs

Raybox design 0 does not use `mprj_io[7:0]` as normal design outputs, and `user_project_wrapper` deliberately leaves `io_out[7:0]` disconnected. Some of these pads nevertheless have Caravel management functions:

- `mprj_io[0]`: JTAG/debug
- `mprj_io[1:4]`: management SPI/debug signals
- `mprj_io[5]`: management UART RX or `opt_user_reset`
- `mprj_io[6]`: management UART TX
- `mprj_io[7]`: management IRQ input

These are not all “no-connect” pads from a board perspective. A bring-up/programming header may need some of them, and attached circuitry must not contend with management functions during reset or boot.

## Management flash and pin conflicts

The Caravel version needs an external management SPI flash containing the startup firmware. The dedicated QFN pins are:

| QFN pin | Function |
|---:|---|
| 24 | `flash_csb` |
| 25 | `flash_clk` |
| 26 | `flash_io0` |
| 27 | `flash_io1` |

### Reprogramming the management flash through `mprj_io[4:1]`

Caravel's housekeeping SPI slave provides an external-programmer path to the management firmware flash. This is a bridge through Caravel, not a second direct electrical connection to the flash. An external MCU, USB-to-SPI adapter or other SPI master connects to `mprj_io[4:1]`; after receiving the management-flash pass-through command, Caravel forwards SPI traffic to the dedicated flash pins 24–27.

| External programmer signal | QFN pin | Caravel pad | Housekeeping function |
|---|---:|---|---|
| MISO (input to programmer) | 32 | `mprj_io[1]` | `SDO`; returns `flash_io1` during pass-through |
| MOSI (output from programmer) | 33 | `mprj_io[2]` | `SDI`; forwarded to `flash_io0` |
| CS_N | 34 | `mprj_io[3]` | Housekeeping `CSB`; controls the pass-through transaction and flash select |
| SCK | 35 | `mprj_io[4]` | Housekeeping `SCK`; forwarded to `flash_clk` |
| Reset control | 21 | `RESETb` | Recommended programmer-controlled reset for safe ownership of the overlaid pads |

The management-flash pass-through transaction is:

1. Assert housekeeping `CSB` low on QFN pin 34.
2. Send `0xC4`, MSB first. This is the housekeeping command for management-flash pass-through.
3. Without raising `CSB`, send the normal SPI-flash command, address and data bytes. For a read, sample returned flash data on `mprj_io[1]`.
4. Raise `CSB` to deselect the flash and leave pass-through mode.
5. Repeat the `0xC4` prefix for every separate flash transaction—for example write-enable, sector erase, page program, status polling and verification reads.

The flash does **not** see the `0xC4` byte. The housekeeping state machine recognizes that byte first, asserts the flash chip select after the command has been decoded, and then connects the remaining serial stream to the flash. Pass-through also asserts the management-core reset, preventing the processor from executing from or contending for the flash while the transaction is active.

For a robust programming session, hold package `RESETb` low before driving `mprj_io[4:1]`, keep it low across all erase/program/verify transactions, and release the programmer's SPI outputs to high impedance before releasing reset. The pass-through logic itself resets the management core once `0xC4` is recognized, but the external reset additionally preserves the power-up housekeeping ownership of these management-overlaid pads and prevents already-running firmware from reconfiguring them. Share ground, use I/O levels compatible with the Caravel pad supply, and never allow the MCU and another adapter to drive the same signals simultaneously.

Thus, a system MCU can reprogram Caravel's firmware ROM in-circuit if it implements both the `0xC4` wrapper protocol and the selected SPI flash's ordinary erase/program/read command set. A practical PCB should route pins 32–35 and pin 21 to that MCU or to an isolated programming header; pins 24–27 remain connected normally between Caravel and the flash.

The `caravel-5V-dev-v6-M.2` board demonstrates the same architecture with an FT232H: host-side Python communicates with the FTDI device over USB, the FTDI acts as the housekeeping-SPI master and reset/GPIO controller, and Caravel bridges the programming traffic to the W25Q32 management flash. Efabless' `caravel_hkflash.py` utility is therefore a useful executable reference for an MCU implementation; its flash operations prepend the Caravel pass-through byte before the ordinary flash command.

Do not confuse this management-flash path with the separate legacy user-flash pass-through command (`0xC2`) and its `mprj_io[11:8]` wiring. Raybox Zero does not need that second flash path for Caravel firmware programming.

This GF180 Caravel version uses **ordinary single-bit, four-wire SPI** for its management flash: chip select, clock, IO0/MOSI and IO1/MISO. It does not provide a working dual- or quad-data management-flash mode. Although the inherited Caravel RTL still contains legacy `qspi_enabled`, `flash_io2` and `flash_io3` plumbing associated with `mprj_io[36:37]`, those hooks are a carry-over from an older Caravel version and must not be treated as a supported feature of this chip.

The [`caravel-5V-dev-v6-M.2` reference schematic](https://github.com/efabless/caravel_board/blob/2812cfd3896e2b1004b5f4559e0601c90cd18f55/hardware/development/caravel-dev-gf180-v6-M.2/caravel-5V-dev-v6-M.2.kicad_sch) reflects the implemented four-wire flash connection. Therefore QFN pins 15 and 16 are available as Raybox `gpout[1]` and `gpout[2]` after the normal GPIO transfer; a PCB should **not** connect them to management-flash IO2/IO3 on the assumption that QSPI is usable.

Likewise, pin 36 cannot simultaneously be a management UART receiver and `opt_user_reset`.

## Power, ground, decoupling and package implementation

The QFN64 package is `QFN-64-1EP, 9 mm × 9 mm, 0.5 mm pitch`, with a 7.65 mm × 7.65 mm exposed pad. The exposed pad is pin 65 and is tied to ground on the Efabless reference board.

The package exposes separate management, user-area and I/O supply names. The QFN symbol has nine positive-supply pins:

| Pins | Rail names |
|---|---|
| 17, 64 | `vddio` |
| 18 | `vccd` |
| 30 | `vdda` |
| 40, 47 | `vdda1` |
| 49 | `vccd1` |
| 9 | `vdda2` |
| 63 | `vccd2` |

Ground pins include 1, 10, 20, 23, 29, 38, 39, 52 and 56, plus exposed pad 65. The reference board BOM contains nine 0.1 µF capacitors, corresponding naturally to local decoupling of the nine positive-supply pins.

Hardware recommendations:

- Connect every required supply and ground pin; do not assume similarly named rails are internally interchangeable.
- Place a 0.1 µF ceramic capacitor close to each positive-supply pin, using short return paths to the corresponding ground plane.
- Bond exposed pad 65 solidly to ground with an appropriate paste pattern and thermal/ground vias.
- Use planes or low-impedance pours for the user-area supplies and VGA-output return currents.
- Confirm the required rail voltages against the final packaged-silicon documentation. Caravel RTL/testbench comments distinguish 3.3 V pad/analog rails and 1.8 V core rails, while some generic top-level comments refer to a 5 V padframe supply. The QFN schematic exposes the named rails separately, so the PCB must not infer supply voltage solely from a generic RTL port comment.
- Sequence or supervise the rails as required by the final Caravel electrical specification; hold `RESETb` asserted/low until the required rails and external clock are valid, then release it high.

## Aligning the Caravel board with the wafer.space 1×0.5 ASIC

The two ASICs implement related Raybox logic, but they are not pin-compatible and do not have identical system contracts.

| Function | Wafer.space 1×0.5 ASIC | Caravel design 0 | Compatibility action |
|---|---|---|---|
| Boot | Dedicated logic is available once clock/reset are valid | Requires management flash and firmware initialization | Add flash, programming access and a boot/ready indication |
| Main clock | Direct Raybox `CLK` pad | QFN pin 22 enters Caravel clock control, then reaches Raybox as `wb_clk_i` | Make firmware establish the desired frequency before releasing design reset |
| Main reset | Direct active-low `RESET_N` | Pin 21 resets Caravel; direct Raybox effect is policy-dependent | Use firmware-assisted reset, or add a deliberate reset policy/inverter for pin 36 |
| Optional user reset | Not needed for the direct standalone reset | Pin 36 can be active-high `opt_user_reset` after mux configuration | Add pull-down and polarity conversion if sharing an active-low board reset |
| VGA | RGB222 plus active-low H/V sync | Same logical RGB222 and sync outputs, on different physical pins | Route by logical colour/bit names, not bus-number assumptions |
| Texture memory | Texture PMOD type 1 wiring includes `TM1QSPI_*` and `GEN_TEXb` | `tex_cs_n`, `tex_sclk`, `tex_io[3:0]`; generated texture selected by `mode2_gen_tex` (`mode[2]`) | `mode2_gen_tex` is active-high; invert a common `GEN_TEXb` control |
| Control interfaces | `CTRL_SPI_*` and other dedicated mode/debug inputs | Separate `vec_*` and `reg_*` three-wire SPI inputs plus mode/debug pins | Use an adapter/controller mapping; they are not a one-for-one pin rename |
| Diagnostics | Many direct internal-position/timing outputs | Three firmware-selectable `gpout` pins | Choose useful `gpout` sources in firmware |
| Pad direction | Fixed by standalone pad ring and design | Caravel pad ownership and direction must be transferred by firmware | Keep external drivers benign until the ready indication |

### A practical common-board strategy

A PCB intended to support either ASIC version should use a logical interface between the ASIC section and the rest of the board:

- `rb_clk`
- `rb_reset_n`
- `rb_ready`
- RGB222, `hsync_n`, `vsync_n`
- texture QSPI signals
- control/register interface signals
- mode/debug straps

Then use variant-specific wiring:

- **Wafer.space build:** `rb_clk` and `rb_reset_n` connect directly to the die pads.
- **Caravel build:** `rb_clk` drives pin 22; `rb_reset_n` drives pin 21 and, if fast direct user reset is required after boot, an inverter can drive pin 36. `rb_ready` comes from firmware or a selected `gpout`.
- Invert the common active-low `GEN_TEXb` signal for Caravel `mode2_gen_tex` (`mode[2]`), because Caravel uses active-high `gen_tex`.
- Keep the external video and texture-memory connectors logically identical even though the package pin numbers differ.
- Use a small MCU, CPLD, or variant-specific resistor/logic population to translate the different control-SPI and reset conventions.

The common system controller should wait for `rb_ready` before driving configuration traffic or assuming valid video. This prevents the rest of the PCB from interpreting the safe-input and boot-transition states as a working Raybox interface.

## Recommended PCB provisions

At minimum, a Caravel Raybox board should include:

- Correct 1.8 V and I/O/analog supply generation for every required rail, confirmed against the packaged-part specification.
- Local decoupling at every positive-supply pin and a solid exposed-pad ground connection.
- A CMOS oscillator or clock-driver connection to pin 22.
- External SPI flash on pins 24–27 with programming access.
- An in-circuit firmware programming path from an MCU or isolated header to pins 32–35, plus control of `RESETb` on pin 21.
- A defined reset network on pin 21 and an accessible reset/test point.
- A pull-down and test point on pin 36 if `opt_user_reset` is to be supported.
- Defined pulls or controller-driven states on Raybox input pins so they do not float during boot.
- A management/programming/debug header for the required Caravel management pins.
- A visible or machine-readable firmware-ready signal.
- Optional series resistors or routing provisions on high-activity VGA, texture-clock and system-clock signals for signal-integrity tuning.
- Isolation/jumpers for any pad that can be driven both by a management function and by external circuitry.

## Bring-up checklist

1. Verify every supply rail independently before fitting or releasing the ASIC.
2. Check that pin 22 has a clean clock and that pin 21 reaches valid low/high levels.
3. With `RESETb` held low, verify the programmer can read the flash JEDEC ID through the housekeeping `0xC4` pass-through path; then verify erase, program and read-back on a non-critical image or test device.
4. Release the programmer's SPI outputs to high impedance, release `RESETb`, and confirm the management flash is readable by Caravel and that firmware begins execution.
5. Observe the dedicated Caravel `gpio` pulse used by the example firmware as an early boot indication.
6. Verify the firmware loads design selection 0 with two mux-clock pulses.
7. Verify `reg_mprj_xfer` completes.
8. Confirm the explicit design-0 reset pulse occurs after pad transfer.
9. Check a diagnostic `gpout` clock before attaching the VGA or texture-memory subsystem.
10. Confirm RGB, sync and texture-pin directions at the package before fitting external memories or low-impedance loads.
11. Test pin 21 and pin 36 separately; they are intentionally different reset paths.
12. Reset Caravel repeatedly and confirm firmware always restores the same mux and pad state.
13. Test cold power-up as well as warm reset, because the mux policy registers are not reset by `RESETb`.

## Common failure modes

- **No video after power-up:** firmware has not booted, design 0 is not selected, GPIO transfer has not completed, or design 0 has not received a reset pulse.
- **Programmer cannot identify the flash:** it is sending raw flash commands directly to `mprj_io[4:1]` instead of prefixing each CS-low transaction with housekeeping command `0xC4`, or the SPI signal directions are reversed.
- **Programming is intermittent or corrupts housekeeping traffic:** `RESETb` was not held low, the programmer did not release its outputs before boot, or two masters are contending for the management-overlaid pads.
- **Video starts only after a second reset:** firmware/reset ordering is relying on stale mux or design state.
- **Package reset does not reset Raybox immediately:** `wb_rst_i` propagation was disabled, as it is in the supplied test firmware.
- **Pin 36 appears ineffective:** IO5 reset propagation was not enabled and clocked into the mux, the pad is not in user-input mode, or the input polarity is wrong.
- **Pin 36 breaks serial diagnostics:** the board is trying to use `ser_rx` and `opt_user_reset` simultaneously.
- **Missing `gpout[1:2]` or unexpected loading:** the PCB was designed around the obsolete Caravel IO2/IO3/QSPI hooks and connected `mprj_io[36:37]` to flash pins. This GF180 version's management flash is four-wire SPI only; reserve those pads for Raybox or other intended user-project functions.
- **Unexpected activity when switching designs:** auto-reset is disabled, and unselected designs continue running internally.
- **Inputs behave randomly:** the GPIOs and external straps have no pulls; the project's startup configuration explicitly uses no-pull inputs.
- **Standalone and Caravel variants select opposite texture modes:** wafer.space uses `GEN_TEXb`, while Caravel uses active-high `mode2_gen_tex` (`mode[2] = gen_tex`).

## Primary source files

- [Multi-project `user_project_wrapper.v`](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/user_project_wrapper.v)
- [Multi-project `top_design_mux.v`](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/mux/top_design_mux.v)
- [Raybox startup firmware `trzf_test.c`](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/firmware/trzf_test/trzf_test.c)
- [Project-specific `user_defines.v`](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/user_defines.v)
- [Raybox wrapper `top_raybox_zero_fsm.v`](https://github.com/algofoogle/algofoogle-multi-caravel/blob/9871f786967d514317c7a2e1e2b2107cce685c2d/verilog/rtl/raybox-zero-fsm/src/rtl/top_raybox_zero_fsm.v)
- [Caravel reset/clock logic](https://github.com/efabless/caravel-gf180mcu/blob/2b51db499eb77d4dea77789f0ec97326ecb912c6/verilog/rtl/caravel_clocking.v)
- [Caravel management protection/user reset path](https://github.com/efabless/caravel-gf180mcu/blob/2b51db499eb77d4dea77789f0ec97326ecb912c6/verilog/rtl/mgmt_protect.v)
- [Caravel housekeeping-SPI command decoder and pass-through state machine](https://github.com/efabless/caravel-gf180mcu/blob/2b51db499eb77d4dea77789f0ec97326ecb912c6/verilog/rtl/housekeeping_spi.v)
- [Caravel housekeeping management-flash signal bridge](https://github.com/efabless/caravel-gf180mcu/blob/2b51db499eb77d4dea77789f0ec97326ecb912c6/verilog/rtl/housekeeping.v)
- [Efabless `caravel_hkflash.py` host programmer](https://github.com/efabless/caravel_board/blob/2812cfd3896e2b1004b5f4559e0601c90cd18f55/firmware/chipignite/util/caravel_hkflash.py)
- [Caravel QFN64 reference schematic](https://github.com/efabless/caravel_board/blob/2812cfd3896e2b1004b5f4559e0601c90cd18f55/hardware/breakout/caravel-M.2-card-QFN/caravel-M.2-card-QFN.kicad_sch)
- [Caravel GF180 5 V development-board schematic](https://github.com/efabless/caravel_board/blob/2812cfd3896e2b1004b5f4559e0601c90cd18f55/hardware/development/caravel-dev-gf180-v6-M.2/caravel-5V-dev-v6-M.2.kicad_sch)
- [Wafer.space 1×0.5 slot definition](https://github.com/algofoogle/gf180ws2-raybox-zero/blob/main/librelane/slots/slot_1x0p5.yaml)

