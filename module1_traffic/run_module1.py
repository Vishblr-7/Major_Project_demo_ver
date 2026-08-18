"""Traffic detection, tracking, ROI density, flow, speed, and CSV export."""

import argparse
import csv
import math
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import supervision as sv
from ultralytics import YOLO

from module1_traffic import config
from module1_traffic.traffic_state import TrafficState


def timestamp() -> str:
    """Return the timestamp format used by all CSV outputs."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def image_to_world(x: float, y: float, homography: np.ndarray) -> tuple[float, float]:
    """Convert an image coordinate into real-world road-plane meters."""
    point = np.array([[[float(x), float(y)]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(point, homography)
    return float(transformed[0][0][0]), float(transformed[0][0][1])


def get_scaled_calibration_points(
    frame_width: int, frame_height: int
) -> list[tuple[float, float]]:
    """Scale the master-camera ROI to the current, same-viewpoint frame size."""
    scale_x = frame_width / config.MASTER_WIDTH
    scale_y = frame_height / config.MASTER_HEIGHT
    return [
        (x * scale_x, y * scale_y) for x, y in config.MASTER_ROI_POINTS
    ]


def validate_camera_resolution(frame_width: int, frame_height: int) -> str:
    """Return the supported calibration profile or reject unsupported input."""
    resolution = (frame_width, frame_height)
    if resolution in config.SUPPORTED_RESOLUTIONS:
        profile = config.SUPPORTED_RESOLUTIONS[resolution]
        print(f"[CALIBRATION] {frame_width}x{frame_height} -> {profile}")
        return profile
    message = (
        f"Unsupported camera resolution {frame_width}x{frame_height}. "
        f"Supported resolutions: {list(config.SUPPORTED_RESOLUTIONS)}."
    )
    if config.REQUIRE_SUPPORTED_RESOLUTION:
        raise RuntimeError(message + " Add/calibrate this resolution before speed estimation.")
    print(f"WARNING: {message}")
    return "UNSUPPORTED"


def create_homography(
    frame_width: int, frame_height: int
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Build and automatically validate the image-to-road homography."""
    profile = validate_camera_resolution(frame_width, frame_height)
    source_points = np.array(
        get_scaled_calibration_points(frame_width, frame_height), dtype=np.float32
    )
    destination_points = np.array(config.WORLD_POINTS, dtype=np.float32)
    homography, _ = cv2.findHomography(
        source_points, destination_points, method=cv2.RANSAC
    )
    if homography is None:
        raise RuntimeError("Homography calculation failed.")

    projected_corners = cv2.perspectiveTransform(
        source_points.reshape(-1, 1, 2), homography
    ).reshape(-1, 2)
    reprojection_error_m = float(
        np.max(np.linalg.norm(projected_corners - destination_points, axis=1))
    )
    roi_area_px = abs(float(cv2.contourArea(source_points)))
    geometry_valid = (
        np.isfinite(homography).all()
        and roi_area_px >= config.GEOMETRY_MIN_ROI_AREA_PX
        and reprojection_error_m <= config.GEOMETRY_MAX_REPROJECTION_ERROR_M
    )
    print(f"\n[CALIBRATION] Profile: {profile}")
    print("[CALIBRATION] Source points:")
    print(source_points)
    print("\n[CALIBRATION] World points:")
    print(destination_points)
    print("\n[CALIBRATION] Homography:")
    print(homography)
    print(
        f"[CALIBRATION] ROI area: {roi_area_px:.1f} px²; "
        f"corner error: {reprojection_error_m:.6f} m"
    )
    if geometry_valid:
        print("[CALIBRATION] Geometry validation: PASS")
    else:
        print("[CALIBRATION] Geometry validation: FAIL — recalibration required")
    return homography, source_points, geometry_valid


def scale_point(point: tuple[int, int], frame_width: int, frame_height: int) -> tuple[int, int]:
    """Scale a master-resolution point to the current camera resolution."""
    x, y = point
    return (
        int(round(x * frame_width / config.MASTER_WIDTH)),
        int(round(y * frame_height / config.MASTER_HEIGHT)),
    )


def valid_emission_track(group: list[dict[str, Any]]) -> bool:
    """Accept only sufficiently long tracks with physically plausible dynamics."""
    if len(group) < config.MIN_TRACK_LENGTH:
        return False
    speeds = [float(row["speed_kmph"]) for row in group]
    accelerations = [abs(float(row["acceleration_mps2"])) for row in group]
    return (
        max(speeds, default=0.0) <= config.MAX_REASONABLE_SPEED_KMPH
        and min(speeds, default=0.0) >= 0.0
        and max(accelerations, default=0.0) <= config.MAX_REASONABLE_ACCEL_MPS2
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run vehicle detection on a video file or live webcam."
    )
    parser.add_argument("--webcam", action="store_true", help="Use camera 0.")
    parser.add_argument("--video", help="Input video path (video mode).")
    parser.add_argument("--model", default=config.MODEL_PATH)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument(
        "--save-video",
        action="store_true",
        help="Save an annotated MP4 in webcam mode (always enabled for video mode).",
    )
    parser.add_argument("--output-video", default=config.OUTPUT_VIDEO)
    parser.add_argument("--vehicle-csv", default=config.VEHICLE_CSV)
    parser.add_argument("--traffic-csv", default=config.TRAFFIC_CSV)
    parser.add_argument(
        "--trajectory-csv",
        help="Per-frame trajectory CSV. Defaults beside --vehicle-csv.",
    )
    parser.add_argument(
        "--emission-csv",
        help="Valid emission-training tracks CSV. Defaults beside --trajectory-csv.",
    )
    parser.add_argument(
        "--video-id",
        help="Stable source identifier written to trajectory and emission rows.",
    )
    parser.add_argument(
        "--traffic-state-csv",
        help="Shared TrafficState snapshot CSV for Modules 2/3/4. Defaults beside --traffic-csv.",
    )
    parser.add_argument(
        "--traffic-state-interval",
        type=float,
        default=config.TRAFFIC_STATE_INTERVAL_S,
        help="Seconds between TrafficState snapshots (default: 2.0).",
    )
    args = parser.parse_args()

    if args.webcam and args.video:
        parser.error("--webcam and --video cannot be used together")

    source = 0 if args.webcam else (args.video or config.VIDEO_PATH)
    source_description = "webcam (camera 0)" if args.webcam else str(source)
    video_id = args.video_id or ("webcam" if args.webcam else Path(str(source)).stem)
    model = YOLO(args.model)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open source: {source_description}")

    fps = cap.get(cv2.CAP_PROP_FPS) or config.FPS
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Source: {source_description}; FPS: {fps:.2f}; resolution: {frame_width} x {frame_height}")

    # Live cameras can be plugged in at any resolution. Video-file inputs keep
    # the original strict behaviour (raise on an uncalibrated resolution) so
    # the 30-video batch pipeline's regression-tested output cannot change.
    # Only --webcam falls back to COUNT-ONLY mode instead of crashing.
    count_only = False
    calibration_profile = config.SUPPORTED_RESOLUTIONS.get(
        (frame_width, frame_height)
    )
    if calibration_profile is None and args.webcam:
        print(
            f"WARNING: unsupported live-camera resolution {frame_width}x{frame_height}. "
            "Falling back to COUNT-ONLY mode: vehicles will still be detected, "
            "tracked, and counted, but speed/distance/emissions are UNAVAILABLE "
            "for this session (no calibrated homography for this resolution)."
        )
        count_only = True
        calibration_profile = "UNSUPPORTED_COUNT_ONLY"
        homography_matrix = np.eye(3, dtype=np.float32)
        roi_points = get_scaled_calibration_points(frame_width, frame_height)
        geometry_valid = False
    else:
        homography_matrix, roi_points, geometry_valid = create_homography(
            frame_width, frame_height
        )
    counting_line_start = scale_point(
        config.MASTER_COUNTING_LINE_START, frame_width, frame_height
    )
    counting_line_end = scale_point(
        config.MASTER_COUNTING_LINE_END, frame_width, frame_height
    )

    trajectory_path = Path(
        args.trajectory_csv
        or str(Path(args.vehicle_csv).with_name("trajectory_data.csv"))
    )
    emission_path = Path(
        args.emission_csv
        or str(trajectory_path.with_name("emission_training_data.csv"))
    )
    traffic_state_path = Path(
        args.traffic_state_csv
        or str(Path(args.traffic_csv).with_name("traffic_state.csv"))
    )
    for path in (Path(args.vehicle_csv), Path(args.traffic_csv), trajectory_path, traffic_state_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    vehicle_file = open(args.vehicle_csv, "w", newline="", encoding="utf-8")
    traffic_file = open(args.traffic_csv, "w", newline="", encoding="utf-8")
    trajectory_file = trajectory_path.open("w", newline="", encoding="utf-8")
    traffic_state_file = traffic_state_path.open("w", newline="", encoding="utf-8")
    traffic_state_writer = csv.DictWriter(
        traffic_state_file, fieldnames=TrafficState.csv_fieldnames()
    )
    traffic_state_writer.writeheader()
    vehicle_writer = csv.writer(vehicle_file)
    traffic_writer = csv.writer(traffic_file)
    trajectory_writer = csv.writer(trajectory_file)
    vehicle_writer.writerow([
        "timestamp", "vehicle_id", "vehicle_type", "speed_kmph",
        "acceleration_mps2", "x", "y", "in_roi", "direction",
    ])
    traffic_writer.writerow([
        "timestamp", "car_count", "motorcycle_count", "bus_count",
        "truck_count", "autorickshaw_count", "bicycle_count",
        "total_vehicles", "current_vehicles", "average_speed", "vehicles_per_100m2",
    ])
    trajectory_header = [
        "video_id", "timestamp", "frame_number", "vehicle_id", "vehicle_type", "image_x",
        "image_y", "world_x_m", "world_y_m", "distance_km", "vehicle_total_distance_km", "speed_kmph",
        "acceleration_mps2", "traffic_density_vehicles_per_100m2",
        "stop_duration_s", "in_roi", "emission_eligible",
    ]
    trajectory_writer.writerow(trajectory_header)

    tracker = sv.ByteTrack()
    line_zone = sv.LineZone(
        start=sv.Point(*counting_line_start),
        end=sv.Point(*counting_line_end),
        triggering_anchors=(sv.Position.BOTTOM_CENTER,),
    )
    line_annotator = sv.LineZoneAnnotator(
        thickness=config.LINE_THICKNESS, text_thickness=2, text_scale=0.7
    )
    box_annotator = sv.BoxAnnotator(thickness=config.LINE_THICKNESS)
    label_annotator = sv.LabelAnnotator(text_scale=config.TEXT_SCALE)

    position_history: dict[int, deque[tuple[int, float, float]]] = {}
    speed_history: dict[int, deque[float]] = {}
    vehicle_speeds: dict[int, float] = {}
    vehicle_accelerations: dict[int, float] = {}
    vehicle_distances_km: dict[int, float] = {}
    counted_ids: set[int] = set()
    crossing_counts = {vehicle: 0 for vehicle in config.VEHICLE_CLASSES}
    current_vehicles = 0
    class_counts = {vehicle: 0 for vehicle in config.VEHICLE_CLASSES}
    current_speeds: list[float] = []
    trajectory_rows: list[dict[str, Any]] = []
    frame_number = 0
    last_snapshot_frame = 0
    out = None
    save_video = not args.webcam or args.save_video
    aggregation_frames = max(1, round(fps * config.AGGREGATION_INTERVAL))
    state_interval_frames = max(1, round(fps * args.traffic_state_interval))
    roi_polygon = np.array(roi_points, dtype=np.int32)
    roi_polygon_float = np.array(roi_points, dtype=np.float32)
    state_window_start_ts = timestamp()
    crossings_since_last_state = 0

    def write_traffic_state() -> None:
        """Emit the shared TrafficState snapshot for Modules 2/3/4."""
        nonlocal state_window_start_ts, crossings_since_last_state
        total_vehicles = sum(class_counts.values())
        window_end_ts = timestamp()
        window_seconds = max(args.traffic_state_interval, 1e-6)
        flow_per_min = crossings_since_last_state / window_seconds * 60.0

        if geometry_valid and current_speeds:
            average_speed = float(np.mean(current_speeds))
            speed_std = float(np.std(current_speeds))
        else:
            average_speed = None
            speed_std = None

        roi_accelerations = [
            vehicle_accelerations[v] for v in current_roi_ids if v in vehicle_accelerations
        ]
        if geometry_valid and roi_accelerations:
            mean_accel = float(np.mean(roi_accelerations))
            accel_std = float(np.std(roi_accelerations))
        else:
            mean_accel = None
            accel_std = None

        roi_speeds_for_stop_ratio = [
            vehicle_speeds.get(v, 0.0) for v in current_roi_ids
        ]
        if geometry_valid and roi_speeds_for_stop_ratio:
            stopped = sum(
                1 for s in roi_speeds_for_stop_ratio if s < config.MOVING_SPEED_THRESHOLD_KMPH
            )
            stopped_ratio = stopped / len(roi_speeds_for_stop_ratio)
        else:
            stopped_ratio = None

        roi_area_m2 = config.ROAD_WIDTH_M * config.ROAD_LENGTH_M
        if geometry_valid and roi_area_m2 > 0:
            density = total_vehicles / roi_area_m2 * 100
            # Rough occupancy proxy: current ROI count against the configured
            # nominal road capacity. Not a calibrated physical quantity.
            occupancy = min(1.0, total_vehicles / config.ROAD_CAPACITY) if config.ROAD_CAPACITY else None
        else:
            density = None
            occupancy = None

        state = TrafficState(
            timestamp=window_end_ts,
            window_start=state_window_start_ts,
            window_end=window_end_ts,
            car_count=class_counts["car"],
            motorcycle_count=class_counts["motorcycle"],
            bus_count=class_counts["bus"],
            truck_count=class_counts["truck"],
            autorickshaw_count=class_counts["autorickshaw"],
            bicycle_count=class_counts["bicycle"],
            total_vehicles=total_vehicles,
            current_vehicles=total_vehicles,
            average_speed_kmph=round(average_speed, 2) if average_speed is not None else None,
            speed_std=round(speed_std, 2) if speed_std is not None else None,
            density_veh_per_100m2=round(density, 3) if density is not None else None,
            flow_veh_per_min=round(flow_per_min, 2),
            roi_occupancy=round(occupancy, 3) if occupancy is not None else None,
            mean_acceleration=round(mean_accel, 3) if mean_accel is not None else None,
            acceleration_std=round(accel_std, 3) if accel_std is not None else None,
            stopped_vehicle_ratio=round(stopped_ratio, 3) if stopped_ratio is not None else None,
            calibration_profile=calibration_profile,
            data_quality="FULL" if geometry_valid else "COUNT_ONLY",
        )
        traffic_state_writer.writerow(state.to_dict())
        traffic_state_file.flush()
        state_window_start_ts = window_end_ts
        crossings_since_last_state = 0

    def write_traffic_snapshot() -> None:
        """Write the current ROI traffic state and real-world density."""
        total_vehicles = sum(class_counts.values())
        current_vehicles = total_vehicles
        average_speed = sum(current_speeds) / len(current_speeds) if current_speeds else 0.0
        roi_area_m2 = config.ROAD_WIDTH_M * config.ROAD_LENGTH_M
        vehicles_per_100m2 = (
            current_vehicles / roi_area_m2 * 100 if roi_area_m2 > 0 else 0.0
        )
        traffic_writer.writerow([
            timestamp(), class_counts["car"], class_counts["motorcycle"],
            class_counts["bus"], class_counts["truck"],
            class_counts["autorickshaw"], class_counts["bicycle"], total_vehicles,
            current_vehicles, round(average_speed, 2), round(vehicles_per_100m2, 3),
        ])
        traffic_file.flush()

    try:
        try:
            while not args.max_frames or frame_number < args.max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_number += 1

                if save_video and out is None:
                    height, width = frame.shape[:2]
                    output_path = Path(args.output_video)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    out = cv2.VideoWriter(
                        str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
                    )
                    if not out.isOpened():
                        raise RuntimeError(f"Unable to create output video: {output_path}")

                result = model(frame, conf=config.CONFIDENCE_THRESHOLD, verbose=False)[0]
                detections = sv.Detections.from_ultralytics(result)
                vehicle_mask = [
                    model.names[int(class_id)] in config.VEHICLE_CLASSES
                    for class_id in detections.class_id
                ]
                detections = tracker.update_with_detections(detections[vehicle_mask])
                crossed_in, crossed_out = line_zone.trigger(detections)

                current_roi_ids: set[int] = set()
                current_speeds = []
                class_counts = {vehicle: 0 for vehicle in config.VEHICLE_CLASSES}
                labels = []
                frame_trajectory_rows: list[dict[str, Any]] = []
                history_length = max(5, int(fps * config.POSITION_HISTORY_SECONDS))

                for box, tracker_id, class_id, entered, exited in zip(
                    detections.xyxy, detections.tracker_id, detections.class_id, crossed_in, crossed_out
                ):
                    vehicle_id = int(tracker_id)
                    vehicle_type = model.names[int(class_id)]
                    x1, y1, x2, y2 = map(float, box)
                    foot_x, foot_y = (x1 + x2) / 2.0, y2
                    if count_only:
                        # No calibrated homography for this resolution -- world
                        # coordinates, speed, acceleration, and distance are all
                        # physically meaningless here and must not be computed.
                        world_x, world_y = float("nan"), float("nan")
                    else:
                        world_x, world_y = image_to_world(
                            foot_x, foot_y, homography_matrix
                        )
                    history = position_history.setdefault(
                        vehicle_id, deque(maxlen=history_length)
                    )
                    previous_observation = history[-1] if history else None
                    history.append((frame_number, world_x, world_y))

                    # Cumulative road distance uses only longitudinal movement. A
                    # lateral lane-position error cannot add artificial distance.
                    step_distance_km = 0.0
                    if previous_observation is not None:
                        previous_frame, _, previous_world_y = previous_observation
                        step_dt = (frame_number - previous_frame) / fps
                        step_distance_m = abs(world_y - previous_world_y)
                        step_speed_kmph = (
                            step_distance_m / step_dt * 3.6 if step_dt > 0 else 0.0
                        )
                        if 0 <= step_speed_kmph <= config.MAX_REASONABLE_SPEED_KMPH:
                            step_distance_km = step_distance_m / 1000.0
                            vehicle_distances_km[vehicle_id] = (
                                vehicle_distances_km.get(vehicle_id, 0.0)
                                + step_distance_km
                            )

                    if len(history) >= 2:
                        old_frame, old_world_x, old_world_y = history[0]
                        frame_delta = frame_number - old_frame
                        if frame_delta > 0:
                            dt = frame_delta / fps
                            displacement = np.array(
                                [world_x - old_world_x, world_y - old_world_y],
                                dtype=float,
                            )
                            flow_direction = np.array(config.FLOW_DIRECTION_WORLD, dtype=float)
                            flow_direction /= np.linalg.norm(flow_direction)
                            # Project onto the road's longitudinal axis. Lateral
                            # drift is ignored so it cannot inflate speed estimates.
                            distance_m = abs(float(np.dot(displacement, flow_direction)))
                            raw_speed = distance_m / dt * 3.6
                            # Robust speed validation: reject raw measurements that
                            # imply an impossible acceleration from the last valid speed.
                            max_speed = config.MAX_REASONABLE_SPEED_KMPH
                            max_accel = config.MAX_REASONABLE_ACCEL_MPS2
                            speeds = speed_history.setdefault(
                                vehicle_id,
                                deque(maxlen=config.SPEED_HISTORY_LENGTH),
                            )
                            previous_speed = vehicle_speeds.get(vehicle_id)
                            if previous_speed is None:
                                if 0 <= raw_speed <= max_speed:
                                    speeds.append(raw_speed)
                                    vehicle_speeds[vehicle_id] = float(np.median(list(speeds)))
                                    vehicle_accelerations[vehicle_id] = 0.0
                            else:
                                previous_speed_mps = previous_speed / 3.6
                                raw_speed_mps = raw_speed / 3.6
                                max_speed_change = max_accel * dt
                                speed_change = raw_speed_mps - previous_speed_mps
                                if 0 <= raw_speed <= max_speed and abs(speed_change) <= max_speed_change:
                                    speeds.append(raw_speed)
                                    median_speed = float(np.median(list(speeds)))
                                    smoothed_speed = (
                                        config.SPEED_SMOOTHING_ALPHA * median_speed
                                        + (1 - config.SPEED_SMOOTHING_ALPHA) * previous_speed
                                    )
                                    acceleration = (
                                        smoothed_speed / 3.6 - previous_speed_mps
                                    ) / dt
                                    vehicle_speeds[vehicle_id] = smoothed_speed
                                    vehicle_accelerations[vehicle_id] = max(
                                        -max_accel, min(max_accel, acceleration)
                                    )
                                else:
                                    vehicle_speeds[vehicle_id] = previous_speed
                                    vehicle_accelerations[vehicle_id] = 0.0

                    point_inside = cv2.pointPolygonTest(
                        roi_polygon_float, (float(foot_x), float(foot_y)), False
                    )
                    in_roi = point_inside >= 0
                    speed = vehicle_speeds.get(vehicle_id, 0.0)
                    acceleration = vehicle_accelerations.get(vehicle_id, 0.0)
                    if in_roi:
                        current_roi_ids.add(vehicle_id)
                        class_counts[vehicle_type] += 1
                        if speed > 0:
                            current_speeds.append(speed)

                    trajectory_row = {
                        "video_id": video_id,
                        "timestamp": timestamp(),
                        "frame_number": frame_number,
                        "vehicle_id": vehicle_id,
                        "vehicle_type": vehicle_type,
                        "image_x": round(foot_x, 2),
                        "image_y": round(foot_y, 2),
                        "world_x_m": round(world_x, 3),
                        "world_y_m": round(world_y, 3),
                        "distance_km": round(step_distance_km, 6),
                        "vehicle_total_distance_km": round(
                            vehicle_distances_km.get(vehicle_id, 0.0), 6
                        ),
                        "speed_kmph": round(speed, 2),
                        "acceleration_mps2": round(acceleration, 3),
                        "in_roi": int(in_roi),
                    }
                    trajectory_rows.append(trajectory_row)
                    frame_trajectory_rows.append(trajectory_row)
                    labels.append(f"ID {vehicle_id} | {vehicle_type} | {speed:.1f} km/h")

                    if (entered or exited) and vehicle_id not in counted_ids:
                        counted_ids.add(vehicle_id)
                        crossing_counts[vehicle_type] += 1
                        crossings_since_last_state += 1
                        vehicle_writer.writerow([
                            timestamp(), vehicle_id, vehicle_type, round(speed, 2),
                            round(acceleration, 3), round(foot_x, 2), round(foot_y, 2),
                            int(in_roi), "IN" if entered else "OUT",
                        ])
                        vehicle_file.flush()

                current_vehicles = len(current_roi_ids)
                traffic_density = (
                    current_vehicles / (config.ROAD_WIDTH_M * config.ROAD_LENGTH_M) * 100
                    if config.ROAD_WIDTH_M * config.ROAD_LENGTH_M > 0
                    else 0.0
                )
                for row in frame_trajectory_rows:
                    row["traffic_density_vehicles_per_100m2"] = round(traffic_density, 3)
                if frame_number % aggregation_frames == 0:
                    write_traffic_snapshot()
                    last_snapshot_frame = frame_number
                if frame_number % state_interval_frames == 0:
                    write_traffic_state()

                frame = box_annotator.annotate(scene=frame, detections=detections)
                frame = label_annotator.annotate(scene=frame, detections=detections, labels=labels)
                frame = line_annotator.annotate(frame, line_counter=line_zone)
                cv2.polylines(
                    frame, [roi_polygon], isClosed=True, color=(255, 0, 0), thickness=3
                )
                cv2.line(
                    frame,
                    counting_line_start,
                    counting_line_end,
                    (255, 255, 255),
                    3,
                )
                y = 40
                cv2.putText(frame, f"Current Vehicles: {current_vehicles}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                y += 30
                for vehicle, count in crossing_counts.items():
                    cv2.putText(frame, f"{vehicle}: {count}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    y += 30
                roi_area_m2 = config.ROAD_WIDTH_M * config.ROAD_LENGTH_M
                density = current_vehicles / roi_area_m2 * 100 if roi_area_m2 else 0.0
                avg_speed = sum(current_speeds) / len(current_speeds) if current_speeds else 0.0
                cv2.putText(frame, f"Density: {density:.2f} veh/100m2 | Avg Speed: {avg_speed:.1f} km/h", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                if out is not None:
                    out.write(frame)
                if config.SHOW_WINDOW and not args.no_display:
                    cv2.imshow("YOLO + ByteTrack Traffic Analytics", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Ctrl-C received. Finishing gracefully: writing partial trajectory/emission CSVs for frames processed so far.")

        if frame_number and frame_number != last_snapshot_frame:
            write_traffic_snapshot()

        tracks: dict[int, list[dict[str, Any]]] = {}
        for row in trajectory_rows:
            tracks.setdefault(int(row["vehicle_id"]), []).append(row)
        eligible_track_ids = {
            vehicle_id
            for vehicle_id, track in tracks.items()
            if geometry_valid and valid_emission_track(track)
        }
        for track in tracks.values():
            stopped_duration = 0.0
            previous_frame = None
            for row in track:
                frame = int(row["frame_number"])
                frame_delta = 1 if previous_frame is None else max(1, frame - previous_frame)
                if float(row["speed_kmph"]) < config.MOVING_SPEED_THRESHOLD_KMPH:
                    stopped_duration += frame_delta / fps
                else:
                    stopped_duration = 0.0
                row["stop_duration_s"] = round(stopped_duration, 3)
                previous_frame = frame
        for row in trajectory_rows:
            trajectory_writer.writerow([
                row[field] for field in trajectory_header[:-1]
            ] + [int(int(row["vehicle_id"]) in eligible_track_ids)])
        trajectory_file.flush()

        if geometry_valid:
            emission_path.parent.mkdir(parents=True, exist_ok=True)
            with emission_path.open("w", newline="", encoding="utf-8") as emission_file:
                emission_fields = [
                    "video_id", "vehicle_id", "vehicle_type", "timestamp",
                    "speed_kmph", "acceleration_mps2", "world_x_m", "world_y_m",
                    "traffic_density_vehicles_per_100m2", "stop_duration_s", "in_roi",
                ]
                emission_writer = csv.DictWriter(emission_file, fieldnames=emission_fields)
                emission_writer.writeheader()
                for row in trajectory_rows:
                    if int(row["vehicle_id"]) in eligible_track_ids:
                        emission_writer.writerow({field: row[field] for field in emission_fields})
            print(f"Emission training data: {emission_path}")
        else:
            print("Emission training data not generated: recalibration required.")
    finally:
        cap.release()
        if out is not None:
            out.release()
        vehicle_file.close()
        traffic_file.close()
        trajectory_file.close()
        traffic_state_file.close()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            # Headless / no-GUI-backend environments (CI, servers, this pipeline's
            # own batch runner) cannot destroy windows that were never created.
            # All CSV/video outputs above are already flushed and closed at this
            # point, so this must never turn into a crash.
            pass

    print(f"Processed {frame_number} frames from {source_description}.")
    print(f"Vehicle crossings: {args.vehicle_csv}")
    print(f"Traffic analytics: {args.traffic_csv}")
    print(f"Trajectory data: {trajectory_path}")
    print(f"Traffic state snapshots: {traffic_state_path}")


if __name__ == "__main__":
    main()
