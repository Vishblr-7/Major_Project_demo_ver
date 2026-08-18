"""Task C: build the windowed emission-rate training dataset for Module 2's XGBoost model.

For each of the 30 INDRA videos, slides module1_traffic.windows.extract_windows() over its
per-frame trajectory CSV, joins the resulting per-window vehicle-distance breakdown against
Task B's outputs/copert_emissions/vehicle_emissions.csv (per-vehicle-track COPERT EF g/km,
already dominant-class-deduplicated and factor-table-sourced), and computes, per window:

    window_<pollutant>_g = sum over vehicles present in that window of
                            (distance_km_in_window * <pollutant>_EF_g_per_km)

for vehicles that have an approved COPERT category (car/motorcycle/bus/truck; autorickshaw and
bicycle contribute zero, matching docs/MODULE1_CONTRACT.md's emission-eligibility rule). The
regression target is a RATE (g/s), not the raw window total, so the model does not implicitly
learn window length as a feature -- divided by each window's actual duration
((frame_end - frame_start + 1) / fps), not the nominal window_length_s, since the final window
of a clip is legitimately shorter.

Output: module2_emission/xgboost/training_dataset.csv, one row per (video_id, window_index),
carrying every TrafficState feature column plus the four target rate columns.
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

        joined = distance_df.merge(
            emissions, on=["video_id", "vehicle_id"], how="left"
        )
        # Vehicles with no matching emissions row (autorickshaw, bicycle, or a
        # track that failed Module 1's quality gates) contribute zero -- they
        # were never emission-eligible in the first place, not a data error.
        for pollutant in POLLUTANTS:
            ef_col = f"{pollutant}_EF_g_per_km"
            joined[f"{pollutant}_g"] = joined["distance_km_in_window"] * joined[ef_col].fillna(0.0)

        window_totals = (
            joined.groupby("window_index")[[f"{p}_g" for p in POLLUTANTS]].sum()
            .reindex(state_df["window_index"], fill_value=0.0)
            .reset_index()
        )

        merged = state_df.merge(window_totals, on="window_index", how="left")
        for pollutant in POLLUTANTS:
            merged[f"{pollutant}_g"] = merged[f"{pollutant}_g"].fillna(0.0)

        duration_s = (merged["frame_end"] - merged["frame_start"] + 1) / float(record.fps)
        for pollutant in POLLUTANTS:
            merged[f"{pollutant}_rate_g_per_s"] = merged[f"{pollutant}_g"] / duration_s
            merged.drop(columns=[f"{pollutant}_g"], inplace=True)

        window_rows.append(merged)

    return pd.concat(window_rows, ignore_index=True) if window_rows else pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the windowed emission-rate training dataset for Module 2's XGBoost model."
    )
    parser.add_argument("--manifest", default="outputs/module1_indra_batch/module1_manifest.csv")
    parser.add_argument("--vehicle-emissions", default="outputs/copert_emissions/vehicle_emissions.csv")
    parser.add_argument("--window-length", type=float, default=DEFAULT_WINDOW_LENGTH_S)
    parser.add_argument("--stride", type=float, default=DEFAULT_STRIDE_S)
    parser.add_argument(
        "--output", default="module2_emission/xgboost/training_dataset.csv"
    )
    args = parser.parse_args()

    dataset = build_training_dataset(
        args.manifest, args.vehicle_emissions, args.window_length, args.stride
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)
    if dataset.empty:
        print(
            f"WARNING: 0 windows produced (no INCLUDED video in {args.manifest} yielded any "
            f"window) -> {output_path} written empty."
        )
    else:
        print(f"Windows: {len(dataset):,} across {dataset['video_id'].nunique()} videos -> {output_path}")


if __name__ == "__main__":
    main()
