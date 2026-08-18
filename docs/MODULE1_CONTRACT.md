# Module 1 output contract (frozen 2026-08-17)

Later modules (2, 3, 4) must treat these schemas as a contract. If Module 1 ever needs to
change one of these, that is a breaking change requiring an explicit version bump and a
migration note here -- not a silent column rename.

## Per-video emission-training CSV
(`module1_traffic/outputs/.../<video_id>_emission_training.csv`, merged into
`outputs/module1_indra_batch/INDRA_COPERT_DATASET.csv`)

| column | type | notes |
|---|---|---|
| video_id | str | stable source identifier |
| vehicle_id | int | ByteTrack id, stable within one video |
| vehicle_type | str | one of: car, motorcycle, bus, truck, autorickshaw, bicycle |
| timestamp | str | `%Y-%m-%d %H:%M:%S` |
| speed_kmph | float | smoothed, clipped to [0, MAX_REASONABLE_SPEED_KMPH] |
| acceleration_mps2 | float | clipped to [-MAX_REASONABLE_ACCEL_MPS2, +MAX_REASONABLE_ACCEL_MPS2] |
| world_x_m, world_y_m | float | road-plane coordinates via homography |
| traffic_density_vehicles_per_100m2 | float | ROI-wide density at that frame |
| stop_duration_s | float | consecutive time below MOVING_SPEED_THRESHOLD_KMPH, resets on movement |
| in_roi | 0/1 | inside the calibrated ROI polygon |

Only rows belonging to tracks that pass `valid_emission_track()` (length >= MIN_TRACK_LENGTH,
plausible speed/acceleration bounds, valid homography) appear in this file at all.

## Per-video traffic CSV
(`<video_id>_traffic.csv`)

| column | type | notes |
|---|---|---|
| timestamp | str | one row per AGGREGATION_INTERVAL |
| car_count, motorcycle_count, bus_count, truck_count, autorickshaw_count, bicycle_count | int | in-ROI counts by class at snapshot time |
| total_vehicles | int | sum of the six class counts |
| current_vehicles | int | vehicles currently inside the ROI |
| average_speed | float | km/h, mean of in-ROI moving vehicles |
| vehicles_per_100m2 | float | density |

## Per-video trajectory CSV
(`<video_id>_trajectory.csv`) -- superset of the emission-training CSV, includes every
detected/tracked vehicle (not just emission-eligible ones), plus:
`frame_number, image_x, image_y, distance_km` (cumulative, longitudinal-only),
`vehicle_total_distance_km`, `emission_eligible` (0/1).

## Module 1 manifest
(`outputs/module1_indra_batch/module1_manifest.csv`)

One row per input video: `video_id, source_video, resolution, fps, frames,
calibration_profile, status, reason, emission_csv`. `status` is one of `INCLUDED`,
`EXCLUDED_RECALIBRATION_REQUIRED`, `EXCLUDED_PROCESSING_FAILED`.

## Emission eligibility by class (unchanged, do not alter)

car, motorcycle, bus, truck -> COPERT-eligible.
autorickshaw -> detected/counted, excluded from quantitative COPERT until a defensible direct
factor is established (see `docs/KNOWN_ISSUES.md`).
bicycle -> excluded from tailpipe emissions entirely; still counted for density/occupancy.
