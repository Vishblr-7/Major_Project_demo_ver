"""Verify the full tracking, counting, speed, and analytics pipeline on a video."""

import argparse

import cv2
import supervision as sv
from ultralytics import YOLO

from analytics import calculate_analytics
from config import (
    CONFIDENCE,
    FPS,
    LINE_END,
    LINE_START,
    MAX_SPEED,
    MODEL_PATH,
    PIXELS_PER_METER,
    ROAD_CAPACITY,
    VEHICLE_CLASSES,
    VIDEO_PATH,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start-frame",
        type=int,
        default=0,
        help="Frame to begin processing from (default: 0).",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Maximum frames to process; 0 processes the full video.",
    )
    args = parser.parse_args()

    model = YOLO(MODEL_PATH)
    tracker = sv.ByteTrack()
    line_zone = sv.LineZone(
        start=sv.Point(LINE_START[0], LINE_START[1]),
        end=sv.Point(LINE_END[0], LINE_END[1]),
        triggering_anchors=(sv.Position.CENTER,),
    )
    vehicle_counts = {vehicle: 0 for vehicle in VEHICLE_CLASSES}
    counted_ids = set()
    previous_positions = {}
    vehicle_speeds = {}

    capture = cv2.VideoCapture(VIDEO_PATH)
    if not capture.isOpened():
        raise FileNotFoundError(f"Unable to open input video: {VIDEO_PATH}")
    capture.set(cv2.CAP_PROP_POS_FRAMES, args.start_frame)
    fps = capture.get(cv2.CAP_PROP_FPS) or FPS
    processed_frames = 0

    try:
        while args.max_frames == 0 or processed_frames < args.max_frames:
            success, frame = capture.read()
            if not success:
                break
            processed_frames += 1

            result = model(frame, conf=CONFIDENCE, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(result)
            vehicle_mask = [
                model.names[int(class_id)] in VEHICLE_CLASSES
                for class_id in detections.class_id
            ]
            detections = tracker.update_with_detections(detections[vehicle_mask])
            crossed_in, crossed_out = line_zone.trigger(detections)

            for box, tracker_id, class_id, entered, exited in zip(
                detections.xyxy,
                detections.tracker_id,
                detections.class_id,
                crossed_in,
                crossed_out,
            ):
                vehicle_id = int(tracker_id)
                class_name = model.names[int(class_id)]
                x1, y1, x2, y2 = box
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)

                if vehicle_id in previous_positions:
                    prev_x, prev_y = previous_positions[vehicle_id]
                    pixel_distance = (
                        (center_x - prev_x) ** 2 + (center_y - prev_y) ** 2
                    ) ** 0.5
                    distance_meters = pixel_distance / PIXELS_PER_METER
                    vehicle_speeds[vehicle_id] = distance_meters * fps * 3.6
                previous_positions[vehicle_id] = (center_x, center_y)

                if (entered or exited) and vehicle_id not in counted_ids:
                    counted_ids.add(vehicle_id)
                    vehicle_counts[class_name] += 1
    finally:
        capture.release()

    elapsed_minutes = processed_frames / fps / 60
    analytics = calculate_analytics(
        vehicle_counts,
        vehicle_speeds,
        elapsed_minutes,
        ROAD_CAPACITY,
        MAX_SPEED,
    )
    print(f"Processed frames: {processed_frames}")
    print(f"LineZone IN: {line_zone.in_count}")
    print(f"LineZone OUT: {line_zone.out_count}")
    print(f"Unique vehicles counted: {analytics['total_vehicles']}")
    print(f"Average speed: {analytics['average_speed_kmph']:.1f} km/h")
    print(f"Traffic flow: {analytics['traffic_flow_per_hour']:.1f} vehicles/hour")
    print(f"Traffic density: {analytics['traffic_density']:.2f}")
    print(f"Congestion: {analytics['congestion_level']}")
    for vehicle, count in vehicle_counts.items():
        print(f"{vehicle}: {count}")


if __name__ == "__main__":
    main()
