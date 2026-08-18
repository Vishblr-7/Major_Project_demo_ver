# Repo map (post Module 0 restructure, 2026-08-17)

## Layout

```
module1_traffic/
  config.py            # calibration + thresholds (thresholds/paths now from configs/project_config.yaml)
  run_module1.py        # former main.py -- single-video/webcam pipeline. Logic untouched.
  run_batch.py           # former run_module1_batch.py -- batch-runs run_module1.py over a video directory.
  analytics/analytics.py # former src/analytics.py. NOT currently called by run_module1.py; kept for reuse.
  detection/ tracking/ homography/ speed/ roi/   # empty scaffolding for a future decomposition of
                                                   # run_module1.py. NOT split now -- see note below.
  outputs/.gitkeep
module2_emission/
  copert/copert_emission_engine.py           # canonical COPERT engine (defect-fixed, see below)
  factors/COPERT_2025_{CO,CO2,NOx}_EF.csv, COPERT_2025_PM2.5.csv
  data/processed/enrich_module1_distances.py, build_copert_scenario_dataset.py
  data/raw/ data/master/                     # empty, for module2_master.csv (Module 2 prompt)
  xgboost/ emission_engine/                  # empty, for the Module 2 prompt
  configuration/                              # empty, reserved for COPERT scenario config docs
module3_optimization/
  vac/ navigation/ qubo/ qiskit/ outputs/     # all empty placeholders (see note below)
module4_deployment/
  live_pipeline/ dashboard/ simulation/ outputs/   # empty, for the Module 4 prompt
models/best.pt                                # untouched, not moved, not retrained
configs/
  project_config.yaml                         # paths, six-class mapping, YOLO->COPERT mapping, thresholds
  loader.py                                    # load_config() / get_path() helpers
archive/
  legacy_src_prototypes/                       # detect.py, track.py, tracker.py + their tests --
                                                 # pre-main.py prototypes, not used by the live pipeline
  legacy_video02_distance_experiments/          # the single-video (video02-only) distance-methodology
                                                 # scripts superseded by enrich_module1_distances.py's
                                                 # longitudinal world_y approach: copert_emission_engine_v2.py,
                                                 # prepare_video_emission_input.py, add_total_distance.py,
                                                 # recalculate_video02_distance_from_speed.py,
                                                 # final_distance_from_speed.py
docs/
  REPO_MAP.md (this file), MODULE1_CONTRACT.md, ARCHIVE_NOTES.md, baseline_checksums.txt
outputs/, videos/, INDRA_data_for_emissions/, datasets/, notebooks/, requirements.txt, .env.example
  -- left in place, per instruction not to move generated data.
```

## Entry points (run from repo root)

```
python -m module1_traffic.run_module1 --video videos/video2.mp4 --video-id video2
python -m module1_traffic.run_batch --input-dir INDRA_data_for_emissions/videos_mp4 --output-dir outputs/module1_indra_batch
python module2_emission/data/processed/enrich_module1_distances.py
python module2_emission/data/processed/build_copert_scenario_dataset.py --input outputs/module1_distance_enriched/INDRA_COPERT_DATASET_WITH_DISTANCE.csv --output-dir outputs/module2_copert_scenario_distance
python -m module2_emission.copert.copert_emission_engine
```

`run_module1.py` and `run_batch.py` must be invoked with `-m` (module mode) from the repo
root, not as a bare script path, so `from module1_traffic import config` and
`from configs.loader import load_config` resolve correctly. As of Module 2,
`copert_emission_engine.py` also imports `configs.loader` (for the fuel-mix assumption and
factor-table sanity-check threshold) and must likewise be invoked with
`-m module2_emission.copert.copert_emission_engine`, not as a bare script path.

## Decisions made during the restructure (read before assuming a deviation is a bug)

1. **`module1_traffic/{detection,tracking,homography,speed,roi}/` are empty on purpose.**
   `run_module1.py` (former `main.py`) currently implements detection, tracking, homography,
   speed and ROI logic all inline in one file, tightly coupled and currently working. Splitting
   it into those subfolders now would be exactly the kind of logic redesign the Module 0 brief
   said not to do, with real risk of breaking a working pipeline for no functional gain. The
   folders exist as the target scaffold; decomposition is future work, ideally done only once
   there are regression tests pinning current behavior (the Module 1 prompt handles this).

2. **`module3_optimization/` subfolders are genuinely empty.** The original `module 3_optimision `
   folder (trailing space + typo in the name, which is why tooling couldn't read it) contained
   only empty scaffold subfolders (`vac/`, `navigation /`, `sumo/`, `route_analysis/`) with no
   files inside any of them. Nothing was lost; the empty scaffold was folded into the new
   `module3_optimization/{vac,navigation,qubo,qiskit,outputs}/` layout with `.gitkeep` markers.

3. **`git mv` couldn't literally run through this session's device bridge** (it blocks file
   deletion/unlink at the OS level for safety, and git's lock-file cleanup needs unlink). Every
   move below was done as `mv` + `git add -A`, which git's rename detection picks up as a proper
   rename (confirmed: `git status` shows `R  old -> new` for all of them, not delete+add).

4. **Two distinct historical script lineages existed for computing vehicle distance.** Lineage A
   (`enrich_module1_distances.py`, longitudinal `world_y` differencing) is the one that actually
   produced the 30-video production dataset and is kept as canonical. Lineage B
   (`prepare_video_emission_input.py` → `add_total_distance.py` →
   `recalculate_video02_distance_from_speed.py` → `final_distance_from_speed.py` →
   `copert_emission_engine_v2.py`) was a video02-only exploration of speed-based distance
   methods, never wired into the 30-video batch, and its entry script
   (`copert_emission_engine_v2.py`) points at an input filename that doesn't exist on disk. Moved
   to `archive/legacy_video02_distance_experiments/`, not deleted, so the reasoning trail survives.

## Defects fixed (Module 0, step 4)

- **4a.** `--factor-dir` now defaults to `module2_emission/factors` (previously pointed at a
  non-existent `copert_factors/`, so every emission record silently used
  `FALLBACK_SCENARIO_FACTOR`). A missing factor directory is now a hard `FileNotFoundError`
  instead of a silent fallback.
- **4b.** The loader now accepts both `COPERT_2025_PM2.5_EF.csv` and `COPERT_2025_PM2.5.csv`.
- **New finding during verification (not in the original defect list):** even with the correct
  directory, none of the four raw `COPERT_2025_*.csv` exports are safely machine-readable by the
  engine's generic column-matching in their current form -- CO2/NOx/CO have no usable header at
  all (merged-cell spreadsheet export), and PM2.5 *does* have a clean `Category`/`Total` column
  pair but that `Total` is tonnes for a reference urban/rural/highway scenario, not a g/km implied
  factor. Trusting it produced PM2.5 values roughly 338x too high. This was caught during
  verification and reverted before being shipped -- see `docs/KNOWN_ISSUES.md` and the
  Module 2 prompt for the follow-up: all four pollutants currently use the documented, correct
  `FALLBACK_FACTORS` constants, now loudly and explicitly logged as such (never silent). A real
  fix requires a dedicated parser per file format, which is new logic, not a path/filename fix,
  and is intentionally out of scope for this repair-only pass.
- **4c.** `requirements.txt` rewritten with pinned-minimum versions covering Modules 1-4.
- **4d.** `.env.example` added with `TOMTOM_API_KEY=`; `.env` was already gitignored.

## Known limitation of this verification pass

This sandbox has no network access and its Python interpreter is separate from the project's
actual environment (the repo's `venv/bin/python` is a symlink to `/Users/vishal/anaconda3/bin/python`,
which does not exist inside this session's isolated Linux VM). `ultralytics`/`torch`/`cv2` could
not be imported here, so the YOLO+ByteTrack detection/tracking stage of Module 1 could not be
re-run to prove `run_batch.py` reproduces `INDRA_COPERT_DATASET.csv` and `module1_manifest.csv`
byte-for-byte after the restructure (see `docs/KNOWN_ISSUES.md`). **Please run
`python -m module1_traffic.run_batch --input-dir INDRA_data_for_emissions/videos_mp4 --output-dir outputs/module1_indra_batch`
yourself and diff the result against `docs/baseline_checksums.txt`** to close that gap; the code
path itself was not touched (only its import line and its subprocess invocation string changed),
so a mismatch would be a real signal worth investigating rather than expected. Everything
downstream of Module 1 (`enrich_module1_distances.py`, `build_copert_scenario_dataset.py`) *was*
re-run in this session against the untouched Module 1 outputs and reproduced byte-identical
results -- see `docs/baseline_checksums.txt`.
