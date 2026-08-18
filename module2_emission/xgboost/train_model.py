"""Task D: train XGBoost models predicting window-level emission RATE (g/s) from
TrafficState-shaped traffic features alone -- no per-vehicle distance tracking, so
Module 4's live dashboard can estimate emissions from the same features it already
computes every 2 seconds, without re-running per-vehicle COPERT.

Four independent single-target XGBRegressor models (one per pollutant), not one
multi-output model -- see docs/MODULE2_XGBOOST_MODEL.md for why.

GroupKFold on video_id: windows from the same video overlap in time (0.5s stride
inside a 2.0s window shares up to 3/4 of its frames with its neighbours), so a
plain random K-fold would leak near-duplicate windows across train/test. Grouping
by video_id guarantees every window from a given video is entirely in one fold.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

POLLUTANTS = ("CO2", "NOx", "CO", "PM25")

FEATURE_COLUMNS = [
    "car_count", "motorcycle_count", "bus_count", "truck_count",
    "autorickshaw_count", "bicycle_count", "total_vehicles", "current_vehicles",
    "average_speed_kmph", "speed_std", "density_veh_per_100m2",
    "mean_acceleration", "acceleration_std", "stopped_vehicle_ratio",
]
# flow_veh_per_min and roi_occupancy are TrafficState fields but are always None
# when reconstructed from a trajectory CSV (windows.py cannot see line-crossing
# events or a calibrated ROI capacity there) -- excluded, see
# docs/MODULE2_XGBOOST_MODEL.md. calibration_profile/data_quality are constant
# across this dataset (single calibration profile, all FULL quality) so they
# carry no signal here and are excluded too.

DEFAULT_XGB_PARAMS = dict(
    n_estimators=200,
    max_depth=3,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    random_state=42,
)


def validate_training_frame(frame: pd.DataFrame) -> None:
    """Raise a clear, actionable error for a malformed training dataset instead of
    letting a raw pandas KeyError/IndexError surface deep inside model training."""
    required = set(FEATURE_COLUMNS) | {"video_id", "window_index"} | {
        f"{p}_rate_g_per_s" for p in POLLUTANTS
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"Training dataset is missing required column(s): {missing}. Expected all "
            f"TrafficState feature columns ({FEATURE_COLUMNS}), video_id, window_index, "
            "and the four *_rate_g_per_s target columns -- regenerate with "
            "module2_emission.xgboost.build_training_dataset."
        )
    if frame.empty:
        raise ValueError(
            "Training dataset has zero rows -- nothing to train on. Check that "
            "module1_manifest.csv has at least one INCLUDED video and that "
            "vehicle_emissions.csv is not empty."
        )


def run_group_kfold(frame: pd.DataFrame, target: str, n_splits: int) -> tuple[pd.DataFrame, list[dict]]:
    X = frame[FEATURE_COLUMNS].to_numpy()
    y = frame[target].to_numpy()
    groups = frame["video_id"].to_numpy()

    oof_predictions = np.full(len(frame), np.nan)
    fold_metrics = []
    gkf = GroupKFold(n_splits=n_splits)
    for fold_index, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups)):
        model = XGBRegressor(**DEFAULT_XGB_PARAMS)
        model.fit(X[train_idx], y[train_idx])
        predictions = model.predict(X[test_idx])
        oof_predictions[test_idx] = predictions
        mae = mean_absolute_error(y[test_idx], predictions)
        rmse = float(np.sqrt(mean_squared_error(y[test_idx], predictions)))
        r2 = r2_score(y[test_idx], predictions) if len(test_idx) > 1 else float("nan")
        fold_metrics.append({
            "fold": fold_index,
            "test_videos": sorted(set(groups[test_idx])),
            "n_test_windows": int(len(test_idx)),
            "mae": float(mae),
            "rmse": rmse,
            "r2": float(r2),
        })

    result = frame[["video_id", "window_index", target]].copy()
    result["prediction"] = oof_predictions
    return result, fold_metrics


def compute_feature_importance(model: XGBRegressor, X: pd.DataFrame) -> dict:
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        importance = dict(zip(FEATURE_COLUMNS, mean_abs_shap.tolist()))
        return {"method": "shap_mean_abs", "importance": importance}
    except Exception as exc:
        print(f"NOTE: SHAP importance failed ({exc}); falling back to XGBoost built-in gain importance.")
        booster_importance = model.get_booster().get_score(importance_type="gain")
        importance = {feature: booster_importance.get(f"f{i}", 0.0) for i, feature in enumerate(FEATURE_COLUMNS)}
        return {"method": "xgboost_gain", "importance": importance}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train per-pollutant XGBoost emission-rate models.")
    parser.add_argument("--training-dataset", default="module2_emission/xgboost/training_dataset.csv")
    parser.add_argument("--model-dir", default="module2_emission/xgboost/models")
    parser.add_argument("--n-splits", type=int, default=5)
    args = parser.parse_args()

    frame = pd.read_csv(args.training_dataset)
    validate_training_frame(frame)
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    n_splits = min(args.n_splits, frame["video_id"].nunique())
    all_metrics = {}
    all_oof = []
    all_importance = {}

    for pollutant in POLLUTANTS:
        target = f"{pollutant}_rate_g_per_s"
        oof_df, fold_metrics = run_group_kfold(frame, target, n_splits)
        oof_df = oof_df.rename(columns={target: "actual"})
        oof_df["pollutant"] = pollutant
        all_oof.append(oof_df)
        all_metrics[pollutant] = fold_metrics

        overall_mae = mean_absolute_error(oof_df["actual"], oof_df["prediction"])
        overall_rmse = float(np.sqrt(mean_squared_error(oof_df["actual"], oof_df["prediction"])))
        overall_r2 = r2_score(oof_df["actual"], oof_df["prediction"])
        all_metrics[pollutant + "_overall"] = {
            "mae": float(overall_mae), "rmse": overall_rmse, "r2": float(overall_r2),
        }
        print(f"{pollutant}: overall OOF MAE={overall_mae:.6g} RMSE={overall_rmse:.6g} R2={overall_r2:.4f}")

        # Final deployed model: fit on all data after CV has already given an
        # honest out-of-fold performance estimate above.
        final_model = XGBRegressor(**DEFAULT_XGB_PARAMS)
        final_model.fit(frame[FEATURE_COLUMNS], frame[target])
        final_model.save_model(str(model_dir / f"{pollutant}_emission_rate_model.json"))

        all_importance[pollutant] = compute_feature_importance(final_model, frame[FEATURE_COLUMNS])

    pd.concat(all_oof, ignore_index=True).to_csv(
        model_dir.parent / "oof_predictions.csv", index=False
    )
    with (model_dir.parent / "training_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {"n_splits": n_splits, "metrics": all_metrics, "feature_importance": all_importance,
             "features": FEATURE_COLUMNS},
            handle, indent=2,
        )
    print(f"\nModels saved to {model_dir}")
    print(f"Out-of-fold predictions: {model_dir.parent / 'oof_predictions.csv'}")
    print(f"Metrics + importance: {model_dir.parent / 'training_metrics.json'}")


if __name__ == "__main__":
    main()
