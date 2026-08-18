"""Add longitudinal cumulative distance to frozen Module 1 trajectory outputs."""

import argparse
from pathlib import Path

import pandas as pd


def add_longitudinal_distance(frame: pd.DataFrame, fps: float) -> pd.DataFrame:
    """Add cumulative distance per video/track from road-world longitudinal motion."""
    frame = frame.sort_values(["video_id", "vehicle_id", "frame_number"]).copy()
    frame["world_y_m"] = pd.to_numeric(frame["world_y_m"], errors="coerce")
    frame["frame_number"] = pd.to_numeric(frame["frame_number"], errors="coerce")
    frame["distance_km"] = 0.0
    for _, indices in frame.groupby(["video_id", "vehicle_id"], sort=False).groups.items():
        group = frame.loc[indices]
        previous_y = None
        previous_frame = None
        cumulative_km = 0.0
        for index, row in group.iterrows():
            current_y = row["world_y_m"]
            current_frame = row["frame_number"]
            if pd.notna(current_y) and previous_y is not None and current_frame > previous_frame:
                dt = (current_frame - previous_frame) / fps
                step_m = abs(current_y - previous_y)
                step_speed_kmph = step_m / dt * 3.6
                if 0 <= step_speed_kmph <= 80.0:
                    cumulative_km += step_m / 1000.0
            frame.at[index, "distance_km"] = round(cumulative_km, 6)
            previous_y = current_y
            previous_frame = current_frame
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich Module 1 emissions rows with distance_km.")
    parser.add_argument("--module1-dir", default="outputs/module1_indra_batch")
    parser.add_argument("--output-dir", default="outputs/module1_distance_enriched")
    args = parser.parse_args()
    module1_dir = Path(args.module1_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(module1_dir / "module1_manifest.csv")
    all_rows = []
    for record in manifest.itertuples(index=False):
        if record.status != "INCLUDED":
            continue
        video_id = record.video_id
        trajectory_path = module1_dir / "individual_runs" / video_id / f"{video_id}_trajectory.csv"
        raw = pd.read_csv(trajectory_path)
        enriched = add_longitudinal_distance(raw, float(record.fps))
        enriched.to_csv(output_dir / f"{video_id}_trajectory_with_distance.csv", index=False)
        approved = enriched.loc[enriched["emission_eligible"] == 1].copy()
        all_rows.append(approved)
    merged = pd.concat(all_rows, ignore_index=True)
    merged_path = output_dir / "INDRA_COPERT_DATASET_WITH_DISTANCE.csv"
    merged.to_csv(merged_path, index=False)
    track_distances = (
        merged.groupby(["video_id", "vehicle_id", "vehicle_type"], as_index=False)["distance_km"]
        .max()
        .rename(columns={"distance_km": "track_distance_km"})
    )
    track_distances.to_csv(output_dir / "INDRA_TRACK_DISTANCES.csv", index=False)
    print(f"Distance-enriched rows: {len(merged):,}")
    print(f"Vehicle tracks: {len(track_distances):,}")
    print(f"Dataset: {merged_path}")


if __name__ == "__main__":
    main()
