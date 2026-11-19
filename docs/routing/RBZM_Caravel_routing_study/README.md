# RBZM–Caravel physical connection study

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
| 0° | 136 | 119 | 133 | 122 |
| 45° | 51 | 61 | 50 | 48 |
| 90° | 32 | 83 | 36 | 85 |

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
