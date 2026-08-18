"""Create a clean, per-video emission-training trajectory CSV from Module 1."""

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare one INDRA video for the COPERT engine.")
    parser.add_argument(
        "--input",
        default="outputs/module1_distance_enriched/INDRA_COPERT_DATASET_WITH_DISTANCE.csv",
    )
    parser.add_argument("--video-id", default="video2")
    parser.add_argument(
        "--output",
        default="outputs/copert_video02/video02_emission_training.csv",
    )
    args = parser.parse_args()
    frame = pd.read_csv(args.input)
    required = {
        "video_id", "vehicle_id", "vehicle_type", "timestamp", "speed_kmph",
        "acceleration_mps2", "traffic_density_vehicles_per_100m2", "world_x_m",
        "world_y_m", "distance_km", "in_roi", "emission_eligible",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Distance-enriched Module 1 input is missing: {missing}")
    selected = frame.loc[
        (frame["video_id"] == args.video_id)
        & (frame["emission_eligible"] == 1)
        & (frame["in_roi"] == 1)
        & (frame["vehicle_type"].astype(str).str.lower() != "bicycle")
    ].copy()
    selected = selected.sort_values(["vehicle_id", "frame_number"])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(output, index=False)
    print(f"Prepared rows: {len(selected):,}")
    print(f"Vehicle tracks: {selected[['video_id', 'vehicle_id']].drop_duplicates().shape[0]}")
    print(f"Trajectory CSV: {output}")


if __name__ == "__main__":
    main()
