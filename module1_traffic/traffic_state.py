"""Shared rolling traffic-state snapshot, emitted by Module 1's live-camera and
batch paths alike, and consumed downstream by Modules 2/3/4 (emission
intelligence, signal/route optimization, and the live dashboard).

This is intentionally a plain dataclass with only primitive/Optional[float]
fields so it serializes trivially to CSV, JSON, or a message-queue payload
without extra glue code in the consuming modules.
"""

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class TrafficState:
    """One rolling snapshot of ROI traffic conditions.

    `average_speed_kmph`, `speed_std`, `mean_acceleration`, `acceleration_std`,
    `density_veh_per_100m2`, and `stopped_vehicle_ratio` are None whenever
    `data_quality != "FULL"` (e.g. COUNT_ONLY mode on an uncalibrated live
    camera resolution) -- callers must check `data_quality` before trusting
    any physical-unit field, not just check for None on one field at a time.
    """

    timestamp: str
    window_start: str
    window_end: str

    car_count: int = 0
    motorcycle_count: int = 0
    bus_count: int = 0
    truck_count: int = 0
    autorickshaw_count: int = 0
    bicycle_count: int = 0

    total_vehicles: int = 0
    current_vehicles: int = 0

    average_speed_kmph: Optional[float] = None
    speed_std: Optional[float] = None
    density_veh_per_100m2: Optional[float] = None
    flow_veh_per_min: Optional[float] = None
    roi_occupancy: Optional[float] = None
    mean_acceleration: Optional[float] = None
    acceleration_std: Optional[float] = None
    stopped_vehicle_ratio: Optional[float] = None

    # H1_1080P / H2_720P / H3_360P / UNSUPPORTED_COUNT_ONLY.
    calibration_profile: str = "UNKNOWN"
    # FULL: geometry valid, all physical fields trustworthy.
    # COUNT_ONLY: geometry invalid/unsupported resolution -- counts/classes
    #   only, all speed/density/flow fields are None by design, not zero.
    data_quality: str = "FULL"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def csv_fieldnames() -> list[str]:
        return list(TrafficState.__dataclass_fields__.keys())
