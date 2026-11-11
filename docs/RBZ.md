# General raybox-zero gf180ws2 documentation

The chip that was taped out went into two half-height slots on wafer.space Run #2, and has the ID `AMM1`.

The standard half-height pin defs list ([`src/slot_defines.svh`](https://github.com/algofoogle/gf180ws2-raybox-zero/blob/f5bbcef7564e779d1411a5593c4e2da3161077a7/src/slot_defines.svh#L33-L45)) is:

```verilog
`ifdef SLOT_1X0P5

// Power/ground pads for core and I/O
`define NUM_DVDD_PADS 7
`define NUM_DVSS_PADS 7

`define NUM_VDD_PADS 1
`define NUM_VSS_PADS 1

// Signal pads
`define NUM_INPUT_PADS 4
`define NUM_BIDIR_PADS 46
`define NUM_ANALOG_PADS 4
```

The padring generator script [`scripts/padring.py`](https://github.com/algofoogle/gf180ws2-raybox-zero/blob/main/scripts/padring.py) generates the actual padring, but using what source? [Makefile has a librelane-padring target](https://github.com/algofoogle/gf180ws2-raybox-zero/blob/f5bbcef7564e779d1411a5593c4e2da3161077a7/Makefile#L121-L123) which uses [`LIBRELANE_CONFIGS`](https://github.com/algofoogle/gf180ws2-raybox-zero/blob/f5bbcef7564e779d1411a5593c4e2da3161077a7/Makefile#L64) referencing [`librelane/slots/slot_1x0p5.yaml`](https://github.com/algofoogle/gf180ws2-raybox-zero/blob/main/librelane/slots/slot_1x0p5.yaml)

## TT pinout

| TT pin | Direction | Function |
|---|---:|---|
| `ui_in[0]` | in | control SPI SCK |
| `ui_in[1]` | in | control SPI MOSI |
| `ui_in[2]` | in | control SPI `/CS` |
| `ui_in[3]` | in | enable map/vector/tracer debug overlays |
| `ui_in[4]` | in | demo: decrement player X each frame |
| `ui_in[5]` | in | demo: decrement player Y each frame |
| `ui_in[6]` | in | select registered VGA outputs |
| `ui_in[7]` | in | texture-PMOD selection in the current wrapper |
| `uo_out[0]` | out | red[1] |
| `uo_out[1]` | out | green[1] |
| `uo_out[2]` | out | blue[1] |
| `uo_out[3]` | out | VSYNC, active low |
| `uo_out[4]` | out | red[0] |
| `uo_out[5]` | out | green[0] |
| `uo_out[6]` | out | blue[0] |
| `uo_out[7]` | out | HSYNC, active low |

TBC: uio pins for texture ROM.

Comments from TT `info.yaml` describing pins:

```verilog
// pinout:
//   # Inputs
//   ui[0]: spi_sck
//   ui[1]: spi_sdi  # aka MOSI
//   ui[2]: spi_csb  # aka ss_n
//   ui[3]: debug    # Show debug overlays on screen?
//   ui[4]: inc_px   # Increment px
//   ui[5]: inc_py   # Increment py
//   ui[6]: reg      # Present registered or unregistered outputs?
//   ui[7]: tex_pmod_type
//   #NOTE: For texture_pmod_type:
//   # 0=Moser's QSPI PMOD;
//   #   In this mode, it's assumed gen_texb is not used, i.e. we're always using
//   #   QSPI textures when tex_pmod_type==0. This eliminates the need for an external
//   #   pull-up resistor; if it weren't for this, then:
//   #     The PMOD should have a weak pull-up applied to uio[5] (its io3 pin).
//   #     This would ensure gen_texb is DISABLED during the times when it would otherwise float.
//   #     Besides that, the memory should be written with io3==1 in the whole ROM so that any
//   #     read doesn't override the weak pull-up and activate gen_texb mode.
//   #     NOTE: Looks like there are jumpers to enable/disable the chips (must cut traces first)...?
//   # 1=Digilent SPI PMOD;
//   #   Expect uio[5] (RSTb) is weakly pulled up, but can be pulled low for GEN_TEXb instead.

//   # Outputs: Tiny VGA PMOD (https://tinytapeout.com/specs/pinouts/#vga-output)
//   uo[0]: red[1]
//   uo[1]: green[1]
//   uo[2]: blue[1]
//   uo[3]: vsync_n
//   uo[4]: red[0]
//   uo[5]: green[0]
//   uo[6]: blue[0]
//   uo[7]: hsync_n

//   # Bidirectional pins
//   #NOTE: The following are compatible with https://digilent.com/reference/pmod/pmodsf3/start
//   # and https://github.com/mole99/qspi-pmod (depending on which is selected by tex_pmod_type).
//   ######## type=1                    type=0                          
//   uio[0]: 'Out: digilent_tex_csb   / Out: moser_tex_csb'                         
//   uio[1]: 'I/O: digilent_tex_io0   / I/O: moser_tex_io0'                         
//   uio[2]: 'In:  digilent_tex_io1   / In:  moser_tex_io1'                         
//   uio[3]: 'Out: digilent_tex_sclk  / Out: moser_tex_sclk'                            
//   uio[4]: 'In:  SPARE              / In:  moser_tex_io2'                         
//   uio[5]: 'In:  gen_texb           / In:  moser_tex_io3'     # aka GEN_TEXb, aka use_texture_spi (when high) -- ignored when tex_pmod_type==0.
//   uio[6]: 'In:  digilent_tex_io2   / N/A: moser_CS1'         # With type==0 it outputs 1 (to disable RAM A).
//   uio[7]: 'In:  digilent_tex_io3   / N/A: moser_CS2'         # With type==0 it outputs 1 (to disable RAM B). NOTE: Otherwise unused for type==1, or MAYBE SPARE
```


## Accepted ws2 commits

* Source commit [`4ab47b1`](https://github.com/algofoogle/gf180ws2-raybox-zero/commit/4ab47b127e13168154c6a2377443e4dacbca3eca)
* [GDS & PNL for that commit](https://github.com/algofoogle/gf180ws2-raybox-zero/commit/72ec06dea71aa0373dc15cb39962037fa5a7edc5)
* [Fix for GL sim with texture ROM](https://github.com/algofoogle/gf180ws2-raybox-zero/commit/5b0d3ad6109dbe7b4aa806c9fdeb267eecccb281)


## ws2 pinout

| `bidir_PAD` | Dir. | Function |
|---:|---:|---|
| 0 | in | control SPI SCK |
| 1 | in | control SPI MOSI |
| 2 | in | control SPI `/CS` |
| 3 | in | enable all compiled debug overlays |
| 4 | in | demo decrement X |
| 5 | in | demo decrement Y |
| 6 | in | 1 selects one-clock-registered VGA outputs |
| 7 | in | texture connector: 0 Moser QSPI PMOD, 1 Digilent Pmod SF3 |
| 8..15 | mixed | texture-flash interface, detailed below |
| 16 | out | red[1] |
| 17 | out | green[1] |
| 18 | out | blue[1] |
| 19 | out | VSYNC_N |
| 20 | out | red[0] |
| 21 | out | green[0] |
| 22 | out | blue[0] |
| 23 | out | HSYNC_N |
| 24 | out | horizontal blanking |
| 25 | out | vertical blanking |
| 26 | out | one-clock `hpos==799` strobe |
| 27 | out | one-line `vpos==524` indication at each line end |
| 28..37 | out | `vpos[9:0]` |
| 38..39 | in | unused; no internal pulls |

See [`src/chip_core.sv`](https://github.com/algofoogle/gf180ws2-raybox-zero/blob/f5bbcef7564e779d1411a5593c4e2da3161077a7/src/chip_core.sv#L55-L91) and note that for the productised version of RBZ that `tex_pmod_type=1` is preferred so we expose `gen_texb` too:

```verilog
// Pin mapping:
// Reserved:
//      clk
//      rst_n
// bidir_in:
//  0   spi_clk
//  1   spi_sdi
//  2   spi_csb
//  3   debug
//  4   inc_px
//  5   inc_py
//  6   reg
//  7   tex_pmod_type:
/////// type=1 -------------------- type=0 ///////
//  8   OUT:    digilent_tex_csb    / Out: moser_tex_csb
//  9   I/O:    digilent_tex_io0    / I/O: moser_tex_io0
//  10  IN:     digilent_tex_io1    / moser_tex_io1
//  11  OUT:    digilent_tex_sclk  / Out: moser_tex_sclk
//  12  IN:     SPARE               / moser_tex_io2
//  13  IN:     gen_texb            / moser_tex_io3
//  14  IN:     digilent_tex_io2    / moser_CS1
//  15  IN:     digilent_tex_io3    / moser_CS2
// OUTPUTS:
//  16  red[1]
//  17  green[1]
//  18  blue[1]
//  19  vsync_n
//  20  red[0]
//  21  green[0]
//  22  blue[0]
//  23  hsync_n
// EXTRA OUTPUTS, for later:
//  24  hblank
//  25  vblank
//  26  hmax
//  27  vmax
//  37:28  vpos
```


## MISC

https://kicanvas.org/?repo=https%3A%2F%2Fgithub.com%2Fwafer-space%2Fchip-on-board-wire-bonded-pcbs%2Fblob%2Fmain%2Frun-2%2F1x0p5-cob%2Fmezzanine-1x0p5.kicad_sch

GPT says TXB0104 needs a drive strength of at least 2mA either end in order to work correctly. What is the hardened drive strength of the GFMPW1 & gf180ws2-rbz?

If TXB doesn't properly sense initial command write, it might be possible to make a one-way booster that operates on /CS falling edge.

In an extreme case, explicit direction control (LVC245) could work if tuned to land perfectly in the turn-around zone: We know exactly how many clocks it is from /CS falling to turn-around zone, so either use a counter (clocked by same system clock) or a passively timed circuit (even a 555).

APX803S-46SA-7 or MCP1319MT-29LE-OT as a power/reset supervisor.

RBZ may need its reset properly _syncronously_ clocked because otherwise a `rst_n` rising edge could occur on a clock edge & propagation (setup) delays would mean some parts come out of reset and start sequencing 1 clock before others do. Maybe a reset supervisor would help, or a 2xDFF external synchroniser, or MCU control over reset.



## RBZ improvements for ttsky26d (that will feed future full-chip versions)

* SPI regs for selecting gpouts: They can override 
* Fix SDC for FSM
* On-chip CORDIC?
* tnt's regfile for "stuff": 32x32 is 1024b = 128 bytes. Only 384 bits are needed for texture line (but might need 50MHz or 75MHz clock for reads); rest could be sprites?
* Video overlay memory region
* Framebuffer PSRAM test
* Instant-on SPI regs (don't double-buffer regs)
* Tri-state all pins during reset (especially Q/SPI), or SPI pass-through method so a host MCU can reprogram SPI chip easily
* Option to expose direction control
* Option to expose `visible` & control polarity
* Ensure proper io0 turn-around at the right time (if not already done), i.e. go Hi-Z when switching from command/address to data-in.
