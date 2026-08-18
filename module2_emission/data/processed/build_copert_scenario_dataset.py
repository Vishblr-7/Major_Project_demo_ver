"""Create a transparent scenario-assumption layer for COPERT inputs.

This script never claims that fuel, engine class, or emission standard was
measured by YOLO. Those fields remain explicit scenario placeholders until a
documented fleet scenario is selected.
"""

import argparse
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "video_id", "vehicle_id", "vehicle_type", "timestamp", "speed_kmph",
        "acceleration_mps2", "world_x_m", "world_y_m",
    "traffic_density_vehicles_per_100m2", "stop_duration_s", "distance_km", "in_roi",
]

VEHICLE_MAPPING = {
    "car": ("PASSENGER_CAR", "Passenger cars"),
    "motorcycle": ("MOTORCYCLE", "Motorcycles"),
    "autorickshaw": ("THREE_WHEELER", "Three-wheelers"),
    "bus": ("BUS", "Heavy-duty vehicles / buses"),
    "truck": ("HEAVY_DUTY_TRUCK", "Heavy-duty vehicles"),
}


def operating_state(speed: float) -> str:
    if speed < 1:
        return "IDLE"
    if speed < 10:
        return "LOW_SPEED"
    if speed < 30:
        return "URBAN_MOVING"
    if speed < 50:
        return "MODERATE_SPEED"
    return "HIGH_SPEED"


def acceleration_state(acceleration: float) -> str:
    if acceleration < -0.5:
        return "DECELERATION"
    if acceleration > 0.5:
        return "ACCELERATION"
    return "CRUISING"


def traffic_condition(density: float) -> str:
    if density < 2:
        return "LOW"
    if density < 5:
        return "MEDIUM"
    if density < 10:
        return "HIGH"
    return "CONGESTED"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build transparent COPERT scenario inputs.")
    parser.add_argument(
        "--input",
        default="outputs/module1_indra_batch/INDRA_COPERT_DATASET.csv",
        help="Merged quality-approved Module 1 observations.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/module2_copert_scenario",
        help="New directory for COPERT-ready data and audit artifacts.",
    )
    parser.add_argument(
        "--include-non-roi",
        action="store_true",
        help="Keep non-ROI observations (default: calibrated ROI observations only).",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(input_path)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required Module 1 columns: {missing}")

    audit = [{"stage": "module1_quality_approved_input", "records": len(frame)}]
    if not args.include_non_roi:
        frame = frame.loc[frame["in_roi"] == 1].copy()
    audit.append({"stage": "calibrated_roi_filter", "records": len(frame)})

    frame["vehicle_type"] = frame["vehicle_type"].astype(str).str.lower().str.strip()
    before_bicycle_filter = len(frame)
    frame = frame.loc[frame["vehicle_type"] != "bicycle"].copy()
    audit.append({
        "stage": "remove_non_motorized_bicycles",
        "records": len(frame),
        "removed": before_bicycle_filter - len(frame),
    })

    for column in (
        "speed_kmph", "acceleration_mps2", "traffic_density_vehicles_per_100m2",
        "stop_duration_s", "world_x_m", "world_y_m", "distance_km",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    before_numeric_filter = len(frame)
    frame = frame.dropna(subset=(
        "speed_kmph", "acceleration_mps2", "traffic_density_vehicles_per_100m2",
        "stop_duration_s", "world_x_m", "world_y_m",
    )).copy()
    audit.append({
        "stage": "remove_missing_numeric_observations",
        "records": len(frame),
        "removed": before_numeric_filter - len(frame),
    })

    before_dynamics_filter = len(frame)
    frame = frame.loc[
        frame["speed_kmph"].between(0, 80)
        & frame["acceleration_mps2"].between(-5, 5)
    ].copy()
    audit.append({
        "stage": "speed_and_acceleration_sanity_filter",
        "records": len(frame),
        "removed": before_dynamics_filter - len(frame),
    })

    frame["copert_category"] = frame["vehicle_type"].map(
        lambda value: VEHICLE_MAPPING.get(value, ("UNKNOWN", "UNKNOWN"))[0]
    )
    frame["copert_group"] = frame["vehicle_type"].map(
        lambda value: VEHICLE_MAPPING.get(value, ("UNKNOWN", "UNKNOWN"))[1]
    )
    unknown_types = sorted(
        frame.loc[frame["copert_category"] == "UNKNOWN", "vehicle_type"].unique()
    )
    if unknown_types:
        raise ValueError(f"Unknown vehicle types need a COPERT mapping: {unknown_types}")
    audit.append({"stage": "vehicle_to_copert_category_mapping", "records": len(frame)})

    frame["operating_state"] = frame["speed_kmph"].map(operating_state)
    frame["is_stopped"] = (frame["speed_kmph"] < 1.0).astype(int)
    frame["acceleration_state"] = frame["acceleration_mps2"].map(acceleration_state)
    frame["traffic_condition"] = frame["traffic_density_vehicles_per_100m2"].map(
        traffic_condition
    )

    # These values are deliberately explicit, non-measured COPERT inputs.
    frame["fuel_type"] = "TO_BE_DEFINED"
    frame["emission_standard"] = "TO_BE_DEFINED"
    frame["engine_class"] = "TO_BE_DEFINED"
    frame["fuel_type_source"] = "SCENARIO_ASSUMPTION"
    frame["emission_standard_source"] = "SCENARIO_ASSUMPTION"
    frame["engine_size_source"] = "SCENARIO_ASSUMPTION"
    frame["data_source"] = "INDRA"
    frame["physics_model"] = "COPERT"
    frame["copert_label_status"] = "READY_FOR_COPERT"

    final_columns = [
        "video_id", "vehicle_id", "timestamp", "vehicle_type", "copert_category",
        "copert_group", "speed_kmph", "acceleration_mps2", "stop_duration_s",
        "is_stopped", "operating_state", "acceleration_state",
        "traffic_density_vehicles_per_100m2", "traffic_condition", "world_x_m",
        "world_y_m", "distance_km", "in_roi", "fuel_type", "emission_standard", "engine_class",
        "fuel_type_source", "emission_standard_source", "engine_size_source",
        "data_source", "physics_model", "copert_label_status",
    ]
    frame = frame.loc[:, final_columns]
    output_path = output_dir / "INDRA_COPERT_INPUT.csv"
    frame.to_csv(output_path, index=False)

    assumptions = pd.DataFrame([
        {
            "vehicle_type": vehicle_type,
            "copert_category": category,
            "copert_group": group,
            "fuel_type": "TO_BE_DEFINED",
            "emission_standard": "TO_BE_DEFINED",
            "engine_class": "TO_BE_DEFINED",
            "assumption_status": "SCENARIO_ASSUMPTION",
            "note": "Not measured by INDRA/YOLO; set from a documented fleet scenario.",
        }
        for vehicle_type, (category, group) in VEHICLE_MAPPING.items()
    ])
    assumptions.to_csv(output_dir / "COPERT_SCENARIO_ASSUMPTIONS.csv", index=False)
    pd.DataFrame(audit).fillna(0).to_csv(output_dir / "COPERT_SCENARIO_AUDIT.csv", index=False)

    print(f"COPERT-ready records: {len(frame):,}")
    print(f"Videos: {frame['video_id'].nunique()}")
    print(f"Vehicles: {frame[['video_id', 'vehicle_id']].drop_duplicates().shape[0]}")
    print(f"Dataset: {output_path}")


if __name__ == "__main__":
    main()
