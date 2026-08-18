# Module 2 — COPERT emission-factor methodology

Written 2026-08-18 as part of the Module 2 (emission intelligence) pass. Resolves
`docs/KNOWN_ISSUES.md` section 1 ("Three of the four COPERT factor CSVs are not safely
auto-parseable").

## Resolution: RESOLVED, not WONTFIX

All four `COPERT_2025_*.csv` exports in `module2_emission/factors/` are now parsed for real,
including PM2.5. `copert_emission_engine.py`'s `_parse_copert_pivot_table()` reads them
correctly, and `get_factor()` applies a unit-sanity check before trusting any parsed value.

## What the raw files actually are

All four files share one layout: a 5-column, headerless spreadsheet **pivot export**. Row 0 is
a junk label (`,,,,Total Total`), not data. Example (`COPERT_2025_CO2_EF.csv`):

```
 1  ,,,,Total Total
 2  Passenger Cars,Petrol,Mini,Euro 6 a/b/c,135.5194
 3  ,,Small,Euro 6 a/b/c,168.372
 4  ,,Medium,Euro 6 a/b/c,194.4926
 5  ,Petrol Total,,,149.1856
 6  ,Petrol Hybrid,Medium,Euro 6 a/b/c,0
 7  ,Diesel,Mini,Euro 6 a/b/c,0
 8  ,,Small,Euro 6 a/b/c,164.3489
 9  ,,Medium,Euro 6 a/b/c,176.2566
10  ,Diesel Total,,,170.3027
...
17  Passenger Cars Total,,,,151.7609
18  Heavy Duty Trucks,Diesel,Rigid >32 t,Euro VI D/E,"1,123.5121"
19  ,CNG,Rigid >12 t,Euro VI D/E,695.3415
20  Heavy Duty Trucks Total,,,,909.4268
21  Buses,Diesel,Urban Buses Standard 15 - 18 t,Euro VI A/B/C,924.2413
...
```

- **Column 0**: the top-level vehicle category (`Passenger Cars`, `L-Category`, `Buses`,
  `Heavy Duty Trucks`), forward-filled: blank on every row that continues the category above it.
- **Column 1**: a fuel type (`Petrol`, `Diesel`, `CNG`, ...), a `"<Fuel> Total"` subtotal label,
  or blank on a further segment-detail sub-row of the same fuel.
- **Column 2**: an engine-size/vehicle-segment label, or blank on a subtotal row.
- **Column 3**: emission standard (e.g. `Euro 6 a/b/c`).
- **Column 4**: the g/km value. Occasionally thousands-comma-formatted inside quotes (e.g.
  `"1,123.5121"`).

There is no single "the" factor per category in this file — it reports one line per
`(category, fuel, segment)` combination, plus fuel-level and category-level subtotal rows.
Picking a representative number requires choosing which row.

## The previous PM2.5 bug, and why it wasn't a "file is unusable" problem

The old loader looked for *any* column literally named `Total` and matched it against a
category substring — a heuristic built for a normal wide table, not a pivot export. Against
this file's structure, that heuristic grabbed a "Total Total" tonnes-for-a-reference-scenario
aggregate rather than a proper g/km row, producing PM2.5 values ~338x too high (5.25 vs the
correct 0.0155 g/km for Passenger Cars/Petrol). CO2/NOx/CO simply found no column named
"category" at all (there isn't one) and fell back safely, never triggering the same bug. The
file's structure was always correctly parseable — pivot-table-aware, not a normal
column-matching problem.

## The fuel-mix assumption that resolves it

`FALLBACK_FACTORS` (the constants used everywhere before this pass) were originally
hand-transcribed from this same PDF/spreadsheet source using one consistent, undocumented rule.
Reverse-engineering that rule and re-implementing it as code (`FUEL_SELECTOR_BY_CATEGORY` in
`configs/project_config.yaml`, under `copert_fuel_mix_assumption`) recovers **every one of the
16 `FALLBACK_FACTORS` values bit-for-bit** directly from the raw CSVs:

| Category | Row selected | Why |
|---|---|---|
| Passenger Cars | `"Petrol Total"` (col 1) | Assumes the light-duty car fleet is predominantly petrol-fuelled — realistic for urban India, where diesel passenger cars are a minority and petrol is the default. |
| L-Category (motorcycle) | `"Petrol Total"` (col 1) | Same assumption; two/three-wheelers in this fleet are overwhelmingly petrol. |
| Heavy Duty Trucks | `"Diesel"` (col 1, the single leaf row under this category — there is no "Diesel Total" subtotal for HDVs in this table, just one diesel technology row) | Assumes the heavy truck fleet is predominantly diesel-fuelled — the near-universal standard for freight trucks in India and most of the world. |
| Buses | `"Diesel"` (col 1, same single-leaf-row situation) | Same assumption; the reference "Urban Buses Standard" diesel technology is the dominant bus type in this context, versus the CNG rows also present in the table. |

This is a **scenario assumption, not a measurement** — exactly like `ROAD_WIDTH_M`/
`ROAD_LENGTH_M` in Module 1. It was already implicit in `FALLBACK_FACTORS`; this pass makes it
explicit, documented, and re-derivable from source instead of a set of opaque hardcoded numbers.
If the real regional fleet composition is known to differ (e.g. a meaningful diesel car
fraction, or CNG buses being the majority in a specific city), the fix is to change
`copert_fuel_mix_assumption` in `configs/project_config.yaml` to point at a different column-1
label — no code change needed.

## Unit sanity check

`get_factor()` now compares every parsed value against `FALLBACK_FACTORS[category][pollutant]`
and rejects it (falls back to the constant, logs a `WARNING`) if the ratio exceeds
`copert_factor_sanity_check_max_ratio` (3.0, in `configs/project_config.yaml`) in either
direction. This is precisely the check that would have caught the PM2.5 ~338x bug on its very
first record — 338 is nowhere near [1/3, 3]. Since the current tables parse to an exact match
of the fallback constants, this check currently never fires in practice; it exists as a guard
rail against a future factor-table update introducing a new row-selection or unit error
silently.

## Category mapping (unchanged, restated for completeness)

`car → PASSENGER_CAR → Passenger Cars`, `motorcycle → MOTORCYCLE → L-Category`,
`bus → BUS → Buses`, `truck → HEAVY_DUTY_TRUCK → Heavy Duty Trucks` — these four classes
receive quantitative CO2/NOx/CO/PM2.5.

**autorickshaw** is excluded from quantitative COPERT: COPERT's standard vehicle categories
(passenger car, L-category two/three-wheeler in the *motorcycle* sense, bus, heavy truck) have
no clean three-wheeler equivalent — an auto-rickshaw's engine, weight, and emissions profile
sit between a motorcycle and a passenger car and mapping it to either would misrepresent it
rather than approximate it defensibly. Rather than force a wrong mapping, autorickshaw tracks
are detected, tracked, and counted (they still affect density/occupancy/flow features) but
excluded from the emissions total until a real three-wheeler COPERT factor is sourced.

**bicycle** is excluded from tailpipe emissions entirely, by physical definition — a bicycle has
no engine and no tailpipe emissions to model. It is still counted for density/occupancy/flow.

## What changed vs. what stayed the same

- **Numeric emission values: unchanged.** Because the parsed factors match `FALLBACK_FACTORS`
  exactly, `outputs/copert_emissions/vehicle_emissions.csv`'s `CO2_g`/`NOx_g`/`CO_g`/`PM25_g`
  columns are byte-identical to before this change, for all 1,075 included vehicle tracks.
- **Provenance: changed, honestly.** Every record's `*_source` column now reads
  `COPERT_FACTOR_TABLE` instead of `FALLBACK_SCENARIO_FACTOR` — the numbers were always the
  correct, documented values, but they are now genuinely read from the vendor-provided tables
  each run instead of hardcoded, so a future table update (e.g. Euro 7 factors) will actually
  take effect without a code change.
- **PM2.5 auto-loading: re-enabled.** `FACTOR_FILENAMES["PM25"]` now points at the real file
  again, protected by the sanity check described above.

See `docs/baseline_checksums.txt` for the updated, current authoritative checksum of
`vehicle_emissions.csv` and a full explanation of what changed (the `*_source` columns) and
what didn't (every numeric column) -- that file's inline comments are the regression-diff
investigation for this pass.
