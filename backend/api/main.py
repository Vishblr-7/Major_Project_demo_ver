"""FastAPI backend for the Module 1/2 demo frontend.

Read-only: every endpoint aggregates/filters the existing, already-verified
Module 1/2 output files (see data_loader.py). Nothing here re-runs YOLO,
ByteTrack, COPERT, or XGBoost, and nothing here writes back to any source
file. If a requested value genuinely isn't available in the source data, the
endpoint returns null/"N/A" rather than inventing one.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import data_loader as dl

app = FastAPI(title="Hybrid Traffic System API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if dl.VIDEO2_DIR.exists():
    app.mount("/media/video2", StaticFiles(directory=str(dl.VIDEO2_DIR)), name="video2-media")
if dl.VIDEO2_RAW.exists():
    app.mount("/media/raw", StaticFiles(directory=str(dl.VIDEO2_RAW.parent)), name="video2-raw")

# The annotated video Module 1 writes is mpeg4-coded (OpenCV's mp4v fourcc),
# which browsers cannot decode. Transcode a browser-playable H.264 copy once
# at startup (cached, source file untouched) and serve that instead -- see
# data_loader.get_browser_playable_video()'s docstring for the full reason.
if dl.VIDEO2_ANNOTATED.exists():
    try:
        dl.get_browser_playable_video(dl.VIDEO2_ANNOTATED, "video2_annotated_h264.mp4")
        app.mount("/media/playable", StaticFiles(directory=str(dl.MEDIA_CACHE_DIR)), name="playable-media")
    except RuntimeError as exc:
        print(f"WARNING: could not prepare a browser-playable annotated video: {exc}")


def _none_if_nan(value):
    if value is None:
        return None
    try:
        if isinstance(value, (float, np.floating)) and (np.isnan(value) or np.isinf(value)):
            return None
    except TypeError:
        return value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def _class_counts(frame: pd.DataFrame) -> dict:
    dominant = dl.dominant_class_per_track(frame)
    counts = dominant.value_counts().to_dict()
    return {name: int(counts.get(name, 0)) for name in dl.VEHICLE_CLASSES.values()}


@app.get("/api/summary")
def get_summary():
    """Fleet-wide KPIs across every INCLUDED video in the authoritative 104-video dataset."""
    frame = dl.get_module1_dataset()
    emissions = dl.get_vehicle_emissions()

    roi = frame.loc[frame["in_roi"] == 1]
    class_counts = _class_counts(frame)
    total_vehicles = sum(class_counts.values())

    avg_speed = roi.loc[roi["speed_kmph"] > 0, "speed_kmph"].mean()
    avg_density = frame["traffic_density_vehicles_per_100m2"].mean()

    totals = {p: float(emissions[f"{p}_g"].sum()) for p in dl.POLLUTANTS}

    return {
        "videos_processed": int(dl.get_manifest()["status"].eq("INCLUDED").sum()),
        "total_vehicles_tracked": total_vehicles,
        "vehicle_class_counts": class_counts,
        "tracked_scope_note": (
            "outputs/module1_distance_enriched_104/INDRA_COPERT_DATASET_WITH_DISTANCE.csv "
            "(the authoritative Module 1 file) already contains only emission_eligible==1 "
            "rows by construction (enrich_module1_distances.py filters before writing it), "
            "so every count here is already the emission-eligible subset -- there is no "
            "separate 'all detections including short/implausible tracks' figure in this "
            "authoritative file."
        ),
        "bicycle_note": "Bicycles are detected and counted but excluded from emission calculation.",
        "average_speed_kmph": _none_if_nan(round(avg_speed, 2)) if pd.notna(avg_speed) else None,
        "average_traffic_density_veh_per_100m2": _none_if_nan(round(avg_density, 3)) if pd.notna(avg_density) else None,
        "congestion_level": dl.classify_congestion(avg_density),
        "total_emissions_g": {p: round(totals[p], 3) for p in dl.POLLUTANTS},
        "emission_source": "COPERT-derived (outputs/copert_emissions_104/vehicle_emissions.csv)",
    }


@app.get("/api/videos")
def list_videos():
    manifest = dl.get_manifest()
    rows = manifest[["video_id", "resolution", "fps", "frames", "calibration_profile", "status"]]
    return rows.to_dict(orient="records")


@app.get("/api/video/{video_id}")
def get_video_detail(video_id: str):
    frame = dl.get_module1_dataset()
    subset = frame.loc[frame["video_id"] == video_id]
    if subset.empty:
        raise HTTPException(status_code=404, detail=f"video_id '{video_id}' not found in the authoritative dataset.")

    roi = subset.loc[subset["in_roi"] == 1]
    class_counts = _class_counts(subset)
    total_vehicles = sum(class_counts.values())

    avg_speed = roi.loc[roi["speed_kmph"] > 0, "speed_kmph"].mean()
    avg_density = subset["traffic_density_vehicles_per_100m2"].mean()
    avg_stop_duration = subset["stop_duration_s"].mean()
    total_distance_km = subset.groupby("vehicle_id")["vehicle_total_distance_km"].max().sum()

    manifest_row = dl.get_manifest().loc[dl.get_manifest()["video_id"] == video_id]
    meta = manifest_row.iloc[0].to_dict() if not manifest_row.empty else {}

    return {
        "video_id": video_id,
        "resolution": meta.get("resolution", "N/A"),
        "fps": _none_if_nan(meta.get("fps")),
        "frames": _none_if_nan(meta.get("frames")),
        "vehicle_class_counts": class_counts,
        "total_vehicles": total_vehicles,
        "note": "Already the emission-eligible subset -- see /api/summary's tracked_scope_note.",
        "bicycle_excluded_count": class_counts.get("bicycle", 0),
        "average_speed_kmph": _none_if_nan(round(avg_speed, 2)) if pd.notna(avg_speed) else None,
        "traffic_density_veh_per_100m2": _none_if_nan(round(avg_density, 3)) if pd.notna(avg_density) else None,
        "average_stop_duration_s": _none_if_nan(round(avg_stop_duration, 2)) if pd.notna(avg_stop_duration) else None,
        "total_distance_km": _none_if_nan(round(float(total_distance_km), 4)),
        "congestion_status": dl.classify_congestion(avg_density),
    }


@app.get("/api/traffic/{video_id}")
def get_traffic_timeseries(video_id: str):
    """Per-frame time series (vehicle count, density, avg speed, stop duration)
    for charting -- built purely from Module 1's own already-computed per-frame
    columns, grouped by frame_number, not recomputed."""
    frame = dl.get_module1_dataset()
    subset = frame.loc[frame["video_id"] == video_id]
    if subset.empty:
        raise HTTPException(status_code=404, detail=f"video_id '{video_id}' not found.")

    roi = subset.loc[subset["in_roi"] == 1]
    by_frame = roi.groupby("frame_number").agg(
        vehicle_count=("vehicle_id", "nunique"),
        traffic_density=("traffic_density_vehicles_per_100m2", "mean"),
        average_speed_kmph=("speed_kmph", lambda s: s[s > 0].mean() if (s > 0).any() else np.nan),
        stop_duration_s=("stop_duration_s", "mean"),
    ).reset_index().sort_values("frame_number")

    by_frame = by_frame.replace({np.nan: None})
    return by_frame.to_dict(orient="records")


@app.get("/api/emissions/summary")
def get_emissions_summary():
    emissions = dl.get_vehicle_emissions()
    excluded_path = dl.VEHICLE_EMISSIONS.parent / "excluded_vehicle_tracks.csv"

    totals = {p: round(float(emissions[f"{p}_g"].sum()), 3) for p in dl.POLLUTANTS}
    per_vehicle_avg = {p: round(float(emissions[f"{p}_g"].mean()), 6) for p in dl.POLLUTANTS}
    by_type = (
        emissions.groupby("vehicle_type")[[f"{p}_g" for p in dl.POLLUTANTS]]
        .agg(["sum", "mean", "count"])
    )
    by_type.columns = ["_".join(col) for col in by_type.columns]
    by_type = by_type.round(6).reset_index().to_dict(orient="records")

    excluded_count = 0
    excluded_reasons: dict = {}
    if excluded_path.exists():
        excluded = pd.read_csv(excluded_path)
        excluded_count = int(len(excluded))
        excluded_reasons = excluded["vehicle_type"].value_counts().to_dict()

    return {
        "included_vehicle_tracks": int(len(emissions)),
        "excluded_vehicle_tracks": excluded_count,
        "excluded_by_type": excluded_reasons,
        "total_emissions_g": totals,
        "average_emission_per_vehicle_g": per_vehicle_avg,
        "by_vehicle_type": by_type,
        "pollutants": list(dl.POLLUTANTS),
        "emission_source": "COPERT-derived, sourced from COPERT_FACTOR_TABLE (see docs/MODULE2_COPERT_METHODOLOGY.md)",
    }


@app.get("/api/emissions/{video_id}")
def get_video_emissions(video_id: str):
    emissions = dl.get_vehicle_emissions()
    subset = emissions.loc[emissions["video_id"] == video_id]
    if subset.empty:
        return {
            "video_id": video_id,
            "note": "No COPERT-eligible (car/motorcycle/bus/truck) emission tracks for this video.",
            "totals_g": {p: 0.0 for p in dl.POLLUTANTS},
            "by_vehicle_type": {},
        }

    totals = {p: round(float(subset[f"{p}_g"].sum()), 4) for p in dl.POLLUTANTS}
    per_vehicle_avg = {p: round(float(subset[f"{p}_g"].mean()), 6) for p in dl.POLLUTANTS}
    by_type = (
        subset.groupby("vehicle_type")[[f"{p}_g" for p in dl.POLLUTANTS]]
        .sum().round(4).reset_index().to_dict(orient="records")
    )

    return {
        "video_id": video_id,
        "included_tracks": int(len(subset)),
        "totals_g": totals,
        "average_per_vehicle_g": per_vehicle_avg,
        "by_vehicle_type": by_type,
        "emission_source": "COPERT_FACTOR_TABLE",
    }


@app.get("/api/models/performance")
def get_model_performance():
    metrics = dl.get_model_metrics()
    pollutants = {}
    for pollutant in dl.POLLUTANTS:
        entry = metrics["pollutants"][pollutant]
        pollutants[pollutant] = {
            "test_r2": round(entry["test"]["r2"], 3),
            "test_mae": entry["test"]["mae"],
            "test_rmse": entry["test"]["rmse"],
            "n_test_windows": entry["test"]["n_test_windows"],
            "cv_r2_mean": round(entry["cv_train_val"]["r2_mean"], 3),
            "cv_r2_std": round(entry["cv_train_val"]["r2_std"], 3),
        }

    return {
        "pollutants": pollutants,
        "model_type": "XGBoost (4 independent single-target regressors)",
        "training_scale": "104 INDRA videos, 1,767 sliding windows (2.0s window / 0.5s stride)",
        "validation_method": "Video-level 70/15/15 train/val/test split; GroupKFold(5) on video_id for hyperparameter selection; final metrics from the held-out test set.",
        "caveats": {
            "NOx": "Test R2 is positive but GroupKFold cross-validation was unstable (negative mean R2 across every hyperparameter tried), traced to a small number of bus-heavy videos with a disproportionate NOx factor (~31x a car's). Treat as encouraging, not yet reliable.",
            "PM25": "Genuinely improved vs. the 30-video baseline (R2 -0.03 -> 0.41), driven by more data and per-class distance features, not by changing the target definition. Still moderate accuracy, not production-grade.",
        },
        "source_file": "module2_emission/xgboost/training_metrics_104.json",
    }


@app.get("/api/architecture")
def get_architecture():
    return {
        "implemented": [
            {"stage": "Input Video", "detail": "INDRA traffic camera footage"},
            {"stage": "YOLO11s", "detail": "6-class vehicle detection (models/best.pt)"},
            {"stage": "ByteTrack", "detail": "Multi-object tracking, stable vehicle IDs"},
            {"stage": "Vehicle Tracking", "detail": "Per-frame trajectories"},
            {"stage": "Traffic Feature Extraction", "detail": "Counts, speed, acceleration, density"},
            {"stage": "Distance & Traffic Density", "detail": "Homography-based world coordinates, longitudinal distance"},
            {"stage": "COPERT", "detail": "Per-vehicle-track emission factors"},
            {"stage": "Emission Dataset", "detail": "outputs/copert_emissions_104/vehicle_emissions.csv"},
            {"stage": "XGBoost", "detail": "Emission-rate prediction from traffic-state features"},
            {"stage": "CO2 | NOx | CO | PM2.5", "detail": "Predicted + COPERT-estimated emissions"},
            {"stage": "Traffic Intelligence", "detail": "This dashboard"},
        ],
        "next_phase": [
            {"stage": "TomTom Traffic API", "detail": "Live external traffic data"},
            {"stage": "Navigation / Route Analysis", "detail": "Not implemented"},
            {"stage": "VAC", "detail": "Vehicle Actuated Control -- not implemented"},
            {"stage": "WACC Signal Optimization", "detail": "Not implemented"},
            {"stage": "Hybrid / Quantum Optimization", "detail": "Not implemented"},
        ],
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
