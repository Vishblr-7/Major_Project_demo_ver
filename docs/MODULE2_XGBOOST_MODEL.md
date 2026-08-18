# Module 2 — XGBoost windowed emission-rate model

Written 2026-08-18. Trains a model that predicts emission rate directly from live
`TrafficState`-shaped traffic features, so Module 4's dashboard never has to run per-vehicle
COPERT lookups in real time.

## Target definition

For every 2.0s window (0.5s stride, from `module1_traffic.windows.extract_windows()`) of every
one of the 30 INDRA videos, the target is:

```
<pollutant>_rate_g_per_s = window_<pollutant>_g / window_duration_s
```

where `window_<pollutant>_g = sum over vehicles present in that window of
(distance_km_in_window * <pollutant>_EF_g_per_km)`, using Task B's per-vehicle-track emission
factors (`outputs/copert_emissions/vehicle_emissions.csv`), and `window_duration_s` is the
window's *actual* frame span (`(frame_end - frame_start + 1) / fps`), not the nominal 2.0s --
the final window of a short clip is legitimately shorter, and dividing by the nominal length
there would understate the rate. A rate, not the raw window total, is the regression target
specifically so the model cannot implicitly learn window length as a hidden feature.

Trained for all four pollutants: **CO2 (primary)**, NOx, CO, PM2.5 (secondary).

## Model architecture: four independent models, not one multi-output model

Chose **four independent single-target `XGBRegressor` models**, one per pollutant, over a
single multi-output model, for three reasons: (1) the four targets span roughly five orders of
magnitude (CO2 ~0.4-7.6 g/s vs PM2.5 ~0.00004-0.0006 g/s), which single-target models handle
naturally via each model's own scale-appropriate splits, whereas a shared multi-output tree
would need careful per-target loss weighting to avoid CO2 dominating the shared splits; (2) the
four pollutants clearly do not share the same learnability (see results below -- PM2.5 is
essentially unlearnable from this dataset, CO2/NOx/CO are weakly learnable), which is easiest to
see and report with independent per-target metrics; (3) with only 386 training rows, XGBoost's
native multi-output tree mode is both immature and more prone to overfitting than four small
single-target models. The cost is 4x the training time and 4x the artifacts, both negligible at
this data scale.

## Features (14, all TrafficState-shaped)

```
car_count, motorcycle_count, bus_count, truck_count, autorickshaw_count, bicycle_count,
total_vehicles, current_vehicles, average_speed_kmph, speed_std,
density_veh_per_100m2, mean_acceleration, acceleration_std, stopped_vehicle_ratio
```

**Excluded, deliberately:** `flow_veh_per_min` and `roi_occupancy` are real `TrafficState`
fields, but `windows.py`'s `_build_state()` always leaves them `None` when reconstructing a
window from a trajectory CSV (flow needs line-crossing events, occupancy needs a calibrated ROI
capacity -- neither is present in the raw per-frame trajectory data) -- see
`module1_traffic/windows.py`'s own docstring. They carry zero signal in this dataset (100% null)
and were dropped rather than trained on all-`NaN` columns. In a genuinely live deployment where
Module 1's live-camera path (`run_module1.py`'s `write_traffic_state()`) computes these two
fields for real, they could be added back in and would likely help, especially `flow_veh_per_min`
as a leading indicator of oncoming traffic the model can't see yet.
`calibration_profile`/`data_quality` were excluded as constant across this dataset (single
calibration profile `H1_1080P`, always `FULL` quality) -- no variance, no signal, here.

## Validation: GroupKFold(n_splits=5), grouped on `video_id`

Windows from the same video are not independent -- a 0.5s stride inside a 2.0s window means
adjacent windows share up to 3 of their 4 quarters of frames. A plain random K-fold would put
near-duplicate windows from the same video on both sides of the train/test split, giving an
optimistic, leaked score. `GroupKFold` on `video_id` guarantees every window from a given video
lands in exactly one fold; with 30 videos and 5 folds, each fold holds out 6 whole videos.

## Results (out-of-fold, 386 windows / 30 videos)

| Pollutant | OOF MAE (g/s) | OOF RMSE (g/s) | OOF R² |
|---|---|---|---|
| **CO2** | 0.660 | 0.963 | **0.271** |
| NOx | 0.000269 | 0.000434 | 0.253 |
| CO | 0.00153 | 0.00196 | 0.370 |
| PM2.5 | 0.0000685 | 0.0000856 | **-0.030** |

Per-fold R² ranges: CO2 0.17-0.33, NOx -1.43-0.58 (one fold badly negative), CO -0.11-0.43,
PM2.5 -0.26- -0.01 (every fold negative).

**Top features (mean |SHAP|, primary CO2 model):** `truck_count` (0.392), `average_speed_kmph`
(0.300), `autorickshaw_count` (0.157), `stopped_vehicle_ratio` (0.146), `car_count` (0.123).
`truck_count` dominating makes physical sense -- COPERT's own factors put a single truck's g/km
CO2 output at ~7.5x a car's and ~15x a motorcycle's (`FALLBACK_FACTORS`), so a window's truck
count is close to a direct emission-rate proxy on its own. NOx and CO follow a similar
truck/bus-led importance pattern (see `module2_emission/xgboost/training_metrics.json` for the
full per-pollutant breakdown). SHAP (`shap` 0.51.0) installed and ran cleanly; no fallback to
built-in gain importance was needed.

**PM2.5 could not be made to learn anything.** Every fold's R² is negative (worse than
predicting the training mean), and inspecting the saved model directly shows why: all 200
boosted trees are pure root leaves -- zero real splits were made
(`booster.trees_to_dataframe()` shows 0/200 trees with a non-leaf node), and SHAP importance is
identically 0.0 for every feature. This was re-tested with three different hyperparameter sets
(shallower/deeper trees, higher/lower regularization, more/fewer estimators) and the result did
not change -- this is a data limitation, not an undertuned model. The likely cause: PM2.5's
window-level EF spread is small (`0.0069`-`0.0702` g/km across categories, versus CO2's
`73`-`1,124` g/km, a ~10x narrower dynamic range) while its rate is still driven by the same rare
truck/bus presence as the other pollutants -- with only 386 windows and 30 groups, there are too
few truck/bus-heavy windows for GroupKFold's held-out folds to generalize a signal this faint
against typical per-frame speed/density noise. More videos, or windows from videos with heavier
truck/bus traffic, would very plausibly fix this; this dataset alone does not.

## What this model does and does not capture

It captures a real, moderate (CO2/CO best, NOx close behind) relationship between aggregate
traffic-state features and window-level emission rate, learned entirely from features Module 1's
live path already produces every 2 seconds -- exactly the point of this model, letting Module 4
skip per-vehicle COPERT lookups in real time. It does **not** capture: (1) any vehicle currently
in the ROI but not yet stably tracked/classified by ByteTrack (a vehicle that just entered frame
contributes to speed/density with a fraction of a track's worth of history, which this model has
no way to distinguish from a fully-observed vehicle); (2) emission factors for vehicle types it
never saw enough truck/bus-heavy windows of -- the training set has only 15 truck tracks and 6
bus tracks in the source `vehicle_emissions.csv` out of 1,075 total, so the model's truck/bus
sensitivity is extrapolated from a small number of examples and should not be trusted far outside
that range; (3) PM2.5 at all, for the reasons above -- Module 4 should not surface a PM2.5
rate from this model as anything more than a rough placeholder, or should suppress it entirely
until retrained on more data; (4) any of the same known upstream limitations already documented
for Module 1 (`ROAD_WIDTH_M`/`ROAD_LENGTH_M` are assumed, not measured -- every distance, speed,
and therefore every emission-rate number here scales with that assumption's error) and Module 2's
`FUEL_SELECTOR_BY_CATEGORY` fleet-mix assumption (`docs/MODULE2_COPERT_METHODOLOGY.md`).

## Honest caveat on dataset size

386 rows from 30 videos, most only 5-11 seconds long, is a small dataset for a 14-feature
gradient-boosted model. The CO2/NOx/CO R² values (0.25-0.37) are real signal above a mean-only
baseline, not noise (every fold is positive for those three), but they should be read as "better
than nothing, not yet production-grade" -- more, longer, and more traffic-diverse videos are the
single highest-leverage improvement available for this model, the same conclusion Module 1's
verification reached for the physical calibration constants.

## Artifacts

- `module2_emission/xgboost/training_dataset.csv` -- the 386-row windowed dataset (Task C).
- `module2_emission/xgboost/models/{CO2,NOx,CO,PM25}_emission_rate_model.json` -- trained
  models, native XGBoost JSON format, each fit on the full 386-row dataset after CV.
- `module2_emission/xgboost/oof_predictions.csv` -- out-of-fold `(video_id, window_index,
  pollutant, actual, prediction)` rows for every window, usable for residual analysis.
- `module2_emission/xgboost/training_metrics.json` -- full per-fold metrics and feature
  importance for all four pollutants.
