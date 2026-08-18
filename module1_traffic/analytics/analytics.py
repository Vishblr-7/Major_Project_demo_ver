"""Traffic analytics calculations and CSV persistence."""

import csv
from pathlib import Path
from typing import Mapping


def calculate_analytics(
    vehicle_counts: Mapping[str, int],
    vehicle_speeds: Mapping[int, float],
    elapsed_minutes: float,
    road_capacity: float,
    max_speed: float,
    current_vehicles: int | None = None,
) -> dict[str, float | int | str]:
    """Calculate flow from crossings and density from the current ROI occupancy."""
    total = sum(vehicle_counts.values())
    valid_speeds = list(vehicle_speeds.values())
    average_speed = sum(valid_speeds) / len(valid_speeds) if valid_speeds else 0.0

    percentages = {
        f"{vehicle}_percentage": (count / total) * 100 if total else 0.0
        for vehicle, count in vehicle_counts.items()
    }
    traffic_flow = total / elapsed_minutes if elapsed_minutes > 0 else 0.0
    traffic_flow_hour = traffic_flow * 60
    density_count = total if current_vehicles is None else current_vehicles
    traffic_density = density_count / road_capacity if road_capacity > 0 else 0.0
    congestion_index = traffic_density * (1 - average_speed / max_speed) if max_speed > 0 else 0.0

    if congestion_index < 0.30:
        congestion_level = "LOW"
    elif congestion_index < 0.60:
        congestion_level = "MEDIUM"
    else:
        congestion_level = "HIGH"

    return {
        "elapsed_minutes": elapsed_minutes,
        "total_vehicles": total,
        "current_vehicles": density_count,
        "average_speed_kmph": average_speed,
        "traffic_flow_per_minute": traffic_flow,
        "traffic_flow_per_hour": traffic_flow_hour,
        "traffic_density": traffic_density,
        "congestion_index": congestion_index,
        "congestion_level": congestion_level,
        **vehicle_counts,
        **percentages,
    }


def save_analytics(csv_path: str, analytics: Mapping[str, float | int | str]) -> None:
    """Append one analysis summary to a CSV database, including a header once."""
    output_path = Path(csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not output_path.exists() or output_path.stat().st_size == 0

    with output_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(analytics.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(analytics)
