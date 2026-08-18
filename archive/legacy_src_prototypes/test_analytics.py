"""Verify traffic analytics calculations and CSV persistence."""

import csv
import tempfile
from pathlib import Path

from analytics import calculate_analytics, save_analytics


def main() -> None:
    vehicle_counts = {
        "car": 25,
        "motorcycle": 12,
        "bus": 2,
        "truck": 3,
        "bicycle": 1,
    }
    vehicle_speeds = {1: 30.0, 2: 50.0}
    analytics = calculate_analytics(
        vehicle_counts=vehicle_counts,
        vehicle_speeds=vehicle_speeds,
        elapsed_minutes=2.0,
        road_capacity=50,
        max_speed=60.0,
    )

    assert analytics["total_vehicles"] == 43
    assert analytics["average_speed_kmph"] == 40.0
    assert analytics["traffic_flow_per_hour"] == 1290.0
    assert analytics["traffic_density"] == 0.86
    assert analytics["congestion_level"] == "LOW"

    with tempfile.TemporaryDirectory() as directory:
        csv_path = Path(directory) / "traffic_analytics.csv"
        save_analytics(str(csv_path), analytics)
        with csv_path.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["total_vehicles"] == "43"
    assert rows[0]["congestion_level"] == "LOW"

    print("Traffic analytics verified successfully.")
    print(f"Total vehicles: {analytics['total_vehicles']}")
    print(f"Average speed: {analytics['average_speed_kmph']:.1f} km/h")
    print(f"Traffic flow: {analytics['traffic_flow_per_hour']:.1f} veh/hr")
    print(f"Traffic density: {analytics['traffic_density']:.2f}")
    print(f"Congestion level: {analytics['congestion_level']}")


if __name__ == "__main__":
    main()
