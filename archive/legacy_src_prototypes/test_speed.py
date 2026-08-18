"""Verify per-vehicle speed estimation over a sample of the input video."""

import cv2
import supervision as sv
from ultralytics import YOLO

from config import CONFIDENCE, FPS, MODEL_PATH, PIXELS_PER_METER, VEHICLE_CLASSES, VIDEO_PATH

MAX_FRAMES = 60


def main() -> None:
    model = YOLO(MODEL_PATH)
    tracker = sv.ByteTrack()
    capture = cv2.VideoCapture(VIDEO_PATH)
    if not capture.isOpened():
        raise FileNotFoundError(f"Unable to open input video: {VIDEO_PATH}")

    fps = capture.get(cv2.CAP_PROP_FPS) or FPS
    previous_positions = {}
    vehicle_speeds = {}

    try:
        for _ in range(MAX_FRAMES):
            success, frame = capture.read()
            if not success:
                break

            result = model(frame, conf=CONFIDENCE, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(result)
            vehicle_mask = [
                model.names[int(class_id)] in VEHICLE_CLASSES
                for class_id in detections.class_id
            ]
            detections = tracker.update_with_detections(detections[vehicle_mask])

            for box, tracker_id in zip(detections.xyxy, detections.tracker_id):
                x1, y1, x2, y2 = box
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                vehicle_id = int(tracker_id)

                if vehicle_id in previous_positions:
                    prev_x, prev_y = previous_positions[vehicle_id]
                    pixel_distance = (
                        (center_x - prev_x) ** 2 + (center_y - prev_y) ** 2
                    ) ** 0.5
                    distance_meters = pixel_distance / PIXELS_PER_METER
                    speed_mps = distance_meters / (1 / fps)
                    vehicle_speeds[vehicle_id] = speed_mps * 3.6

                previous_positions[vehicle_id] = (center_x, center_y)
    finally:
        capture.release()

    if not vehicle_speeds:
        raise RuntimeError("No tracked vehicle had enough frames for speed estimation.")

    print(f"Speed estimation verified at {fps:.2f} FPS:")
    for vehicle_id, speed_kmph in sorted(vehicle_speeds.items()):
        print(f"ID {vehicle_id}: {speed_kmph:.1f} km/h")


if __name__ == "__main__":
    main()
