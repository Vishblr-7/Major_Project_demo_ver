"""ByteTrack wrapper that turns YOLO detections into tracked vehicle records."""

from typing import Any

import numpy as np
import supervision as sv

from config import VEHICLE_CLASSES


class VehicleTracker:
    """Filter YOLO detections to vehicles and assign stable ByteTrack IDs."""

    def __init__(self, class_names: dict[int, str]) -> None:
        self.class_names = class_names
        self.vehicle_class_ids = {
            class_id
            for class_id, class_name in class_names.items()
            if class_name in VEHICLE_CLASSES
        }
        self.tracker = sv.ByteTrack()

    def update(self, yolo_result: Any) -> list[dict[str, Any]]:
        """Return tracked vehicle IDs, boxes, classes, and confidences for one frame."""
        detections = sv.Detections.from_ultralytics(yolo_result)
        if detections.class_id is not None:
            detections = detections[
                np.isin(detections.class_id, list(self.vehicle_class_ids))
            ]

        tracked_detections = self.tracker.update_with_detections(detections)
        tracked_vehicles = []
        for xyxy, confidence, class_id, tracker_id in zip(
            tracked_detections.xyxy,
            tracked_detections.confidence,
            tracked_detections.class_id,
            tracked_detections.tracker_id,
        ):
            tracked_vehicles.append(
                {
                    "vehicle_id": int(tracker_id),
                    "bounding_box": tuple(map(int, xyxy)),
                    "vehicle_class": self.class_names[int(class_id)],
                    "confidence": float(confidence),
                }
            )
        return tracked_vehicles
