# Module 0 verification — real-environment Module 1 reproduction

Executed 2026-08-18, directly inside the project's real `venv`, closing the gap left by the
previous (sandboxed) session, which could not import `torch`/`ultralytics`/`cv2` at all.

## Environment

| Item | Value |
|---|---|
| Python interpreter | `venv/bin/python` (venv built from `/Users/vishal/anaconda3/bin/python3.11`) |
| Python version | 3.11.5 |
| numpy | 2.4.6 |
| pandas | 3.0.5 |
| opencv-python | 5.0.0.93 |
| torch | 2.13.0 |
| torchvision | 0.28.0 |
| ultralytics | 8.4.115 |
| supervision (ByteTrack) | 0.29.1 |
| lap | 0.5.13 |

## Model / tracker load

- `models/best.pt` loads via `ultralytics.YOLO('models/best.pt')` — **successful**.
- `model.names` = `{0: car, 1: motorcycle, 2: bus, 3: truck, 4: autorickshaw, 5: bicycle}` —
  **matches `configs/project_config.yaml`'s `vehicle_classes` exactly**, six-class mapping
  unchanged.
- `supervision.ByteTrack()` instantiates successfully (emits a harmless deprecation notice from
  `supervision` 0.29.1 about a future API change in 0.30.0; not acted on, out of scope — no
  project code was changed because of it).

## Entry point used

Per `docs/REPO_MAP.md`:
```
venv/bin/python -m module1_traffic.run_batch \
  --input-dir INDRA_data_for_emissions/videos_mp4 \
  --output-dir <output dir>
```
Run twice into a **separate** directory, `outputs/module1_indra_batch_RERUN/`, never into the
frozen `outputs/module1_indra_batch/` — the baseline was never overwritten.

## Videos processed

30/30 INDRA videos, all `1920x1080` @ `30.0` fps, `H1_1080P` calibration profile, all
`INCLUDED` (none excluded for recalibration or processing failure). Frame counts range 150–330
(total 5,790 frames across all 30 videos). Full per-video table in
`outputs/module1_indra_batch_RERUN/module1_manifest.csv`.

## Bug found and fixed

**First run (unmodified code) failed at the merge step**, after all 30 individual videos had
already processed successfully:
```
ValueError: dict contains fields not in fieldnames: 'distance_km', 'vehicle_total_distance_km'
  File "module1_traffic/run_batch.py", line 140, in main
    writer.writerows(merged_rows)
```

**Root cause:** `module1_traffic/run_module1.py`'s per-video emission-training CSV writer
(`emission_fields`, ~line 502) included `distance_km` and `vehicle_total_distance_km` — two
columns that are not part of the frozen 11-column schema documented in
`docs/MODULE1_CONTRACT.md` ("Per-video emission-training CSV") and not present in the baseline
`*_emission_training.csv` files. `run_batch.py`'s merge writer correctly uses the 11-column
contract schema, so it rejected the two extra fields.

**This predates the Module 0 restructure** — confirmed byte-identical against
`run_module1.py.bak` (the pre-restructure `main.py`, differing only in its import line). It is a
genuine latent defect that had simply never been exercised end-to-end before, because no prior
session had a working Python environment to actually run `run_batch.py` against real video.

**Why it's safe to fix, not just work around:** `module2_emission/data/processed/
enrich_module1_distances.py` (the canonical, documented distance calculation — REPO_MAP.md
"Lineage A") recomputes `distance_km` itself from `world_y_m` in the trajectory CSV; it never
reads `distance_km` from the emission-training CSV. The two extra columns in the emission CSV
were dead, duplicate data — removing them changes no calculation, no calibration value, no
mapping, and no COPERT factor.

**Fix applied:** removed `"distance_km", "vehicle_total_distance_km"` from `emission_fields` in
`module1_traffic/run_module1.py` (~line 502-505), restoring the exact contract-documented
11-column schema. One line changed; nothing else touched.

Reran the full 30-video batch after the fix: **30/30 videos completed, merge succeeded, exit
code 0.**

## Known, accepted (non-bug) schema note

The raw per-video **trajectory** CSV (`<video_id>_trajectory.csv`, and therefore its direct
descendant `outputs/module1_distance_enriched*/INDRA_COPERT_DATASET_WITH_DISTANCE.csv`) now
contains one column, `vehicle_total_distance_km`, that the frozen baseline file predates. This
*is* part of the documented `MODULE1_CONTRACT.md` trajectory-CSV schema (`... plus:
frame_number, image_x, image_y, distance_km ..., vehicle_total_distance_km, emission_eligible`)
— i.e. current code matches the contract; the old baseline file was generated before this
column existed and was never regenerated. It was **not** changed, because doing so would mean
discarding legitimately-computed, contract-documented data. It has no downstream effect: it is
not consumed by `build_copert_scenario_dataset.py`'s `REQUIRED_COLUMNS`, and the actual COPERT
input file (`INDRA_COPERT_INPUT.csv`) is confirmed identical to baseline (see below). Flagged
here for visibility, not treated as a defect.

## Baseline comparison

Compared regenerated `outputs/module1_indra_batch_RERUN/**` (and its downstream re-derivations)
against `docs/baseline_checksums.txt` and the untouched baseline files in place.

| File | Baseline SHA-256 | Regenerated SHA-256 | Byte-identical? | Content-identical (excl. `timestamp`)? |
|---|---|---|---|---|
| `outputs/module1_indra_batch/INDRA_COPERT_DATASET.csv` | `2aaeebb9...18ed4` | `30aac1d8...9656 3` | No | **Yes** — all 61,707 rows, all 11 columns except `timestamp` verified identical (`pandas.DataFrame.equals`) |
| `outputs/module1_indra_batch/module1_manifest.csv` | `4ce4ed50...4590c` | `e3b98bca...9f0f30` | No | **Yes** — identical except the `source_video`/`emission_csv` path strings, which differ only because the rerun was deliberately written to a different directory name; all other columns (`resolution`, `fps`, `frames`, `calibration_profile`, `status`, `reason`) identical |
| `outputs/module1_distance_enriched/INDRA_COPERT_DATASET_WITH_DISTANCE.csv` | `7c85f5c7...eaba f39` | `e4300aab...835f7b2` | No | **Partially** — all 16 baseline columns identical row-for-row except `timestamp`; regenerated file has 1 additional documented column (`vehicle_total_distance_km`, see note above) |
| `outputs/module2_copert_scenario_distance/INDRA_COPERT_INPUT.csv` | `e58c57a1...e09bc4` | `c7b633cf...29611c14` | No | **Yes** — all 53,044 rows, all 27 columns except `timestamp` verified identical |

**Classification of every difference found:**
1. `timestamp` column differs on every row of every file → **nondeterministic output, expected
   and semantically equivalent.** `timestamp()` in `run_module1.py` is `datetime.now()` —
   wall-clock time at the moment each video is processed, by design, not derived from video
   content. All content-bearing columns (vehicle IDs, classes, speeds, positions, density,
   distances) are byte-identical.
2. `module1_manifest.csv` path columns (`source_video`, `emission_csv`) differ → **path
   difference caused by this verification run deliberately using a different `--output-dir`**
   (`..._RERUN`) to avoid touching the frozen baseline, not a pipeline defect. Running with the
   original `--output-dir outputs/module1_indra_batch` would reproduce the exact baseline paths.
3. `INDRA_COPERT_DATASET_WITH_DISTANCE.csv` extra `vehicle_total_distance_km` column →
   **path/contract-drift difference** (baseline predates a documented column now legitimately
   present in current code); not a calculation change, not consumed downstream, not fixed (see
   note above).
4. The genuine bug (item above, emission CSV schema) → **fixed**, see "Bug found and fixed".

No nondeterminism was found in vehicle detection, tracking, class assignment, speed,
acceleration, world coordinates, density, or distance — every one of those columns reproduced
exactly across a full independent 30-video rerun using the real model and real ByteTrack
tracker.

## Duplicate-row check

- `INDRA_COPERT_DATASET.csv`: 17 rows are duplicates when `timestamp` is excluded, identical
  between baseline and rerun. Investigated: all 17 belong to `video12`, `vehicle_id=2`, with
  `speed_kmph=0`, `in_roi=0`, unchanging `world_x_m`/`world_y_m` — a genuinely stationary,
  continuously-tracked vehicle whose rounded values simply repeat across consecutive frames.
  **Not the class-flicker duplication bug** documented in `docs/KNOWN_ISSUES.md` §2 (that issue
  was about `vehicle_emissions.csv` splitting one physical vehicle across multiple emission
  rows by class; it was already fixed in `copert_emission_engine.py` before this session and is
  unaffected by anything touched here).
- `vehicle_emissions.csv` (existing, untouched, per instruction not to rerun the COPERT engine
  unnecessarily): 0 duplicate `(video_id, vehicle_id)` pairs across 1,075 rows — confirms the
  KNOWN_ISSUES §2 fix is intact.
- 6 fully-duplicate rows (including `timestamp`) exist in the original baseline
  `INDRA_COPERT_DATASET.csv` — coincidental exact-timestamp collisions among the same
  stationary-vehicle rows above; not present in the rerun (different wall-clock timestamps),
  confirming this was always benign.

## COPERT-relevant validation

- Bicycle: 782 raw detections / 71 tracks across the 30-video rerun. Confirmed **excluded**
  from all COPERT/emission processing at `build_copert_scenario_dataset.py`'s
  `remove_non_motorized_bicycles` stage (audited: 625 rows removed in the ROI-filtered baseline
  data, logged in `COPERT_SCENARIO_AUDIT.csv`) — bicycles never reach
  `copert_emission_engine.py`. Matches the six-class mapping rule (bicycle counted, never
  tailpipe-mapped).
- Autorickshaw: counted and tracked, but has no approved COPERT factor category (documented,
  `docs/KNOWN_ISSUES.md`) — excluded at the emission-engine step (127 tracks in
  `excluded_vehicle_tracks.csv`), consistent with `docs/MODULE1_CONTRACT.md`.
- Only `car → PASSENGER_CAR`, `motorcycle → MOTORCYCLE`, `bus → BUS`, `truck →
  HEAVY_DUTY_TRUCK` reach emission calculation — matches `configs/project_config.yaml`'s
  `yolo_to_copert_category`, unchanged.
- Only 4 pollutants computed: **CO2, NOx, CO, PM2.5** — matches `FALLBACK_FACTORS` /
  `pollutants` in `configs/project_config.yaml`; no other pollutant is calculated anywhere in
  the codebase.
- Per instruction, `copert_emission_engine.py` was **not rerun** — `outputs/copert_emissions/
  vehicle_emissions.csv` (1,075 tracks, 0 duplicates, no nulls) was inspected as-is and treated
  as the existing, validated source of truth. Its input (`INDRA_COPERT_INPUT.csv`) was
  independently confirmed to reproduce exactly from the real-environment rerun (see baseline
  comparison table), so the existing emissions file remains valid.

## Module 1 output row counts (rerun)

| Stage | Rows |
|---|---|
| Raw per-frame detections (all 6 classes, all tracks, incl. non-eligible) | 65,318 |
| Merged `INDRA_COPERT_DATASET.csv` (quality-approved emission rows) | 61,707 |
| `INDRA_COPERT_DATASET_WITH_DISTANCE.csv` | 61,707 |
| `INDRA_COPERT_INPUT.csv` (post ROI + bicycle-removal + numeric/sanity filters) | 53,044 |
| Unique tracked vehicles (ByteTrack IDs, all classes) | 2,231 |
| Unique quality-approved emission tracks | 1,266 |

## Units / sanity check

- `speed_kmph`: 0.0–75.58 (bounded by `MAX_REASONABLE_SPEED_KMPH=80.0`) — OK.
- `acceleration_mps2`: −1.293–1.339 (bounded by `MAX_REASONABLE_ACCEL_MPS2=5.0`) — OK.
- `traffic_density_vehicles_per_100m2`: 0.714–13.571 — plausible for the calibrated ROI.
- `in_roi`: binary {0,1} — OK.
- No null values in any column of `INDRA_COPERT_DATASET.csv` or `INDRA_COPERT_INPUT.csv`.
- Class-flicker rate (same ByteTrack ID assigned >1 class across its life): 183/1,266 tracks
  (~14.5%) — pre-existing, expected, and already handled correctly downstream by
  `copert_emission_engine.py`'s per-track majority-class grouping (KNOWN_ISSUES.md §2).

## Tests

`tests/` contains only an empty `__init__.py` — no test cases exist in the live suite. The
`archive/legacy_src_prototypes/test_*.py` files are explicitly archived, pre-`main.py`
prototypes (see `docs/REPO_MAP.md`), not part of the live pipeline, and were not run.
`pytest` was installed into `venv` and run against `tests/`: **0 tests collected, 0 failures.**

## Fixes made

1. `module1_traffic/run_module1.py`: removed `distance_km` and `vehicle_total_distance_km` from
   the per-video emission-training CSV's `emission_fields` list, restoring the frozen
   `docs/MODULE1_CONTRACT.md` 11-column schema and fixing the `run_batch.py` merge crash. No
   calibration, mapping, distance-calculation, or COPERT-factor logic was changed.

## Final status

**MODULE 0 VERIFICATION: PASS**

Module 1's YOLO11s + ByteTrack pipeline was proven to reproduce the frozen baseline's
content exactly (modulo the expected wall-clock `timestamp` column) across all 30 INDRA videos,
using the real project environment for the first time. One genuine, pre-existing (not
restructure-caused) bug was found and fixed with a minimal, contract-aligned change. All
downstream Module 1/2 data-preparation outputs (`INDRA_COPERT_DATASET_WITH_DISTANCE.csv`,
`INDRA_COPERT_INPUT.csv`) were independently re-derived and confirmed to match. The existing,
already-validated `vehicle_emissions.csv` was left untouched per instruction and confirmed
consistent with its (now independently reproduced) input.
