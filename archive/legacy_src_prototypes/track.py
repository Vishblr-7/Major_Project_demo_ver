"""Track vehicles across video frames using YOLO11s and ByteTrack."""

from pathlib import Path

import cv2
from ultralytics import YOLO

from config import (
    CONFIDENCE,
    MODEL_PATH,
    OUTPUT_VIDEO,
    VIDEO_PATH,
)
from tracker import VehicleTracker


def main() -> None:
    """Detect vehicles, assign persistent ByteTrack IDs, and save the result."""
    model = YOLO(MODEL_PATH)
    tracker = VehicleTracker(model.names)

    capture = cv2.VideoCapture(VIDEO_PATH)
    if not capture.isOpened():
        raise FileNotFoundError(f"Unable to open input video: {VIDEO_PATH}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    output_path = Path(OUTPUT_VIDEO)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (frame_width, frame_height),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Unable to create output video: {OUTPUT_VIDEO}")

    try:
        while True:
            success, frame = capture.read()
            if not success:
                break

            # Frame -> YOLO detections -> vehicle-only bounding boxes -> ByteTrack IDs.
            result = model(frame, conf=CONFIDENCE, verbose=False)[0]
            for vehicle in tracker.update(result):
                x1, y1, x2, y2 = vehicle["bounding_box"]
                label = (
                    f"{vehicle['vehicle_class']} ID: {vehicle['vehicle_id']} "
                    f"{vehicle['confidence']:.2f}"
                )

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    label,
                    (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

            writer.write(frame)
            cv2.imshow("Vehicle Tracking", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        capture.release()
        writer.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
