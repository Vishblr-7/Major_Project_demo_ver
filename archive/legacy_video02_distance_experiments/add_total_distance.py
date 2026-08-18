"""Convert trajectory distance to per-step distance and add vehicle totals."""

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Add vehicle_total_distance_km to trajectory CSV.")
    parser.add_argument(
        "--input",
        default="outputs/copert_video02/video02_emission_training.csv",
    )
    parser.add_argument(
        "--output",
        default="outputs/copert_video02/video02_emission_ready.csv",
    )
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    required = {"video_id", "vehicle_id", "frame_number", "distance_km", "emission_eligible"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required trajectory columns: {missing}")
    frame["distance_km"] = pd.to_numeric(frame["distance_km"], errors="coerce").fillna(0.0)
    frame = frame.sort_values(["video_id", "vehicle_id", "frame_number"]).reset_index(drop=True)

    # The existing frozen input holds cumulative distance. Preserve it, then
    # expose a true per-trajectory-step distance for all downstream consumers.
    frame["distance_km_cumulative_source"] = frame["distance_km"]
    frame["distance_km"] = (
        frame.groupby(["video_id", "vehicle_id"])["distance_km_cumulative_source"]
        .diff()
        .fillna(frame["distance_km_cumulative_source"])
        .clip(lower=0.0)
    )
    frame["vehicle_total_distance_km"] = frame.groupby(
        ["video_id", "vehicle_id"]
    )["distance_km"].transform("sum")
    frame["emission_eligible"] = frame["emission_eligible"].astype(bool)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    totals = frame.groupby(["video_id", "vehicle_id"])["vehicle_total_distance_km"].first()
    print("Distance correction complete")
    print("--------------------------------")
    print(f"Input records : {len(frame):,}")
    print(f"Vehicles      : {frame[['video_id', 'vehicle_id']].drop_duplicates().shape[0]}")
    print("\nVehicle total-distance statistics:")
    print(totals.describe())
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()
