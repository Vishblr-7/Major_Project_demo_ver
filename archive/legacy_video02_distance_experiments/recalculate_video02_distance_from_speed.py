"""Recalculate Video 02 trajectory step distances from speed and known FPS."""

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Video 02 FPS-derived distance input.")
    parser.add_argument(
        "--input",
        default="outputs/copert_video02/video02_emission_training.csv",
    )
    parser.add_argument(
        "--output",
        default="outputs/copert_video02/video02_emission_ready_v2.csv",
    )
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()
    if args.fps <= 0:
        raise ValueError("FPS must be positive.")

    frame = pd.read_csv(args.input)
    required = {"video_id", "vehicle_id", "speed_kmph"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    frame["speed_kmph"] = pd.to_numeric(frame["speed_kmph"], errors="coerce").fillna(0.0)

    # km/h -> km/s -> kilometres travelled in one 1/FPS-second step.
    frame["distance_km"] = (frame["speed_kmph"] / (3600.0 * args.fps)).clip(lower=0.0)
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
            total_distance_km=("distance_km", "sum"),
        )
        .reset_index()
    )
    print("Distance recalculation complete")
    print("--------------------------------")
    print(f"FPS: {args.fps}")
    print(f"Records: {len(frame):,}")
    print("\nVehicle distance summary:")
    print(vehicle_summary.to_string(index=False))
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()
