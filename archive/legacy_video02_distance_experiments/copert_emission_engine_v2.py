"""COPERT v2: aggregate true trajectory steps into one auditable vehicle record."""

import argparse
from pathlib import Path

import pandas as pd


MIN_TRACK_SAMPLES = 10
YOLO_TO_COPERT = {
    0: "Passenger Cars", 1: "L-Category", 2: "Buses", 3: "Heavy Duty Trucks",
    4: None, 5: None,
}
NAME_TO_ID = {
    "car": 0, "motorcycle": 1, "bus": 2, "truck": 3,
    "autorickshaw": 4, "bicycle": 5,
}
COPERT_EF = {
    "Passenger Cars": {"CO2": 149.1856, "NOx": 0.0414, "CO": 0.3529, "PM25": 0.0155},
    "L-Category": {"CO2": 73.1875, "NOx": 0.0311, "CO": 0.4329, "PM25": 0.0069},
    "Buses": {"CO2": 924.2413, "NOx": 1.2932, "CO": 0.3836, "PM25": 0.0639},
    "Heavy Duty Trucks": {"CO2": 1123.5121, "NOx": 0.3130, "CO": 0.0769, "PM25": 0.0702},
}


def dominant_value(values: pd.Series):
    """Select a track's most frequent classification, breaking ties consistently."""
    mode = values.dropna().mode()
    return mode.iat[0] if not mode.empty else pd.NA


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the COPERT v2 vehicle-level emission engine.")
    parser.add_argument(
        "--input",
        default="outputs/copert_video02/video02_emissionv2_ready.csv",
    )
    parser.add_argument("--output-dir", default="outputs/copert_video02_v2")
    args = parser.parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frame = pd.read_csv(input_path)
    required = {
        "video_id", "vehicle_id", "vehicle_type", "distance_km",
        "vehicle_total_distance_km",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    frame["distance_km"] = pd.to_numeric(frame["distance_km"], errors="coerce").fillna(0.0)
    frame["vehicle_total_distance_km"] = pd.to_numeric(
        frame["vehicle_total_distance_km"], errors="coerce"
    )
    frame["yolo_class"] = frame["vehicle_type"].astype(str).str.lower().str.strip().map(NAME_TO_ID)

    vehicle_df = (
        frame.groupby(["video_id", "vehicle_id"], dropna=False)
        .agg(
            track_samples=("vehicle_id", "size"),
            distance_km=("distance_km", "sum"),
            expected_total_distance_km=("vehicle_total_distance_km", "max"),
            vehicle_type=("vehicle_type", dominant_value),
            yolo_class=("yolo_class", dominant_value),
        )
        .reset_index()
    )
    vehicle_df["copert_category"] = vehicle_df["yolo_class"].map(YOLO_TO_COPERT)
    vehicle_df["distance_consistent"] = (
        vehicle_df["distance_km"] - vehicle_df["expected_total_distance_km"]
    ).abs().le(1e-6)
    vehicle_df["exclusion_reason"] = ""
    vehicle_df.loc[vehicle_df["track_samples"] < MIN_TRACK_SAMPLES, "exclusion_reason"] = "SHORT_TRACK"
    vehicle_df.loc[
        vehicle_df["copert_category"].isna() & vehicle_df["exclusion_reason"].eq(""),
        "exclusion_reason",
    ] = "NO_COPERT_CATEGORY"
    vehicle_df.loc[
        vehicle_df["distance_km"].le(0) & vehicle_df["exclusion_reason"].eq(""),
        "exclusion_reason",
    ] = "INVALID_DISTANCE"
    vehicle_df.loc[
        ~vehicle_df["distance_consistent"] & vehicle_df["exclusion_reason"].eq(""),
        "exclusion_reason",
    ] = "DISTANCE_MISMATCH"
    vehicle_df["emission_eligible"] = vehicle_df["exclusion_reason"].eq("")

    for pollutant in ("CO2", "NOx", "CO", "PM25"):
        vehicle_df[f"{pollutant}_EF_g_per_km"] = 0.0
        vehicle_df[f"{pollutant}_g"] = 0.0
    for index, row in vehicle_df.loc[vehicle_df["emission_eligible"]].iterrows():
        for pollutant, factor in COPERT_EF[row["copert_category"]].items():
            vehicle_df.at[index, f"{pollutant}_EF_g_per_km"] = factor
            vehicle_df.at[index, f"{pollutant}_g"] = row["distance_km"] * factor

    vehicle_output = output_dir / "video02_vehicle_emissions.csv"
    summary_output = output_dir / "video02_emission_summary.csv"
    excluded_output = output_dir / "video02_emission_excluded.csv"
    vehicle_df.to_csv(vehicle_output, index=False)
    excluded = vehicle_df.loc[~vehicle_df["emission_eligible"]].copy()
    excluded.to_csv(excluded_output, index=False)
    summary = (
        vehicle_df.loc[vehicle_df["emission_eligible"]]
        .groupby("video_id", as_index=False)
        .agg(
            vehicles=("vehicle_id", "nunique"), distance_km=("distance_km", "sum"),
            CO2_g=("CO2_g", "sum"), NOx_g=("NOx_g", "sum"),
            CO_g=("CO_g", "sum"), PM25_g=("PM25_g", "sum"),
        )
    )
    summary.to_csv(summary_output, index=False)
    print("COPERT EMISSION ENGINE V2 — VIDEO 02")
    print(f"Total tracked vehicles: {len(vehicle_df)}")
    print(f"Emission eligible: {vehicle_df['emission_eligible'].sum()}")
    print(f"Excluded: {len(excluded)}")
    print(f"Vehicle output: {vehicle_output}")
    print(f"Summary output: {summary_output}")
    print(f"Excluded output: {excluded_output}")


if __name__ == "__main__":
    main()
