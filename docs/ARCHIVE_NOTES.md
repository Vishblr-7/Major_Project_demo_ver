# archive/ contents and why each script was moved here (2026-08-17, Module 0)

## archive/legacy_src_prototypes/
`detect.py`, `track.py`, `tracker.py` (+ their tests: `test_yolo.py`, `test_tracker.py`,
`test_line_count.py`, `test_speed.py`, `test_opencv.py`, `test_analytics.py`,
`verify_video_analytics.py`). These predate `main.py` (now `module1_traffic/run_module1.py`):
they use a bare `from config import ...` import style (not `from src import config`), and
`tracker.py`'s `VehicleTracker` class is not instantiated anywhere in the live pipeline, which
implements detection + ByteTrack tracking inline instead. Kept for reference, not deleted;
would need rewriting against the current module layout before being useful again, which is out
of scope for a repair-only pass.

## archive/legacy_video02_distance_experiments/
`copert_emission_engine_v2.py`, `prepare_video_emission_input.py`, `add_total_distance.py`,
`recalculate_video02_distance_from_speed.py`, `final_distance_from_speed.py`. A single-video
(video02-only) exploration of three different ways to compute per-step vehicle distance
(cumulative-diff, constant-FPS-from-speed, frame-gap-aware-from-speed), evaluated before
settling on the longitudinal-`world_y`-differencing approach that
`enrich_module1_distances.py` uses for the real 30-video production dataset.
`copert_emission_engine_v2.py`'s default `--input` points at
`outputs/copert_video02/video02_emissionv2_ready.csv`, a filename that was never actually
produced by any script in this lineage (closest matches are `video02_emission_ready.csv`,
`_ready_v2.csv`, `_ready_final.csv`) -- confirming this branch was never fully wired end to end.
Kept for the reasoning trail, not deleted.

## src/analytics.py -> module1_traffic/analytics/analytics.py
Kept, not archived -- `calculate_analytics()`/`save_analytics()` are generically useful
(congestion index, per-class percentages) and not tied to the old prototype modules. It is
NOT currently called by `run_module1.py`; a future module (dashboard, or a live traffic-state
summary) is the more likely place to wire it in.

## What was NOT archived
`enrich_module1_distances.py`, `build_copert_scenario_dataset.py`, `copert_emission_engine.py`
are the canonical, currently-in-use Lineage A pipeline (confirmed: their outputs' row counts
and checksums match what actually produced the 1,192/1,202-track COPERT dataset). These moved
into `module2_emission/` as first-class code, not archive.
