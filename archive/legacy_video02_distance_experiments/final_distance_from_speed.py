"""Calculate Video 02 step distances from speed and actual frame gaps."""

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Create final frame-gap-aware emission input.")
    parser.add_argument(
        "--input",
        default="outputs/copert_video02/video02_emission_training.csv",
    )
    parser.add_argument(
        "--output",
        default="outputs/copert_video02/video02_emission_ready_final.csv",
    )
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()
    if args.fps <= 0:
        raise ValueError("FPS must be positive.")

    frame = pd.read_csv(args.input)
    required = {"video_id", "vehicle_id", "frame_number", "speed_kmph"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    frame["speed_kmph"] = pd.to_numeric(frame["speed_kmph"], errors="coerce").fillna(0.0)
    frame["frame_number"] = pd.to_numeric(frame["frame_number"], errors="coerce")
    frame = frame.dropna(subset=["frame_number"]).copy()
    frame = frame.sort_values(["video_id", "vehicle_id", "frame_number"]).reset_index(drop=True)

    frame["frame_gap"] = frame.groupby(["video_id", "vehicle_id"])["frame_number"].diff()
    frame["frame_gap"] = frame["frame_gap"].fillna(1).clip(lower=0)

    # speed km/h -> km/s; elapsed seconds = frame_gap / FPS.
    frame["distance_km"] = (
        frame["speed_kmph"] / 3600.0 * frame["frame_gap"] / args.fps
    ).clip(lower=0.0)
    frame["vehicle_total_distance_km"] = frame.groupby(
        ["video_id", "vehicle_id"]
    )["distance_km"].transform("sum")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)

    vehicle_summary = (
        frame.groupby(["video_id", "vehicle_id"])
        .agg(
            samples=("vehicle_id", "size"),
            mean_speed_kmph=("speed_kmph", "mean"),
            max_speed_kmph=("speed_kmph", "max"),
            total_distance_km=("distance_km", "sum"),
        )
        .reset_index()
    )
    print("FINAL DISTANCE CALCULATION")
    print(f"FPS: {args.fps}")
    print(f"Records: {len(frame):,}")
    print(f"Vehicles: {len(vehicle_summary):,}")
    print("Distance statistics:")
    print(vehicle_summary["total_distance_km"].describe())
    print("Vehicle summary:")
    print(vehicle_summary.to_string(index=False))
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
