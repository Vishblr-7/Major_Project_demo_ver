"""Verify that ByteTrack assigns vehicle IDs across consecutive video frames."""

import cv2
from ultralytics import YOLO

from config import CONFIDENCE, MODEL_PATH, VIDEO_PATH
from tracker import VehicleTracker

MAX_FRAMES = 60


def main() -> None:
    model = YOLO(MODEL_PATH)
    tracker = VehicleTracker(model.names)
    capture = cv2.VideoCapture(VIDEO_PATH)
    if not capture.isOpened():
        raise FileNotFoundError(f"Unable to open input video: {VIDEO_PATH}")

    tracked_vehicle_count = 0
    try:
        for frame_number in range(1, MAX_FRAMES + 1):
            success, frame = capture.read()
            if not success:
                break

            yolo_result = model(frame, conf=CONFIDENCE, verbose=False)[0]
            tracked_vehicles = tracker.update(yolo_result)

            for vehicle in tracked_vehicles:
                tracked_vehicle_count += 1
                print(
                    f"Frame {frame_number}: "
                    f"ID={vehicle['vehicle_id']}, "
                    f"class={vehicle['vehicle_class']}, "
                    f"confidence={vehicle['confidence']:.2f}, "
                    f"box={vehicle['bounding_box']}"
                )
    finally:
        capture.release()

    if tracked_vehicle_count == 0:
        raise RuntimeError("No tracked vehicles were returned by ByteTrack.")

    print(f"Tracking verified: {tracked_vehicle_count} tracked vehicles returned.")


if __name__ == "__main__":
    main()
