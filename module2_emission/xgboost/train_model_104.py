"""104-video XGBoost emission-rate model: video-level train/val/test split + GroupKFold
CV + a small principled hyperparameter search per pollutant (especially aimed at PM2.5,
which the 30-video baseline (module2_emission/xgboost/train_model.py) could not learn at
all -- see docs/MODULE2_XGBOOST_MODEL.md). No target manipulation: same rate definition,
same four pollutants, same GroupKFold-on-video_id discipline as the baseline.

Methodology:
  1. Split all INCLUDED videos' ids into train/val/test (70/15/15, fixed seed) -- test is
     never touched until the very end, for an unbiased final comparison against baseline.
  2. For each pollutant, GroupKFold(n_splits=5) CV on train+val (grouped by video_id) is
     used to score a small hyperparameter grid; the config with the best mean CV R² is
     selected. This is the same validation discipline as the baseline, just also used for
     tuning instead of a single fixed hyperparameter set.
  3. The selected config is refit on all of train+val, then evaluated once on the held-out
     test set -- this is the number to compare against the baseline's OOF metrics.
  4. The final model (refit on train+val) is what gets saved -- not fit on test data.
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

BASE_FEATURE_COLUMNS = [
    "car_count", "motorcycle_count", "bus_count", "truck_count",
    "autorickshaw_count", "bicycle_count", "total_vehicles", "current_vehicles",
    "average_speed_kmph", "speed_std", "density_veh_per_100m2",
    "mean_acceleration", "acceleration_std", "stopped_vehicle_ratio",
]
ENGINEERED_FEATURE_COLUMNS = [
    "car_distance_km", "motorcycle_distance_km", "bus_distance_km", "truck_distance_km",
    "autorickshaw_distance_km", "bicycle_distance_km", "total_distance_km_in_window",
    "car_ratio", "motorcycle_ratio", "bus_ratio", "truck_ratio",
    "window_position_frac", "prev_total_vehicles", "delta_total_vehicles",
]
FEATURE_COLUMNS = BASE_FEATURE_COLUMNS + ENGINEERED_FEATURE_COLUMNS

# A small, principled grid -- not an exhaustive search, but covers the axes most
# likely to matter for a still-small (~1,300-window), skewed-target dataset:
# tree depth/complexity, learning rate, and regularization strength.
HYPERPARAM_GRID = [
    dict(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0),
    dict(n_estimators=300, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0),
    dict(n_estimators=150, max_depth=2, learning_rate=0.1, subsample=1.0, colsample_bytree=1.0, reg_lambda=0.1),
    dict(n_estimators=400, max_depth=3, learning_rate=0.02, subsample=0.7, colsample_bytree=0.7, reg_lambda=2.0),
    dict(n_estimators=100, max_depth=2, learning_rate=0.1, subsample=1.0, colsample_bytree=1.0, reg_lambda=5.0),
]


def video_level_split(video_ids: list[str], train_frac=0.70, val_frac=0.15, seed=42):
    rng = np.random.default_rng(seed)
    shuffled = list(video_ids)
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_train = round(n * train_frac)
    n_val = round(n * val_frac)
    train_ids = set(shuffled[:n_train])
    val_ids = set(shuffled[n_train:n_train + n_val])
    test_ids = set(shuffled[n_train + n_val:])
    assert not (train_ids & val_ids) and not (train_ids & test_ids) and not (val_ids & test_ids)
    return train_ids, val_ids, test_ids


def group_kfold_score(X, y, groups, params, n_splits) -> dict:
    n_splits = min(n_splits, len(set(groups)))
    if n_splits < 2:
        return {"r2_mean": float("nan"), "r2_std": float("nan"), "mae_mean": float("nan"), "rmse_mean": float("nan")}
    gkf = GroupKFold(n_splits=n_splits)
    r2s, maes, rmses = [], [], []
    for train_idx, test_idx in gkf.split(X, y, groups):
        model = XGBRegressor(random_state=42, **params)
        model.fit(X[train_idx], y[train_idx])
        pred = model.predict(X[test_idx])
        r2s.append(r2_score(y[test_idx], pred) if len(test_idx) > 1 else np.nan)
        maes.append(mean_absolute_error(y[test_idx], pred))
        rmses.append(np.sqrt(mean_squared_error(y[test_idx], pred)))
    return {
        "r2_mean": float(np.nanmean(r2s)), "r2_std": float(np.nanstd(r2s)),
        "mae_mean": float(np.mean(maes)), "rmse_mean": float(np.mean(rmses)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train 104-video XGBoost emission-rate models.")
    parser.add_argument("--training-dataset", default="module2_emission/xgboost/training_dataset_104.csv")
    parser.add_argument("--model-dir", default="module2_emission/xgboost/models_104")
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    frame = pd.read_csv(args.training_dataset)
    missing = sorted(set(FEATURE_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Training dataset missing engineered feature column(s): {missing}")

    video_ids = sorted(frame["video_id"].unique())
    train_ids, val_ids, test_ids = video_level_split(video_ids, seed=args.seed)
    print(f"Video-level split: {len(train_ids)} train / {len(val_ids)} val / {len(test_ids)} test "
          f"(of {len(video_ids)} total videos)")

    train_val = frame[frame["video_id"].isin(train_ids | val_ids)].reset_index(drop=True)
    test = frame[frame["video_id"].isin(test_ids)].reset_index(drop=True)
    print(f"Windows: {len(train_val)} train+val / {len(test)} test")

    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    report = {"split": {"train_videos": sorted(train_ids), "val_videos": sorted(val_ids),
                         "test_videos": sorted(test_ids)}, "pollutants": {}}

    X_train_val = train_val[FEATURE_COLUMNS].to_numpy()
    groups_train_val = train_val["video_id"].to_numpy()
    X_test = test[FEATURE_COLUMNS].to_numpy()

    for pollutant in POLLUTANTS:
        target = f"{pollutant}_rate_g_per_s"
        y_train_val = train_val[target].to_numpy()
        y_test = test[target].to_numpy()

        grid_results = []
        for params in HYPERPARAM_GRID:
            cv = group_kfold_score(X_train_val, y_train_val, groups_train_val, params, args.n_splits)
            grid_results.append({"params": params, "cv": cv})
        best = max(grid_results, key=lambda r: r["cv"]["r2_mean"])
        print(f"{pollutant}: best CV R2={best['cv']['r2_mean']:.4f} (+/-{best['cv']['r2_std']:.4f}) "
              f"params={best['params']}")

        final_model = XGBRegressor(random_state=42, **best["params"])
        final_model.fit(X_train_val, y_train_val)
        test_pred = final_model.predict(X_test)
        test_r2 = r2_score(y_test, test_pred) if len(y_test) > 1 else float("nan")
        test_mae = mean_absolute_error(y_test, test_pred)
        test_rmse = float(np.sqrt(mean_squared_error(y_test, test_pred)))
        print(f"{pollutant}: held-out TEST R2={test_r2:.4f} MAE={test_mae:.6g} RMSE={test_rmse:.6g}")

        final_model.save_model(str(model_dir / f"{pollutant}_emission_rate_model.json"))

        report["pollutants"][pollutant] = {
            "best_params": best["params"],
            "cv_train_val": best["cv"],
            "grid_search": grid_results,
            "test": {"r2": float(test_r2), "mae": float(test_mae), "rmse": test_rmse, "n_test_windows": len(y_test)},
        }

    report["features"] = FEATURE_COLUMNS
    with (model_dir.parent / "training_metrics_104.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(f"\nModels saved to {model_dir}")
    print(f"Metrics: {model_dir.parent / 'training_metrics_104.json'}")


if __name__ == "__main__":
    main()
