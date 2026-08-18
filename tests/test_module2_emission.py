"""Fault-tolerance tests for Module 2 (COPERT engine + windowed training-dataset
builder + XGBoost trainer). Task E's brief: force each fault condition and assert
graceful degradation -- empty output, a documented skip, or a clear error message --
never an uncaught, unexplained exception.
"""

from pathlib import Path

import pandas as pd
import pytest

from module2_emission.copert import copert_emission_engine as engine
from module2_emission.xgboost.build_training_dataset import build_training_dataset
from module2_emission.xgboost.train_model import FEATURE_COLUMNS, validate_training_frame


COPERT_INPUT_COLUMNS = [
    "video_id", "vehicle_id", "vehicle_type", "distance_km",
    "in_roi", "emission_eligible", "vehicle_total_distance_km",
]


def _write_copert_input(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows, columns=COPERT_INPUT_COLUMNS).to_csv(path, index=False)


# ---------------------------------------------------------------------------
# 1. Empty input CSV
# ---------------------------------------------------------------------------

def test_empty_input_csv_produces_empty_output_not_a_crash(tmp_path):
    input_csv = tmp_path / "empty.csv"
    _write_copert_input(input_csv, [])
    output_dir = tmp_path / "out"

    import sys
    old_argv = sys.argv
    try:
        sys.argv = [
            "copert_emission_engine.py",
            "--input", str(input_csv),
            "--output-dir", str(output_dir),
        ]
        engine.main()
    finally:
        sys.argv = old_argv

    result = pd.read_csv(output_dir / "vehicle_emissions.csv")
    assert result.empty


# ---------------------------------------------------------------------------
# 2. A video with zero emission-eligible tracks
# ---------------------------------------------------------------------------

def test_video_with_zero_eligible_tracks_excludes_everything_gracefully(tmp_path):
    input_csv = tmp_path / "no_eligible.csv"
    _write_copert_input(input_csv, [
        {"video_id": "v1", "vehicle_id": 1, "vehicle_type": "bicycle",
         "distance_km": 0.01, "in_roi": 1, "emission_eligible": 1,
         "vehicle_total_distance_km": 0.01},
        {"video_id": "v1", "vehicle_id": 2, "vehicle_type": "autorickshaw",
         "distance_km": 0.02, "in_roi": 1, "emission_eligible": 1,
         "vehicle_total_distance_km": 0.02},
    ])
    output_dir = tmp_path / "out"
    import sys
    old_argv = sys.argv
    try:
        sys.argv = [
            "copert_emission_engine.py",
            "--input", str(input_csv),
            "--output-dir", str(output_dir),
        ]
        engine.main()
    finally:
        sys.argv = old_argv

    result = pd.read_csv(output_dir / "vehicle_emissions.csv")
    excluded = pd.read_csv(output_dir / "excluded_vehicle_tracks.csv")
    assert result.empty
    assert len(excluded) == 2
    assert set(excluded["vehicle_type"]) == {"bicycle", "autorickshaw"}


# ---------------------------------------------------------------------------
# 3. An unknown / unmapped vehicle category
# ---------------------------------------------------------------------------

def test_unknown_vehicle_category_is_excluded_not_crashed(tmp_path):
    input_csv = tmp_path / "unknown.csv"
    _write_copert_input(input_csv, [
        {"video_id": "v1", "vehicle_id": 1, "vehicle_type": "hovercraft",
         "distance_km": 0.05, "in_roi": 1, "emission_eligible": 1,
         "vehicle_total_distance_km": 0.05},
        {"video_id": "v1", "vehicle_id": 2, "vehicle_type": "car",
         "distance_km": 0.05, "in_roi": 1, "emission_eligible": 1,
         "vehicle_total_distance_km": 0.05},
    ])
    output_dir = tmp_path / "out"
    import sys
    old_argv = sys.argv
    try:
        sys.argv = [
            "copert_emission_engine.py",
            "--input", str(input_csv),
            "--output-dir", str(output_dir),
        ]
        engine.main()
    finally:
        sys.argv = old_argv

    result = pd.read_csv(output_dir / "vehicle_emissions.csv")
    excluded = pd.read_csv(output_dir / "excluded_vehicle_tracks.csv")
    assert len(result) == 1 and result.iloc[0]["vehicle_type"] == "car"
    assert len(excluded) == 1 and excluded.iloc[0]["vehicle_type"] == "hovercraft"


def test_get_factor_unknown_category_raises_keyerror_not_silent_wrong_number():
    """get_factor() is only ever called with a category already filtered to the
    known COPERT_LABELS set (main() excludes unmapped categories first) -- if
    it were ever called with an unknown one, it must fail loudly (KeyError on
    FALLBACK_FACTORS), not silently return a wrong number."""
    with pytest.raises(KeyError):
        engine.get_factor("Hovercraft", "CO2", {})


# ---------------------------------------------------------------------------
# 4. Missing factor-table directory
# ---------------------------------------------------------------------------

def test_missing_factor_directory_raises_clear_error(tmp_path):
    missing_dir = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError) as excinfo:
        engine.load_copert_factors(missing_dir)
    message = str(excinfo.value)
    assert "does_not_exist" in message
    assert "factor-dir" in message.lower() or "factors" in message.lower()


def test_factor_directory_with_no_matching_files_falls_back_per_pollutant(tmp_path, capsys):
    empty_but_existing_dir = tmp_path / "factors"
    empty_but_existing_dir.mkdir()
    tables = engine.load_copert_factors(empty_but_existing_dir)
    assert tables == {}
    value, source = engine.get_factor("Passenger Cars", "CO2", tables)
    assert source == "FALLBACK_SCENARIO_FACTOR"
    assert value == engine.FALLBACK_FACTORS["Passenger Cars"]["CO2"]


# ---------------------------------------------------------------------------
# 5. A windows/training dataset missing a required TrafficState feature column
# ---------------------------------------------------------------------------

def test_training_dataset_missing_feature_column_raises_clear_error():
    frame = pd.DataFrame({col: [1.0] for col in FEATURE_COLUMNS if col != "truck_count"})
    frame["video_id"] = ["v1"]
    frame["window_index"] = [0]
    for pollutant in ("CO2", "NOx", "CO", "PM25"):
        frame[f"{pollutant}_rate_g_per_s"] = [0.1]

    with pytest.raises(ValueError) as excinfo:
        validate_training_frame(frame)
    assert "truck_count" in str(excinfo.value)


def test_empty_training_dataset_raises_clear_error_not_silent_nan_model():
    columns = FEATURE_COLUMNS + ["video_id", "window_index"] + [
        f"{p}_rate_g_per_s" for p in ("CO2", "NOx", "CO", "PM25")
    ]
    frame = pd.DataFrame(columns=columns)
    with pytest.raises(ValueError) as excinfo:
        validate_training_frame(frame)
    assert "zero rows" in str(excinfo.value)


def test_build_training_dataset_with_no_included_videos_returns_empty_frame(tmp_path):
    manifest_path = tmp_path / "module1_manifest.csv"
    pd.DataFrame([{
        "video_id": "v1", "source_video": "x", "resolution": "1920x1080", "fps": 30.0,
        "frames": 10, "calibration_profile": "H1_1080P",
        "status": "EXCLUDED_RECALIBRATION_REQUIRED", "reason": "test", "emission_csv": "",
    }]).to_csv(manifest_path, index=False)
    emissions_path = tmp_path / "vehicle_emissions.csv"
    pd.DataFrame(columns=[
        "video_id", "vehicle_id", "CO2_EF_g_per_km", "NOx_EF_g_per_km",
        "CO_EF_g_per_km", "PM25_EF_g_per_km",
    ]).to_csv(emissions_path, index=False)

    dataset = build_training_dataset(manifest_path, emissions_path)
    assert dataset.empty
