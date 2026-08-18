# Known issues surfaced during Module 0 verification (2026-08-17)

## 1. RESOLVED -- COPERT factor CSVs are now genuinely parsed (was: "not safely auto-parseable")

Resolved 2026-08-18 in Module 2 Task A. See `docs/MODULE2_COPERT_METHODOLOGY.md` for the full
writeup; summary here.

All four `COPERT_2025_*.csv` files (`module2_emission/factors/`) turned out to share one
consistent, parseable structure: a 5-column, headerless spreadsheet **pivot export** (column 0 =
category, forward-filled; column 1 = fuel type or a `"<Fuel> Total"` subtotal label; column 4 =
the g/km value). The previous loader's "any column literally named Total" heuristic was built
for a normal wide table, not a pivot export, and on `COPERT_2025_PM2.5.csv` it grabbed a
tonnes-for-a-reference-scenario aggregate row instead of a proper g/km factor, producing values
~338x too high (5.25 vs the correct 0.0155 g/km for Passenger Cars/Petrol). That was a
row-selection bug, not evidence the file was unusable.

`copert_emission_engine.py`'s new `_parse_copert_pivot_table()` reads the real pivot structure
and selects one representative row per category using a documented fuel-mix assumption
(`copert_fuel_mix_assumption` in `configs/project_config.yaml`: `"Petrol Total"` for
Passenger Cars/L-Category, the single `"Diesel"` leaf row for Heavy Duty Trucks/Buses). This
rule reproduces **every one of the 16 `FALLBACK_FACTORS` values bit-for-bit** directly from the
raw CSVs -- strong evidence those constants were originally hand-derived from this exact file
using this exact rule. A `get_factor()` sanity check (`copert_factor_sanity_check_max_ratio:
3.0`) rejects any future parsed value that drifts more than 3x from the fallback in either
direction, guarding against a future table update introducing a new row-selection or unit bug
undetected -- the same kind of check that would have caught the PM2.5 bug on its first record.

**Current state:** all four pollutants (CO2, NOx, CO, and now PM2.5 too) are read from the real
tables and logged as `COPERT_FACTOR_TABLE`, not `FALLBACK_SCENARIO_FACTOR`. Because the parsed
values equal the fallback constants exactly, `outputs/copert_emissions/vehicle_emissions.csv`'s
numeric columns are unchanged from before this fix -- only the `*_source` provenance columns
changed (see `docs/baseline_checksums.txt`). "Defect 4a" is now fully closed.

## 2. RESOLVED -- the pre-restructure `vehicle_emissions.csv` duplicate-row mystery

Investigated 2026-08-17. The baseline file (1,192 rows, but only 1,101 unique
`(video_id, vehicle_id)` pairs) was not corrupted data -- it was produced by grouping
emission records in a way that double/triple-counted vehicles whose ByteTrack ID
flickered between classes for a frame or two.

Concrete proof: `video11` / ByteTrack ID `8` has 10 raw detection frames -- 8 labeled
`car`, 1 labeled `truck`, 1 labeled `bus` -- with cumulative distance climbing cleanly
from 0 to 0.001077 km across all 10 frames (one continuous, physically plausible track).
The baseline file has THREE separate emission rows for this one vehicle: one as car, one
as truck, one as bus, each carrying a fraction of the total distance. Roughly 87 of the
~1,200 tracks (~7%, a normal class-flicker rate) were split this way, turning 87 real
vehicles into 178 emission records.

The currently-checked-in `copert_emission_engine.py` already contains the fix, with an
explicit comment: "ByteTrack IDs may have an occasional class flicker, so choose the
dominant class within a track instead of splitting the same ID into emissions twice." It
groups strictly by `(video_id, vehicle_id)` and assigns the whole track to its majority
(`.mode()`) class. Someone fixed the code at some point without regenerating the output
CSV to match, so code and output silently drifted apart before this session started.

Module 0's verification re-run of `copert_emission_engine.py` against the
checksum-verified-unchanged input simply exercised the already-correct code and produced
the correct, deduplicated 1,075-row result. **This is a fix, not a regression** -- the
current `outputs/copert_emissions/vehicle_emissions.csv` is more accurate than the file it
replaced, independent of the separate factor-table issue in section 1 above.

