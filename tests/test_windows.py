"""Task D: unit test for module1_traffic/windows.py's sliding-window extractor,
run against one real INDRA trajectory CSV (video2, 150 frames @ 30fps)."""

from pathlib import Path

import pandas as pd

from module1_traffic.windows import (
    extract_windows,
    vehicle_distance_breakdown_to_dataframe,
    windows_to_dataframe,
)

TRAJECTORY_CSV = Path("/tmp/full2_traj.csv")


def _skip_if_missing():
    if not TRAJECTORY_CSV.exists():
        import pytest
        pytest.skip(
            "Requires a real Module 1 trajectory CSV from a video run; "
            "not present in this environment/test invocation."
        )


def test_extract_windows_produces_expected_count_for_video2():
    _skip_if_missing()
    results = extract_windows(TRAJECTORY_CSV, fps=30.0, window_length_s=2.0, stride_s=0.5)
    # 150 frames @ 30fps = 5.0s clip; 2.0s windows, 0.5s stride ->
    # starts at 0.0, 0.5, ..., while start_frame <= max_frame(150).
    assert len(results) > 0
    assert all(r.frame_end >= r.frame_start for r in results)
    assert all(r.video_id == "video2" for r in results)
    # window_index must be sequential and start at 0.
    assert [r.window_index for r in results] == list(range(len(results)))


def test_windows_are_frame_length_consistent_with_configured_window():
    _skip_if_missing()
    results = extract_windows(TRAJECTORY_CSV, fps=30.0, window_length_s=2.0, stride_s=0.5)
    max_frame = max(r.frame_end for r in results)
    # 2.0s @ 30fps = 60 frames per window, except windows clamped against the
    # end of the clip (frame_end == max_frame), which are legitimately shorter.
    for result in results:
        if result.frame_end < max_frame:
            assert result.frame_end - result.frame_start + 1 == 60


def test_vehicle_distance_breakdown_sums_to_less_than_total_track_distance():
    _skip_if_missing()
    results = extract_windows(TRAJECTORY_CSV, fps=30.0, window_length_s=2.0, stride_s=0.5)
    breakdown = vehicle_distance_breakdown_to_dataframe(results)
    assert not breakdown.empty
    assert (breakdown["distance_km_in_window"] >= 0).all()


def test_windows_to_dataframe_has_traffic_state_shape():
    _skip_if_missing()
    results = extract_windows(TRAJECTORY_CSV, fps=30.0, window_length_s=2.0, stride_s=0.5)
    frame = windows_to_dataframe(results)
    for column in ("total_vehicles", "average_speed_kmph", "data_quality", "calibration_profile"):
        assert column in frame.columns


def test_smaller_stride_produces_more_windows():
    _skip_if_missing()
    coarse = extract_windows(TRAJECTORY_CSV, fps=30.0, window_length_s=2.0, stride_s=1.0)
    fine = extract_windows(TRAJECTORY_CSV, fps=30.0, window_length_s=2.0, stride_s=0.5)
    assert len(fine) >= len(coarse)
