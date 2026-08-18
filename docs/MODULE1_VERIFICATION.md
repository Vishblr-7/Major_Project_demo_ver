# Module 1 (Traffic Perception) — Verification Report

Generated 2026-08-17 as part of the Module 1 prompt (verify, harden, add live-camera path).
Module 1's core detection/tracking/homography logic is unchanged from Module 0 — this report
documents what exists and what was verified, not a redesign.

## 1. Detector

- **Model:** `models/best.pt`, YOLO11s, custom-trained on 6 vehicle classes.
- **Class mapping** (must match training labels exactly; sourced from
  `configs/project_config.yaml`, verified identical to the pre-Module-0 hardcoded values):
  `0=car, 1=motorcycle, 2=bus, 3=truck, 4=autorickshaw, 5=bicycle`.
- **Dataset split** (15,000 train / 2,000 val / 2,000 test): as documented in the handoff PDF.
  This session could not independently re-verify the split, since the raw YOLO training dataset
  (image files + label files used for `best.pt`'s training run) is not present in this repo
  snapshot — only the trained weights and the downstream INDRA batch outputs are. If you have
  the original training manifest/dataset folder, it's worth cross-checking those counts once;
  this report defers to the PDF's figures rather than asserting them independently.

## 2. Batch run evidence — all 30 INDRA videos

Read from `outputs/module1_indra_batch/module1_manifest.csv`. All 30 videos: resolution
1920x1080, fps 30.0, calibration profile `H1_1080P`, status `INCLUDED`. No video was excluded.

| video_id | frames | emission rows | rows/frame |
|---|---|---|---|
| video10 | 150 | 1,780 | 11.87 |
| video11 | 210 | 1,987 | 9.46 |
| video12 | 180 | 1,774 | 9.86 |
| video13 | 240 | 2,384 | 9.93 |
| video14 | 180 | 1,677 | 9.32 |
| video15 | 180 | 1,885 | 10.47 |
| video16 | 210 | 2,037 | 9.70 |
| video17 | 330 | 3,632 | 11.01 |
| video18 | 210 | 2,176 | 10.36 |
| video19 | 180 | 1,787 | 9.93 |
| video2 | 150 | 1,777 | 11.85 |
| video20 | 210 | 2,349 | 11.19 |
| video21 | 180 | 2,293 | 12.74 |
| video22 | 150 | 1,761 | 11.74 |
| video23 | 180 | 2,318 | 12.88 |
| video24 | 240 | 2,947 | 12.28 |
| video25 | 180 | 1,878 | 10.43 |
| video26 | 210 | 1,792 | 8.53 |
| video27 | 180 | 2,348 | 13.04 |
| video28 | 180 | 2,194 | 12.19 |
| video29 | 180 | 1,916 | 10.64 |
| video3 | 180 | 1,822 | 10.12 |
| video30 | 180 | 2,143 | 11.91 |
| video31 | 210 | 2,057 | 9.80 |
| **video4** | 150 | 2,113 | **14.09** |
| video5 | 240 | 2,696 | 11.23 |
| **video6** | 210 | 1,377 | **6.56** |
| **video7** | 210 | 1,724 | 8.21 |
| video8 | 150 | 1,645 | 10.97 |
| video9 | 150 | 1,438 | 9.59 |

**Rows/frame across the 30 videos:** mean 10.73, std 1.59.

**Outliers flagged** (|z| > 1.5, computed on rows-per-frame to normalize for differing clip
lengths):
- **video6** (z = -2.62): the clear low outlier — 6.56 rows/frame, well below the rest of the
  set. Suggests either genuinely sparse traffic in that clip or a higher proportion of tracks
  that failed the quality gates (short tracks, implausible speed/acceleration). Worth a manual
  look at `outputs/module1_indra_batch/individual_runs/video6/video6_annotated.mp4`.
- **video4** (z = +2.11): the clear high outlier — 14.09 rows/frame, the densest clip in the set.
  Plausibly just heavier real traffic; also worth a manual look to confirm it isn't an ID-flicker
  or double-counting artifact (see `docs/KNOWN_ISSUES.md` section 2 for a related, confirmed
  flicker issue found elsewhere in the pipeline).
- **video7** (z = -1.58): borderline low, noted but not flagged as strongly as video6.

## 3. Calibration (unchanged, do not alter)

- Master resolution: 1920x1080.
- ROI points (image-space, master resolution): P1 (250, 230), P2 (1670, 260),
  P3 (1810, 1030), P4 (100, 1030).
- Road dimensions: **7.0 m wide x 20.0 m long**. These are stated in `module1_traffic/config.py`
  as assumed values ("Replace these with physically measured road dimensions when available").
  **They have not been physically measured.** Every downstream quantity that depends on absolute
  scale — speed (km/h), acceleration, distance (km), and therefore every COPERT g/km emission
  figure — is only as accurate as this 7.0 m x 20.0 m assumption. If the real road segment is
  wider or shorter, all speed/distance/emission numbers scale linearly with the error. This is
  the single highest-leverage measurement to go get with a tape measure or satellite imagery
  before treating any absolute number in this project as more than directionally correct.
- Supported resolution profiles: 1920x1080 -> H1_1080P, 1280x720 -> H2_720P,
  640x360 -> H3_360P. All 30 INDRA videos matched H1_1080P; H2/H3 have not been exercised by
  the batch (see Task B fault-tolerance tests for synthetic coverage of the other two).
- Reprojection gate: 0.05 m maximum error transforming calibrated ROI corners to world
  points. Minimum ROI area: 1,000 px². Both gates passed for all 30 videos (manifest shows all
  30 as `INCLUDED`, and `INCLUDED` requires `geometry_valid` to be true).

## 4. Quality gates actually enforced

From `module1_traffic/config.py` / `run_module1.py`'s `valid_emission_track()`:
- `MIN_TRACK_LENGTH = 10` — a track needs at least 10 observations to be emission-eligible.
- `MAX_REASONABLE_SPEED_KMPH = 80.0` — any track containing a speed sample above this is
  entirely excluded from emissions (not clamped, excluded).
- `MAX_REASONABLE_ACCEL_MPS2 = 5.0` — same treatment for acceleration.
- `SPEED_SMOOTHING_ALPHA = 0.30` — exponential smoothing weight; each accepted speed sample is
  30% the new median-of-recent-samples value and 70% the previous smoothed value.
- Per-step speed validation additionally rejects any single-frame speed jump implying more than
  `MAX_REASONABLE_ACCEL_MPS2` of acceleration from the vehicle's last valid speed, before it
  ever reaches the smoothing/track-level checks above.

## 5. Emission eligibility by class (unchanged, do not alter)

- **car, motorcycle, bus, truck** — COPERT-eligible; contribute to quantitative CO2/NOx/CO/PM2.5.
- **autorickshaw** — detected, tracked, and counted (affects density/occupancy/flow features),
  but excluded from quantitative COPERT emissions until a defensible direct emission factor is
  established (COPERT's standard categories don't have a clean three-wheeler mapping). See
  `docs/KNOWN_ISSUES.md`.
- **bicycle** — excluded from tailpipe emissions entirely (zero emissions by definition), but
  still counted for density/occupancy/flow features.

## 6. Hardening changes made in this pass (Tasks B/C/D)

- **Fixed a real headless-environment crash.** `run_module1.py`'s `finally` block
  unconditionally called `cv2.destroyAllWindows()`, which raises `cv2.error` under
  `opencv-python-headless` (no GUI backend) -- exactly the build any server/CI/Module-4
  deployment would use. Now wrapped in `try/except cv2.error: pass`. All CSV/video
  outputs are already flushed and closed before this line runs, so the fix cannot mask
  a real failure.
- **Live-camera count-only fallback.** Video-file inputs keep the original strict
  behaviour: an uncalibrated resolution still raises `RuntimeError` immediately (this
  cannot regress the 30-video batch, which is always 1920x1080). `--webcam` mode alone
  now falls back to COUNT-ONLY mode instead of crashing on an uncalibrated resolution --
  vehicles are still detected, tracked, and counted, but speed/distance/emission fields
  are left `None`/unavailable rather than silently reported as a plausible-looking `0.0`.
- **Shared `TrafficState` dataclass** (`module1_traffic/traffic_state.py`), emitted every
  2.0s (configurable via `--traffic-state-interval`) to a new `traffic_state.csv`,
  additive to all existing outputs -- no existing CSV schema changed. Fields: per-class
  counts, `total_vehicles`, `current_vehicles`, `average_speed_kmph`, `speed_std`,
  `density_veh_per_100m2`, `flow_veh_per_min`, `roi_occupancy`, `mean_acceleration`,
  `acceleration_std`, `stopped_vehicle_ratio`, `calibration_profile`, `data_quality`
  (`FULL` vs `COUNT_ONLY`).
- **Graceful Ctrl-C shutdown.** A `KeyboardInterrupt` during the frame loop now breaks
  out cleanly and still runs the existing tail processing (track eligibility, trajectory
  CSV, emission CSV) over whatever frames were processed, instead of losing that work.
- **`module1_traffic/windows.py`** -- a sliding-window feature extractor (default 2.0s
  window, 0.5s stride, both configurable) over the per-frame trajectory CSV, producing
  one `TrafficState`-shaped row per window plus a per-window `vehicle_id -> distance_km`
  breakdown for Module 2's COPERT apportionment. Verified on video2's real 150-frame
  trajectory output (10 windows produced; see `tests/test_windows.py`).
- **15 fault-tolerance tests + 5 windows tests, all passing** (`tests/test_fault_tolerance.py`,
  `tests/test_windows.py`): unsupported resolution (strict-mode raise, not a crash),
  short/empty tracks, implausible speed/acceleration exclusion, unknown-class filtering,
  and the `TrafficState` COUNT_ONLY contract (None, not 0.0, for physical fields).

## 7. Regression check (superseded, redone in the real project environment)

An earlier pass of this report ran in a sandboxed "cloud-container" session that could not
access the project's actual `venv`/Anaconda-based Python, and reported a ~1.5% row-count gap
against `docs/baseline_checksums.txt` (1,803 vs 1,777 rows for `video2`), attributed there to
unpinned-library version drift. That session's environment was never the real one, so that
gap could not be root-caused with confidence.

**This pass ran directly in the real `venv/bin/python`** (Python 3.11.5; torch 2.13.0;
ultralytics 8.4.115; opencv-python 5.0.0.93; supervision 0.29.1; numpy 2.4.6; pandas 3.0.5 --
see `docs/MODULE0_VERIFICATION.md` for the full environment verification). Two full 30-video
batch runs were executed with `venv/bin/python -m module1_traffic.run_batch`:

1. A rerun with only the Module 0 emission-schema fix applied (before Tasks B/C/D).
2. A second full rerun after all Task B/C/D hardening changes (`traffic_state.py`,
   `windows.py`, COUNT_ONLY fallback, graceful shutdown, the headless-`cv2` fix).

Results, all 30/30 videos `INCLUDED`, 61,707 merged rows both times:

- `outputs/module1_indra_batch/INDRA_COPERT_DATASET.csv` (frozen baseline) vs. the post-hardening
  rerun: **all 61,707 rows x 11 columns content-identical**, except the wall-clock `timestamp`
  column (`datetime.now()` at processing time, nondeterministic by design -- see
  `docs/MODULE0_VERIFICATION.md` for the full classification of this).
- `module1_manifest.csv`: identical on every column except the `source_video`/`emission_csv`
  path strings, which differ only because this verification run deliberately used a separate
  `--output-dir` to avoid touching the frozen baseline.
- Per-video trajectory CSVs (`video2`, `video10`, `video17`, `video6` spot-checked in full, all
  30 implicitly via the merged dataset check above): **content-identical row-for-row between
  the pre-hardening and post-hardening reruns**, except timestamp -- proof that Tasks B/C/D
  changed zero numeric output of the existing pipeline.
- The only new file per video is `traffic_state.csv` (from the new `TrafficState` emission) --
  strictly additive; no existing file was renamed, restructured, or had columns added/removed.

**Conclusion: byte-for-byte reproduction is achieved (modulo the documented, intentional
wall-clock timestamp) in the real project environment.** The earlier "~1.5% gap" was an
artifact of running in the wrong environment, not a real defect in Module 1 or in this
session's changes; it does not apply here and this section supersedes it.

## 8. What this report does NOT claim

This report describes what the code does and what the existing 30-video batch output shows. It
does not independently re-verify the YOLO11s training run's accuracy/mAP (no held-out
evaluation was re-run in this session), and the dataset-split figures in section 1 are taken
from the handoff PDF rather than independently recomputed. It does not claim the live-camera
path was tested against a real physical camera -- COUNT_ONLY-mode correctness was verified at
the unit-test level (`tests/test_fault_tolerance.py`), not via an actual uncalibrated webcam
session.

## 9. Task D window table (video2, real INDRA data, 150 frames @ 30fps)

`module1_traffic.windows.extract_windows()` run on `video2`'s real trajectory CSV with the
default `window_length_s=2.0`, `stride_s=0.5` produced 10 windows:

| window | frame_start | frame_end | total_vehicles | avg_speed_kmph | density_veh/100m2 | stopped_ratio | data_quality |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 60 | 20 | 3.35 | 14.286 | 0.400 | FULL |
| 1 | 16 | 75 | 24 | 3.65 | 17.143 | 0.375 | FULL |
| 2 | 31 | 90 | 27 | 3.11 | 19.286 | 0.556 | FULL |
| 3 | 46 | 105 | 25 | 3.16 | 17.857 | 0.520 | FULL |
| 4 | 61 | 120 | 24 | 2.31 | 17.143 | 0.500 | FULL |
| 5 | 76 | 135 | 20 | 2.52 | 14.286 | 0.450 | FULL |
| 6 | 91 | 150 | 19 | 3.04 | 13.571 | 0.368 | FULL |
| 7 | 106 | 150 | 14 | 3.59 | 10.000 | 0.429 | FULL |
| 8 | 121 | 150 | 11 | 4.20 | 7.857 | 0.364 | FULL |
| 9 | 136 | 150 | 11 | 4.20 | 7.857 | 0.364 | FULL |

Windows 7-9 are progressively shorter than 60 frames because the 150-frame clip ends before a
full 60-frame window fits, exactly the documented partial-final-window behaviour. The
per-window vehicle-distance breakdown produced 229 `(window_index, vehicle_id) ->
distance_km_in_window` rows for this one video, all non-negative, ready for Module 2's COPERT
apportionment.

## 10. Test suite

`venv/bin/python -m pytest tests/ -v`: **20/20 passed** -- 15 fault-tolerance tests
(`tests/test_fault_tolerance.py`: resolution validation, homography/geometry gates, short/empty
track rejection, implausible speed/acceleration exclusion, unknown-class filtering, and the
`TrafficState` COUNT_ONLY contract) and 5 windowed-extractor tests (`tests/test_windows.py`,
run against `video2`'s real trajectory data, not a synthetic fixture).

## 11. Final status

**MODULE 1 STATUS: PASS**

- Detector/tracker/calibration/quality-gates/emission-eligibility: unchanged, verified against
  the real 30-video batch output (section 2-5).
- Fault tolerance (Task B): 15/15 tests pass; the one crash actually found (unconditional
  `cv2.destroyAllWindows()` under a headless build) was fixed.
- Live-camera path (Task C): `TrafficState` dataclass, COUNT_ONLY fallback, 2s rolling
  snapshot cadence, and graceful Ctrl-C shutdown are all implemented and unit-tested.
- Windowed feature extractor (Task D): implemented, unit-tested against real data, output
  table shown above (section 9).
- Regression safety (Task E): the real-environment 30-video batch rerun reproduces
  `docs/baseline_checksums.txt`'s content byte-for-byte (modulo the documented wall-clock
  timestamp column), both before and after the Task B/C/D hardening changes, proving those
  changes are purely additive (section 7).
