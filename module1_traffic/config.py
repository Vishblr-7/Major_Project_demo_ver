# ===========================
# Project Configuration
# ===========================
#
# Module 0 note: path-ish constants (model path, six-class mapping, emission
# quality thresholds) now come from configs/project_config.yaml, so there is
# one place to change them. Camera calibration (ROI, homography, resolution
# profiles) stays hardcoded here, untouched, exactly as it was before the
# restructure -- these values were measured for the physical camera setup and
# must not silently drift because a config file changed.

from configs.loader import load_config

_project_config = load_config()
_paths = _project_config["paths"]
_thresholds = _project_config["emission_quality_thresholds"]

# Custom vehicle detector. Keep all entry points on the same trained model.
MODEL_PATH = _paths["model_path"]

VIDEO_PATH = "videos/video2.mp4"

OUTPUT_VIDEO = "outputs/videos/tracked_output.mp4"

# Vehicle classes, sourced from configs/project_config.yaml's
# vehicle_classes mapping (id -> name), ordered by class id. Must match
# models/best.pt's training labels exactly -- do not reorder.
VEHICLE_CLASSES = [
    name for _, name in sorted(_project_config["vehicle_classes"].items())
]

CONFIDENCE_THRESHOLD = 0.35
# Backward-compatible alias used by existing helper scripts.
CONFIDENCE = CONFIDENCE_THRESHOLD

SHOW_WINDOW = True

LINE_THICKNESS = 2

TEXT_SCALE = 0.6

# ============================================================
# CAMERA + ADAPTIVE HOMOGRAPHY CALIBRATION
# ============================================================
# Do not change any value in this section as part of a refactor. These were
# calibrated for the physical INDRA camera setup.

# ------------------------------------------------------------
# MASTER CALIBRATION
# ------------------------------------------------------------
MASTER_WIDTH = 1920
MASTER_HEIGHT = 1080

# ------------------------------------------------------------
# MASTER ROAD ROI
# ------------------------------------------------------------
# P1 = far-left, P2 = far-right, P3 = near-right, P4 = near-left.
# These points must be calibrated for the actual 1920x1080 INDRA camera view.
MASTER_ROI_POINTS = [
    (250, 230),   # P1
    (1670, 260),  # P2
    (1810, 1030), # P3
    (100, 1030),  # P4
]

# Master 1920x1080 counting line. It is scaled alongside the ROI.
MASTER_COUNTING_LINE_START = (170, 620)
MASTER_COUNTING_LINE_END = (1750, 620)

# Compatibility aliases for older helper scripts; main.py uses adaptive points.
LINE_START = MASTER_COUNTING_LINE_START
LINE_END = MASTER_COUNTING_LINE_END

# ------------------------------------------------------------
# REAL-WORLD ROAD DIMENSIONS
# ------------------------------------------------------------
# Replace these with physically measured road dimensions when available.
ROAD_WIDTH_M = 7.0
ROAD_LENGTH_M = 20.0

# ------------------------------------------------------------
# HOMOGRAPHY DESTINATION
# ------------------------------------------------------------
# P4 -> (0, 0), P3 -> (ROAD_WIDTH_M, 0), P2 ->
# (ROAD_WIDTH_M, ROAD_LENGTH_M), P1 -> (0, ROAD_LENGTH_M).
WORLD_POINTS = [
    (0.0, ROAD_LENGTH_M),
    (ROAD_WIDTH_M, ROAD_LENGTH_M),
    (ROAD_WIDTH_M, 0.0),
    (0.0, 0.0),
]

# ------------------------------------------------------------
# SUPPORTED CAMERA RESOLUTIONS
# ------------------------------------------------------------
SUPPORTED_RESOLUTIONS = {
    (1920, 1080): "H1_1080P",
    (1280, 720): "H2_720P",
    (640, 360): "H3_360P",
}

# ------------------------------------------------------------
# SPEED FILTERING (sourced from configs/project_config.yaml)
# ------------------------------------------------------------
MAX_REASONABLE_SPEED_KMPH = _thresholds["max_reasonable_speed_kmph"]
MAX_REASONABLE_ACCEL_MPS2 = _thresholds["max_reasonable_accel_mps2"]
SPEED_SMOOTHING_ALPHA = _thresholds["speed_smoothing_alpha"]
SPEED_HISTORY_LENGTH = 7
POSITION_HISTORY_SECONDS = 0.5
MOVING_SPEED_THRESHOLD_KMPH = _thresholds["moving_speed_threshold_kmph"]
FPS = 30  # Fallback when the input source does not report FPS.

# Do not silently apply this calibration to a different resolution.
REQUIRE_SUPPORTED_RESOLUTION = True

# ------------------------------------------------------------
# CALIBRATION / EMISSION DATA QUALITY
# ------------------------------------------------------------
# Maximum error (metres) when transforming calibrated ROI corners to WORLD_POINTS.
GEOMETRY_MAX_REPROJECTION_ERROR_M = 0.05
GEOMETRY_MIN_ROI_AREA_PX = 1_000.0

# Emission-model training only uses established, physically plausible tracks.
MIN_TRACK_LENGTH = _thresholds["min_track_length"]

# Dominant vehicle travel direction in road-world coordinates. WORLD_POINTS use
# the road length as the Y axis, so lateral X displacement is intentionally ignored.
FLOW_DIRECTION_WORLD = (0.0, 1.0)

# ===========================
# CSV Configuration
# ===========================

VEHICLE_CSV_PATH = "outputs/csv/video2_vehicles.csv"
TRAFFIC_CSV_PATH = "outputs/csv/video2_traffic.csv"
# Backward-compatible aliases.
VEHICLE_CSV = VEHICLE_CSV_PATH
TRAFFIC_CSV = TRAFFIC_CSV_PATH

# How often traffic statistics are saved
AGGREGATION_INTERVAL = 1.0  # seconds

# How often the shared TrafficState snapshot (module1_traffic/traffic_state.py)
# is emitted for downstream Modules 2/3/4 consumption. Independent of, and
# additive to, AGGREGATION_INTERVAL -- does not change any existing CSV.
TRAFFIC_STATE_INTERVAL_S = 2.0

# Road capacity for density calculation
ROAD_CAPACITY = 50

# Maximum expected road speed
MAX_SPEED = 60
