"""Run the frozen Module 1 pipeline for a directory of INDRA videos."""

import argparse
import csv
import subprocess
import sys
from pathlib import Path

import cv2

from module1_traffic import config


VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def video_metadata(path: Path) -> tuple[int, int, float, int]:
    """Read input metadata without processing the video."""
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return 0, 0, 0.0, 0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS)
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    return width, height, fps, frames


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-run frozen Module 1.")
    parser.add_argument(
        "--input-dir",
        default="INDRA_data_for_emissions/videos_mp4",
        help="Directory containing selected INDRA videos.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/module1",
        help="New root directory for all Module 1 artifacts.",
    )
    parser.add_argument(
        "--videos",
        nargs="*",
        help="Optional video file names to process; defaults to every supported video.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    requested = set(args.videos or [])
    videos = sorted(
        (
            path for path in input_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in VIDEO_SUFFIXES
            and (not requested or path.name in requested)
        ),
        key=lambda path: path.name,
    )
    missing = requested - {path.name for path in videos}
    if missing:
        raise FileNotFoundError(f"Requested videos not found: {sorted(missing)}")
    if not videos:
        raise RuntimeError("No supported video files selected.")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    merged_rows = []
    emission_header = [
        "video_id", "vehicle_id", "vehicle_type", "timestamp", "speed_kmph",
        "acceleration_mps2", "world_x_m", "world_y_m",
        "traffic_density_vehicles_per_100m2", "stop_duration_s", "in_roi",
    ]

    for video_path in videos:
        video_id = video_path.stem
        width, height, fps, frames = video_metadata(video_path)
        profile = config.SUPPORTED_RESOLUTIONS.get((width, height))
        run_dir = output_dir / "individual_runs" / video_id
        run_dir.mkdir(parents=True, exist_ok=True)
        emission_path = run_dir / f"{video_id}_emission_training.csv"
        row = {
            "video_id": video_id,
            "source_video": str(video_path),
            "resolution": f"{width}x{height}",
            "fps": fps,
            "frames": frames,
            "calibration_profile": profile or "FLAG_RECALIBRATION",
            "status": "",
            "reason": "",
            "emission_csv": "",
        }
        if profile is None:
            row["status"] = "EXCLUDED_RECALIBRATION_REQUIRED"
            row["reason"] = "Unsupported resolution; emission data was not generated."
            manifest_rows.append(row)
            print(f"[EXCLUDED] {video_path.name}: {row['reason']}")
            continue

        command = [
            sys.executable, "-m", "module1_traffic.run_module1", "--video", str(video_path), "--video-id", video_id,
            "--no-display", "--output-video", str(run_dir / f"{video_id}_annotated.mp4"),
            "--vehicle-csv", str(run_dir / f"{video_id}_vehicles.csv"),
            "--traffic-csv", str(run_dir / f"{video_id}_traffic.csv"),
            "--trajectory-csv", str(run_dir / f"{video_id}_trajectory.csv"),
            "--emission-csv", str(emission_path),
        ]
        print(f"[MODULE 1] {video_path.name} ({profile})")
        result = subprocess.run(command, text=True, capture_output=True)
        (run_dir / "module1.log").write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
        if result.returncode != 0:
            row["status"] = "EXCLUDED_PROCESSING_FAILED"
            row["reason"] = result.stderr.strip() or "Pipeline returned a non-zero exit code."
        elif not emission_path.exists():
            row["status"] = "EXCLUDED_RECALIBRATION_REQUIRED"
            row["reason"] = "Geometry quality gate failed; emission data was not generated."
        else:
            with emission_path.open(newline="", encoding="utf-8") as file:
                emission_rows = list(csv.DictReader(file))
            merged_rows.extend(emission_rows)
            row["status"] = "INCLUDED"
            row["reason"] = f"{len(emission_rows)} quality-approved emission rows."
            row["emission_csv"] = str(emission_path)
        manifest_rows.append(row)

    manifest_path = output_dir / "module1_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)
    dataset_path = output_dir / "INDRA_COPERT_DATASET.csv"
    with dataset_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=emission_header)
        writer.writeheader()
        writer.writerows(merged_rows)

    included = sum(row["status"] == "INCLUDED" for row in manifest_rows)
    print(f"Module 1 complete: {included}/{len(manifest_rows)} videos included.")
    print(f"Manifest: {manifest_path}")
    print(f"Merged COPERT dataset: {dataset_path} ({len(merged_rows)} rows)")


if __name__ == "__main__":
    main()
