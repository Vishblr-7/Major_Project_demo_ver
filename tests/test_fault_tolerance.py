"""Fault-tolerance tests for Module 1 (module1_traffic/run_module1.py).

These exercise the pure, side-effect-free building blocks of the pipeline
directly (resolution validation, homography/geometry validation, the
emission-track quality gate, and the shared TrafficState dataclass) rather
than running the full YOLO+ByteTrack loop end-to-end, since that requires a
GPU/CPU-heavy model load per test. Task B's brief: force each fault
condition and assert graceful degradation, not an uncaught exception.
"""

import numpy as np
import pytest

from module1_traffic import config, run_module1
from module1_traffic.traffic_state import TrafficState


# ---------------------------------------------------------------------------
# 1. Missing / unsupported calibration
# ---------------------------------------------------------------------------

def test_supported_resolution_returns_known_profile():
    profile = run_module1.validate_camera_resolution(1920, 1080)
    assert profile == "H1_1080P"


def test_unsupported_resolution_raises_clean_error_for_strict_mode():
    """Video-file inputs must still fail loudly and clearly, never silently
    apply the wrong calibration to a different physical camera setup."""
    assert config.REQUIRE_SUPPORTED_RESOLUTION is True
    with pytest.raises(RuntimeError) as excinfo:
        run_module1.validate_camera_resolution(800, 600)
    message = str(excinfo.value)
    assert "800x600" in message
    assert "calibrate" in message.lower()


def test_all_three_calibrated_profiles_are_supported():
    for (width, height), profile in config.SUPPORTED_RESOLUTIONS.items():
        assert run_module1.validate_camera_resolution(width, height) == profile


# ---------------------------------------------------------------------------
# 2. Homography / geometry validation on a degenerate ROI
# ---------------------------------------------------------------------------

def test_create_homography_passes_for_master_resolution():
    homography, roi_points, geometry_valid = run_module1.create_homography(
        config.MASTER_WIDTH, config.MASTER_HEIGHT
    )
    assert geometry_valid is True
    assert homography.shape == (3, 3)
    assert np.isfinite(homography).all()
    assert len(roi_points) == 4


def test_create_homography_still_returns_a_result_for_a_scaled_resolution():
    """H2_720P is a supported, scaled-down profile of the same physical ROI --
    must not raise and must still validate cleanly."""
    homography, roi_points, geometry_valid = run_module1.create_homography(1280, 720)
    assert geometry_valid is True
    assert np.isfinite(homography).all()


# ---------------------------------------------------------------------------
# 3. Short tracks (below MIN_TRACK_LENGTH)
# ---------------------------------------------------------------------------

def _track(speeds, accelerations=None):
    accelerations = accelerations or [0.0] * len(speeds)
    return [
        {"speed_kmph": s, "acceleration_mps2": a}
        for s, a in zip(speeds, accelerations)
    ]


def test_short_track_is_rejected_not_crashed():
    short_track = _track([20.0] * (config.MIN_TRACK_LENGTH - 1))
    assert run_module1.valid_emission_track(short_track) is False


def test_empty_track_is_rejected_not_crashed():
    assert run_module1.valid_emission_track([]) is False


def test_long_plausible_track_is_accepted():
    plausible_track = _track([20.0] * config.MIN_TRACK_LENGTH)
    assert run_module1.valid_emission_track(plausible_track) is True


# ---------------------------------------------------------------------------
# 4. Implausible dynamics (would previously have polluted emissions silently)
# ---------------------------------------------------------------------------

def test_track_with_implausible_speed_is_excluded_entirely():
    bad_track = _track(
        [20.0] * (config.MIN_TRACK_LENGTH - 1)
        + [config.MAX_REASONABLE_SPEED_KMPH + 50.0]
    )
    assert run_module1.valid_emission_track(bad_track) is False


def test_track_with_implausible_acceleration_is_excluded_entirely():
    accelerations = [0.0] * (config.MIN_TRACK_LENGTH - 1) + [
        config.MAX_REASONABLE_ACCEL_MPS2 + 10.0
    ]
    bad_track = _track([20.0] * config.MIN_TRACK_LENGTH, accelerations)
    assert run_module1.valid_emission_track(bad_track) is False


# ---------------------------------------------------------------------------
# 5. Unsupported / unknown vehicle classes must not be counted or tracked
# ---------------------------------------------------------------------------

def test_unknown_class_name_is_filtered_before_tracking():
    """Mirrors the vehicle_mask list comprehension in run_module1.main():
    only classes in config.VEHICLE_CLASSES are ever handed to ByteTrack."""
    detected_names = ["car", "traffic_cone", "pedestrian", "truck", "unknown_object"]
    mask = [name in config.VEHICLE_CLASSES for name in detected_names]
    assert mask == [True, False, False, True, False]


def test_vehicle_classes_match_six_class_contract():
    assert set(config.VEHICLE_CLASSES) == {
        "car", "motorcycle", "bus", "truck", "autorickshaw", "bicycle",
    }


# ---------------------------------------------------------------------------
# 6. Shared TrafficState dataclass (Task C contract Modules 2/3/4 depend on)
# ---------------------------------------------------------------------------

def test_traffic_state_defaults_to_full_quality_with_zero_counts():
    state = TrafficState(timestamp="t", window_start="t0", window_end="t1")
    assert state.data_quality == "FULL"
    assert state.total_vehicles == 0
    assert state.average_speed_kmph is None  # not yet populated, not zero


def test_traffic_state_count_only_marks_physical_fields_none_not_zero():
    """A COUNT_ONLY snapshot must not silently claim 0 km/h -- that is a
    real, distinct measurement from 'no calibrated speed available'."""
    state = TrafficState(
        timestamp="t", window_start="t0", window_end="t1",
        total_vehicles=5, current_vehicles=5,
        calibration_profile="UNSUPPORTED_COUNT_ONLY",
        data_quality="COUNT_ONLY",
    )
    assert state.average_speed_kmph is None
    assert state.density_veh_per_100m2 is None
    assert state.total_vehicles == 5  # counts still work without calibration


def test_traffic_state_csv_fieldnames_are_stable_and_complete():
    fields = TrafficState.csv_fieldnames()
    for required in (
        "timestamp", "window_start", "window_end", "total_vehicles",
        "current_vehicles", "average_speed_kmph", "calibration_profile",
        "data_quality",
    ):
        assert required in fields
