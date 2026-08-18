"""Task (104-video scale-up): build an enriched windowed emission-rate training dataset
across all 104 INDRA videos, extending Task C's original 30-video builder
(build_training_dataset.py, left untouched as the baseline's dataset builder).

Adds, on top of the original 14 TrafficState features:
  - per-class distance traveled inside the window (car/motorcycle/bus/truck/
    autorickshaw/bicycle _distance_km), and total_distance_km_in_window -- a much
    more direct emission proxy than raw counts, since EF is a g/km rate.
  - vehicle-class composition ratios (car_ratio, motorcycle_ratio, bus_ratio,
    truck_ratio) -- composition, not just volume, of a window's traffic.
  - temporal features: window_position_frac (how far into its video's clip this
    window falls) and prev_total_vehicles / delta_total_vehicles (a simple lag
    feature capturing whether traffic is building up or dissipating).

Same target definition as Task C: <pollutant>_rate_g_per_s = window total g /
actual window duration in seconds.
"""

import argparse
from pathlib import Path

import pandas as pd

from module1_traffic.windows import (
    DEFAULT_STRIDE_S,
    DEFAULT_WINDOW_LENGTH_S,
    extract_windows,
    vehicle_distance_breakdown_to_dataframe,
    windows_to_dataframe,
)

POLLUTANTS = ("CO2", "NOx", "CO", "PM25")
VEHICLE_CLASSES = ("car", "motorcycle", "bus", "truck", "autorickshaw", "bicycle")


def build_training_dataset(
    manifest_path: str | Path,
    vehicle_emissions_path: str | Path,
    window_length_s: float = DEFAULT_WINDOW_LENGTH_S,
    stride_s: float = DEFAULT_STRIDE_S,
) -> pd.DataFrame:
    manifest = pd.read_csv(manifest_path)
    emissions = pd.read_csv(vehicle_emissions_path)
    ef_columns = ["video_id", "vehicle_id"] + [f"{p}_EF_g_per_km" for p in POLLUTANTS]
    emissions = emissions[ef_columns]

    manifest_dir = Path(manifest_path).parent
    window_rows = []
    for record in manifest.itertuples(index=False):
        if record.status != "INCLUDED":
            continue
        video_id = record.video_id
        trajectory_path = manifest_dir / "individual_runs" / video_id / f"{video_id}_trajectory.csv"
        results = extract_windows(
            trajectory_path, fps=float(record.fps),
            window_length_s=window_length_s, stride_s=stride_s,
            calibration_profile=str(record.calibration_profile),
        )
        if not results:
            continue
        state_df = windows_to_dataframe(results)
        distance_df = vehicle_distance_breakdown_to_dataframe(results)

        # Per-class distance breakdown: join the raw trajectory's (video_id,
        # vehicle_id) -> vehicle_type (majority class per track, matching the
        # same class-flicker handling copert_emission_engine.py uses) onto the
        # per-window vehicle distance, then pivot-sum by class.
        trajectory = pd.read_csv(trajectory_path)
        track_class = (
            trajectory.groupby("vehicle_id")["vehicle_type"]
            .agg(lambda values: values.astype(str).str.lower().mode().iat[0])
        )
        distance_df = distance_df.merge(
            track_class.rename("vehicle_type"), left_on="vehicle_id", right_index=True, how="left"
        )
        class_distance = (
            distance_df.pivot_table(
                index="window_index", columns="vehicle_type",
                values="distance_km_in_window", aggfunc="sum", fill_value=0.0,
            )
        )
        for vehicle_class in VEHICLE_CLASSES:
            if vehicle_class not in class_distance.columns:
                class_distance[vehicle_class] = 0.0
        class_distance = class_distance[list(VEHICLE_CLASSES)].add_suffix("_distance_km")
        class_distance["total_distance_km_in_window"] = class_distance.sum(axis=1)
        class_distance = class_distance.reindex(state_df["window_index"], fill_value=0.0).reset_index()

        # Emission totals (same approach as Task C's builder).
        joined = distance_df.merge(emissions, on=["video_id", "vehicle_id"], how="left")
        for pollutant in POLLUTANTS:
            ef_col = f"{pollutant}_EF_g_per_km"
            joined[f"{pollutant}_g"] = joined["distance_km_in_window"] * joined[ef_col].fillna(0.0)
        window_totals = (
            joined.groupby("window_index")[[f"{p}_g" for p in POLLUTANTS]].sum()
            .reindex(state_df["window_index"], fill_value=0.0)
            .reset_index()
        )

        merged = state_df.merge(window_totals, on="window_index", how="left")
        merged = merged.merge(class_distance, on="window_index", how="left")
        for pollutant in POLLUTANTS:
            merged[f"{pollutant}_g"] = merged[f"{pollutant}_g"].fillna(0.0)

        duration_s = (merged["frame_end"] - merged["frame_start"] + 1) / float(record.fps)
        for pollutant in POLLUTANTS:
            merged[f"{pollutant}_rate_g_per_s"] = merged[f"{pollutant}_g"] / duration_s
            merged.drop(columns=[f"{pollutant}_g"], inplace=True)

        # Composition ratios (guard against a zero-vehicle window).
        safe_total = merged["total_vehicles"].replace(0, pd.NA)
        for vehicle_class in ("car", "motorcycle", "bus", "truck"):
            merged[f"{vehicle_class}_ratio"] = (merged[f"{vehicle_class}_count"] / safe_total).fillna(0.0)

        # Temporal features: position within the clip, and a same-video lag.
        max_frame = float(trajectory["frame_number"].max())
        merged["window_position_frac"] = merged["frame_start"] / max_frame if max_frame > 0 else 0.0
        merged = merged.sort_values("window_index")
        merged["prev_total_vehicles"] = merged["total_vehicles"].shift(1).fillna(merged["total_vehicles"].iloc[0])
        merged["delta_total_vehicles"] = merged["total_vehicles"] - merged["prev_total_vehicles"]

        window_rows.append(merged)

    return pd.concat(window_rows, ignore_index=True) if window_rows else pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the enriched 104-video windowed emission-rate training dataset."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--vehicle-emissions", required=True)
    parser.add_argument("--window-length", type=float, default=DEFAULT_WINDOW_LENGTH_S)
    parser.add_argument("--stride", type=float, default=DEFAULT_STRIDE_S)
    parser.add_argument("--output", default="module2_emission/xgboost/training_dataset_104.csv")
    args = parser.parse_args()

    dataset = build_training_dataset(
        args.manifest, args.vehicle_emissions, args.window_length, args.stride
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)
    if dataset.empty:
        print(f"WARNING: 0 windows produced -> {output_path} written empty.")
    else:
        print(f"Windows: {len(dataset):,} across {dataset['video_id'].nunique()} videos -> {output_path}")


if __name__ == "__main__":
    main()
