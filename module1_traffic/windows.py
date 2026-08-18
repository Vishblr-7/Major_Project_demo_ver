"""Sliding-window feature extractor over a Module 1 per-frame trajectory CSV.

Module 2 (COPERT emission intelligence) needs both:
  1. a rolling traffic-state summary at a fixed cadence (same shape as the
     live TrafficState snapshot in module1_traffic/traffic_state.py, so
     Modules 2/3/4 consume one consistent schema whether the data came from
     a batch video or a live camera), and
  2. how much distance each individual vehicle covered inside that specific
     window, to apportion a COPERT g/km emission factor across the windows
     a long-lived track passes through, instead of only ever attributing
     the full track distance to a single row.

This module reads the trajectory_data.csv written by run_module1.main() and
produces both, without touching or re-deriving anything already computed by
Module 1 (it consumes speed_kmph/distance_km/in_roi as-is).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from module1_traffic import config
from module1_traffic.traffic_state import TrafficState

DEFAULT_WINDOW_LENGTH_S = 2.0
DEFAULT_STRIDE_S = 0.5


@dataclass
class WindowResult:
    """One sliding window's TrafficState plus per-vehicle distance breakdown."""

    video_id: str
    window_index: int
    frame_start: int
    frame_end: int
    state: TrafficState
    # vehicle_id -> total distance_km travelled by that vehicle within
    # [frame_start, frame_end], summed from the per-frame distance_km column
    # (not vehicle_total_distance_km, which is cumulative since track start).
    vehicle_distance_km: dict[int, float]


def _build_state(
    window_frame: pd.DataFrame,
    window_start_label: str,
    window_end_label: str,
    calibration_profile: str,
    geometry_valid: bool,
) -> TrafficState:
    roi = window_frame.loc[window_frame["in_roi"] == 1]
    # One row per vehicle: its most recent observation in this window.
    latest_per_vehicle = roi.sort_values("frame_number").groupby("vehicle_id").tail(1)

    class_counts = {vehicle: 0 for vehicle in config.VEHICLE_CLASSES}
    for vehicle_type, count in latest_per_vehicle["vehicle_type"].value_counts().items():
        if vehicle_type in class_counts:
            class_counts[vehicle_type] = int(count)
    total_vehicles = int(len(latest_per_vehicle))

    speeds = latest_per_vehicle["speed_kmph"].astype(float)
    accelerations = latest_per_vehicle["acceleration_mps2"].astype(float)
    stopped_ratio: Optional[float] = None
    average_speed: Optional[float] = None
    speed_std: Optional[float] = None
    mean_accel: Optional[float] = None
    accel_std: Optional[float] = None
    density: Optional[float] = None

    if geometry_valid and total_vehicles > 0:
        average_speed = float(speeds.mean())
        speed_std = float(speeds.std(ddof=0))
        mean_accel = float(accelerations.mean())
        accel_std = float(accelerations.std(ddof=0))
        stopped_ratio = float(
            (speeds < config.MOVING_SPEED_THRESHOLD_KMPH).sum() / total_vehicles
        )
        roi_area_m2 = config.ROAD_WIDTH_M * config.ROAD_LENGTH_M
        density = total_vehicles / roi_area_m2 * 100 if roi_area_m2 > 0 else 0.0

    return TrafficState(
        timestamp=window_end_label,
        window_start=window_start_label,
        window_end=window_end_label,
        car_count=class_counts.get("car", 0),
        motorcycle_count=class_counts.get("motorcycle", 0),
        bus_count=class_counts.get("bus", 0),
        truck_count=class_counts.get("truck", 0),
        autorickshaw_count=class_counts.get("autorickshaw", 0),
        bicycle_count=class_counts.get("bicycle", 0),
        total_vehicles=total_vehicles,
        current_vehicles=total_vehicles,
        average_speed_kmph=round(average_speed, 2) if average_speed is not None else None,
        speed_std=round(speed_std, 2) if speed_std is not None else None,
        density_veh_per_100m2=round(density, 3) if density is not None else None,
        flow_veh_per_min=None,  # requires crossing events, not present in trajectory CSV.
        roi_occupancy=None,
        mean_acceleration=round(mean_accel, 3) if mean_accel is not None else None,
        acceleration_std=round(accel_std, 3) if accel_std is not None else None,
        stopped_vehicle_ratio=round(stopped_ratio, 3) if stopped_ratio is not None else None,
        calibration_profile=calibration_profile,
        data_quality="FULL" if geometry_valid else "COUNT_ONLY",
    )


def extract_windows(
    trajectory_csv: str | Path,
    fps: float,
    window_length_s: float = DEFAULT_WINDOW_LENGTH_S,
    stride_s: float = DEFAULT_STRIDE_S,
    calibration_profile: str = "H1_1080P",
) -> list[WindowResult]:
    """Slide a window_length_s window, stepping by stride_s, across the video.

    Windows are frame-index based: [frame_start, frame_end] inclusive, sized
    round(window_length_s * fps) frames, stepped round(stride_s * fps) frames.
    The final partial window (shorter than window_length_s because the video
    ended) is still emitted -- callers needing fixed-length windows only
    should filter on (frame_end - frame_start + 1).
    """
    if window_length_s <= 0 or stride_s <= 0:
        raise ValueError("window_length_s and stride_s must both be positive.")

    frame = pd.read_csv(trajectory_csv)
    if frame.empty:
        return []

    required = {
        "video_id", "frame_number", "vehicle_id", "vehicle_type",
        "speed_kmph", "acceleration_mps2", "distance_km", "in_roi",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"trajectory CSV missing required columns: {missing}")

    video_id = str(frame["video_id"].iloc[0])
    # A geometry-invalid (COUNT_ONLY) trajectory CSV still has speed_kmph
    # columns, but they are meaningless -- emission_eligible is 0 for every
    # row in that case, which we use as our geometry-validity signal here
    # since the raw geometry_valid flag itself isn't persisted per-row.
    geometry_valid = bool(frame.get("emission_eligible", pd.Series([0])).astype(int).any()) or (
        "emission_eligible" not in frame.columns
    )

    window_frames = max(1, round(window_length_s * fps))
    stride_frames = max(1, round(stride_s * fps))
    min_frame = int(frame["frame_number"].min())
    max_frame = int(frame["frame_number"].max())

    results: list[WindowResult] = []
    window_index = 0
    start = min_frame
    while start <= max_frame:
        end = start + window_frames - 1
        window_slice = frame.loc[
            (frame["frame_number"] >= start) & (frame["frame_number"] <= end)
        ]
        if not window_slice.empty:
            start_ts = str(window_slice["timestamp"].iloc[0]) if "timestamp" in window_slice else str(start)
            end_ts = str(window_slice["timestamp"].iloc[-1]) if "timestamp" in window_slice else str(end)
            state = _build_state(window_slice, start_ts, end_ts, calibration_profile, geometry_valid)
            vehicle_distance = (
                window_slice.groupby("vehicle_id")["distance_km"].sum().round(6).to_dict()
            )
            results.append(
                WindowResult(
                    video_id=video_id,
                    window_index=window_index,
                    frame_start=start,
                    frame_end=min(end, max_frame),
                    state=state,
                    vehicle_distance_km={int(k): float(v) for k, v in vehicle_distance.items()},
                )
            )
            window_index += 1
        start += stride_frames

    return results


def windows_to_dataframe(results: list[WindowResult]) -> pd.DataFrame:
    """Flatten WindowResult objects into one row per window (state fields
    only) -- the per-window vehicle_id breakdown is written separately,
    since it's a variable-length one-to-many relationship."""
    rows = []
    for result in results:
        row = {
            "video_id": result.video_id,
            "window_index": result.window_index,
            "frame_start": result.frame_start,
            "frame_end": result.frame_end,
        }
        row.update(result.state.to_dict())
        rows.append(row)
    return pd.DataFrame(rows)


def vehicle_distance_breakdown_to_dataframe(results: list[WindowResult]) -> pd.DataFrame:
    """One row per (window, vehicle_id) -- the apportionment table Module 2
    COPERT distance-splitting needs."""
    rows = []
    for result in results:
        for vehicle_id, distance_km in result.vehicle_distance_km.items():
            rows.append({
                "video_id": result.video_id,
                "window_index": result.window_index,
                "vehicle_id": vehicle_id,
                "distance_km_in_window": distance_km,
            })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract sliding-window traffic-state features from a Module 1 trajectory CSV."
    )
    parser.add_argument("--trajectory-csv", required=True)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--window-length", type=float, default=DEFAULT_WINDOW_LENGTH_S)
    parser.add_argument("--stride", type=float, default=DEFAULT_STRIDE_S)
    parser.add_argument("--output-dir", default="outputs/module1_windows")
    args = parser.parse_args()

    results = extract_windows(
        args.trajectory_csv, args.fps, args.window_length, args.stride
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    windows_to_dataframe(results).to_csv(output_dir / "windows.csv", index=False)
    vehicle_distance_breakdown_to_dataframe(results).to_csv(
        output_dir / "window_vehicle_distances.csv", index=False
    )
    print(f"Extracted {len(results)} windows -> {output_dir}")


if __name__ == "__main__":
    main()
