# Module 2 — 104-video XGBoost emission-rate models vs. the 30-video baseline

Written 2026-08-18. The 30-video baseline (`docs/MODULE2_XGBOOST_MODEL.md`,
`module2_emission/xgboost/models/`) is **kept as-is, untouched** — this is a separate,
additional set of models (`module2_emission/xgboost/models_104/`) trained on the full 104-video
INDRA dataset, for direct comparison.

## What changed vs. the 30-video pass

- **Data scale:** 30 → 104 videos (all 104 raw `datasets/INDRA_dataset/Videos/Videos/*.MOV`
  files — all confirmed 1920x1080, so all pass calibration; none excluded). The 74 videos not
  already in `INDRA_data_for_emissions/videos_mp4/` were run through the real YOLO11s+ByteTrack
  pipeline for the first time in this pass; the original 30 videos' Module 1 output was reused
  as-is (not reprocessed) and merged with the new 74 via
  `module2_emission/xgboost/merge_module1_batches.py`. **Verified the merge changed nothing**:
  the original 30 videos' entries in the recombined `vehicle_emissions.csv` are numerically
  identical, row-for-row, to the existing 30-video-only file.
- **COPERT run once, not per-video:** `enrich_module1_distances.py` →
  `build_copert_scenario_dataset.py` → `copert_emission_engine.py` ran exactly once against the
  combined 104-video manifest (not once per new video, not repeated), producing
  `outputs/copert_emissions_104/vehicle_emissions.csv` (3,179 included tracks / 408 excluded,
  up from 1,075/127) — satisfying "don't rerun COPERT unnecessarily" while still covering every
  video. All four pollutants source from `COPERT_FACTOR_TABLE`, same as the 30-video pass.
- **Windowed dataset:** 386 → 1,767 windows (`module2_emission/xgboost/training_dataset_104.csv`,
  via the new `build_training_dataset_104.py` — the original `build_training_dataset.py` and its
  `training_dataset.csv` output are untouched).

## Feature engineering (new, on top of the original 14 `TrafficState` features)

| Feature group | Columns added | Why |
|---|---|---|
| Per-class distance | `{car,motorcycle,bus,truck,autorickshaw,bicycle}_distance_km`, `total_distance_km_in_window` | Emission = distance x EF, so distance actually traveled inside the window (not just vehicle counts) is a far more direct predictor. Confirmed by SHAP below -- these dominate every pollutant's importance. |
| Composition ratios | `{car,motorcycle,bus,truck}_ratio` | Traffic *composition*, not just volume -- a window with 2 buses out of 3 vehicles emits very differently than one with 2 buses out of 30. |
| Temporal | `window_position_frac` (how far into its clip the window falls), `prev_total_vehicles`, `delta_total_vehicles` (same-video lag/trend) | Traffic building up or dissipating over a clip is real signal a snapshot-only feature set can't see. |

`flow_veh_per_min`/`roi_occupancy` remain excluded (always null when reconstructed from a
trajectory CSV, same reason as the 30-video baseline).

## Validation methodology

1. **Video-level 70/15/15 train/val/test split** (fixed seed 42): 73 train / 16 val / 15 test
   videos (1,571 / 196 windows respectively). Test videos are never touched until final
   evaluation.
2. **GroupKFold(n_splits=5) on train+val, grouped by `video_id`** -- same no-leakage discipline
   as the baseline, additionally used here to score a 5-point hyperparameter grid (tree
   depth/learning-rate/regularization) per pollutant; the config with the best mean CV R² is
   selected.
3. The selected config is refit on all of train+val and evaluated **once** on the held-out test
   set -- never used for tuning.

## Results: baseline (30-video) vs. 104-video

| Pollutant | Metric | 30-video baseline (OOF, all data) | 104-video CV (train+val) | 104-video held-out TEST |
|---|---|---|---|---|
| **CO2** | R² | 0.271 | **0.702** (±0.139) | **0.874** |
| | MAE (g/s) | 0.660 | -- | 0.185 |
| | RMSE (g/s) | 0.963 | -- | 0.248 |
| **NOx** | R² | 0.253 | **-0.370** (±0.919, unstable -- see below) | 0.696 |
| | MAE (g/s) | 0.000269 | -- | 0.000103 |
| | RMSE (g/s) | 0.000434 | -- | 0.000134 |
| **CO** | R² | 0.370 | **0.832** (±0.034) | **0.888** |
| | MAE (g/s) | 0.00153 | -- | 0.000590 |
| | RMSE (g/s) | 0.00196 | -- | 0.000800 |
| **PM2.5** | R² | -0.030 | **0.292** (±0.059) | **0.411** |
| | MAE (g/s) | 0.0000685 | -- | 0.0000379 |
| | RMSE (g/s) | 0.0000856 | -- | 0.0000529 |

CO2, CO, and PM2.5 all improve substantially and consistently between the CV estimate and the
held-out test set -- real, reproducible signal, not a lucky split. **NOx needs a caveat, not a
victory lap** (next section).

## PM2.5: genuinely improved, not target-manipulated

**Yes, PM2.5 genuinely improves.** The 30-video baseline model was provably unable to learn
anything (every one of its 200 trees was a leaf-only stump, R² = -0.03, worse than predicting
the mean). The 104-video model's CV R² (0.292) and test R² (0.411) are both clearly positive and
agree with each other -- the same pattern CO2/CO show, not an isolated lucky number. Nothing
about the target definition changed: still `PM25_g / actual_window_duration_s`, same COPERT
factors, same units. The improvement came entirely from (1) ~4.6x more windows and (2) the
per-class/total distance features, which SHAP confirms are now PM2.5's top three predictors
(`total_distance_km_in_window`, `car_distance_km`, `truck_distance_km`) -- versus the baseline
model, whose SHAP importance was identically zero for every feature because it never split at
all. This is exactly "improve through data/features and principled tuning," as asked, not a
redefinition of the target that would make the number better for the wrong reason.

## NOx: an honest caveat, not a clean win

NOx's held-out test R² (0.696) looks like the best-improved pollutant after CO2. It should not
be read that way without the full picture: **every hyperparameter configuration's GroupKFold CV
produced a negative mean R²** (range -0.37 to -1.14, with enormous per-fold standard deviation,
0.92-2.24). The mechanism is identifiable, not random noise: NOx's COPERT factor for buses
(1.2932 g/km) is ~31x a passenger car's (0.0414 g/km) -- by far the largest between-class ratio
of the four pollutants (CO2 ~6x, PM2.5 ~4x, CO ~1x) -- so NOx rate is close to "is there a bus in
this window," a feature almost entirely determined by whichever few bus-heavy videos exist.
`video67` (mean NOx rate ~8x the dataset average) happened to land in the **training** portion of
this run's random split, which is exactly why the final model's test score looks good: it got to
learn from the one video most responsible for CV instability. A different train/val/test seed
that put `video67` (or another bus-heavy video) in the test set instead would very plausibly
produce a much worse test R². **Treat the NOx test R² as encouraging but not yet reliable** --
more bus-heavy video coverage, not a different model, is what would actually fix this; a single
72-bus-track sample (6 in the 30-video set, more in the full 104 but still a minority class) is
the real bottleneck, not a modeling choice.

## Feature importance (SHAP, mean |value|, top predictors per pollutant)

- **CO2:** `total_distance_km_in_window`, `truck_distance_km`, `car_distance_km`,
  `window_position_frac`, `prev_total_vehicles`.
- **NOx:** `total_distance_km_in_window`, `bus_distance_km`, `truck_distance_km`,
  `prev_total_vehicles`, `bus_ratio` -- confirms the bus-sensitivity described above directly.
- **CO:** `total_distance_km_in_window`, `motorcycle_distance_km`, `window_position_frac`,
  `car_distance_km`, `prev_total_vehicles`.
- **PM2.5:** `total_distance_km_in_window`, `car_distance_km`, `truck_distance_km` (the rest are
  effectively zero) -- a much smaller but real and non-degenerate signal, unlike the baseline.

Across every pollutant, the new per-class/total distance features are the dominant predictors --
they were the single highest-leverage addition of this pass, well ahead of raw counts or
composition ratios.

## What's still fragile

- **NOx as discussed above** -- do not deploy without either more bus-heavy training coverage or
  a wider, video-diverse re-evaluation of the train/val/test split.
- **PM2.5 is improved, not solved.** R² ~0.3-0.4 is real signal, not production-grade precision;
  treat point estimates as directional.
- **408 excluded tracks (mostly autorickshaw)** still contribute zero to every target, same
  policy as the 30-video pass, for the same documented reason
  (`docs/MODULE2_COPERT_METHODOLOGY.md`).
- **`ROAD_WIDTH_M`/`ROAD_LENGTH_M` are still assumed, not measured** -- this affects every
  distance-derived feature and target in this document exactly as it did before; more data does
  not fix a systematic calibration assumption.
- The video-level split is a **single fixed 70/15/15 draw** (seed 42), not repeated-split
  cross-validation of the split itself -- the NOx finding above is a direct consequence of that;
  a more robust final report would repeat the whole train/val/test split under several seeds and
  report the spread, not just one draw's numbers.

## Artifacts

- `outputs/module1_104_batch/` -- merged 104-video Module 1 manifest + individual runs.
- `outputs/module1_distance_enriched_104/`, `outputs/module2_copert_scenario_distance_104/`,
  `outputs/copert_emissions_104/vehicle_emissions.csv` -- 104-video Lineage A + COPERT output.
- `module2_emission/xgboost/training_dataset_104.csv` -- the 1,767-window enriched dataset.
- `module2_emission/xgboost/models_104/{CO2,NOx,CO,PM25}_emission_rate_model.json` -- trained
  models (refit on train+val after CV-based hyperparameter selection).
- `module2_emission/xgboost/training_metrics_104.json` -- full grid search, CV, and test metrics
  for all four pollutants, plus the exact train/val/test video-id split for reproducibility.
- 30-video baseline (`module2_emission/xgboost/models/`, `training_dataset.csv`,
  `docs/MODULE2_XGBOOST_MODEL.md`) -- unchanged, kept as the comparison reference.
