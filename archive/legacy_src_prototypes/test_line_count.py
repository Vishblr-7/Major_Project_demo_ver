"""Verify Supervision LineZone vehicle counting on the configured video."""

import cv2
import supervision as sv
from ultralytics import YOLO

from config import CONFIDENCE, LINE_END, LINE_START, MODEL_PATH, VEHICLE_CLASSES, VIDEO_PATH

START_FRAME = 700
MAX_FRAMES = 180


def main() -> None:
    model = YOLO(MODEL_PATH)
    tracker = sv.ByteTrack()
    line_zone = sv.LineZone(
        start=sv.Point(LINE_START[0], LINE_START[1]),
        end=sv.Point(LINE_END[0], LINE_END[1]),
        triggering_anchors=(sv.Position.CENTER,),
    )
    vehicle_counts = {vehicle: 0 for vehicle in VEHICLE_CLASSES}
    counted_ids = set()

    capture = cv2.VideoCapture(VIDEO_PATH)
    if not capture.isOpened():
        raise FileNotFoundError(f"Unable to open input video: {VIDEO_PATH}")
    capture.set(cv2.CAP_PROP_POS_FRAMES, START_FRAME)

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
            crossed_in, crossed_out = line_zone.trigger(detections)

            for tracker_id, class_id, entered, exited in zip(
                detections.tracker_id,
                detections.class_id,
                crossed_in,
                crossed_out,
            ):
                vehicle_id = int(tracker_id)
                class_name = model.names[int(class_id)]
                if (entered or exited) and vehicle_id not in counted_ids:
                    counted_ids.add(vehicle_id)
                    vehicle_counts[class_name] += 1
    finally:
        capture.release()

    print(f"IN count: {line_zone.in_count}")
    print(f"OUT count: {line_zone.out_count}")
    print(f"Unique vehicles counted: {sum(vehicle_counts.values())}")
    for vehicle, count in vehicle_counts.items():
        print(f"{vehicle}: {count}")

    if not counted_ids:
        raise RuntimeError("No vehicles crossed the configured counting line.")


if __name__ == "__main__":
    main()
