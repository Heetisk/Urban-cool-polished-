"""
Model Comparison (Physics Baseline + ML Residual).

Compares different ML models for predicting the spatial residual
on top of the physics baseline. Uses spatial block cross-validation.

Architecture for all models:
  1. Physics baseline (linear regression on solar, albedo, emissivity, SVF, humidity, wind)
  2. ML model predicts residual (actual - physics_predicted) using 7 urban morphology features
  3. Final = physics_baseline + ML_residual

Output:
- Console comparison table
- models/{city}/validation_report.json (updated with comparison)
"""

import json
import os
import sys
import numpy as np
import pandas as pd
import joblib
import time
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "data", "scripts"))

from train_temperature_model import (
    ML_FEATURES, PHYSICS_FEATURES, PHYSICS_COLS, TARGET, load_data,
    create_spatial_blocks, _fit_physics_on_data,
)


def _get_best_alpha(city):
    """Read best alpha from validation_report.json."""
    report_path = os.path.join(BASE_DIR, "models", city, "validation_report.json")
    if os.path.exists(report_path):
        with open(report_path) as f:
            report = json.load(f)
        return report.get("alpha", 1.0)
    return 1.0

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False


def spatial_cv_physics_ml(model_class, model_params, df, n_blocks=3, label=""):
    """Run spatial block CV: physics baseline + ML residual (no leakage)."""
    block_ids = create_spatial_blocks(df, n_blocks)
    unique_blocks = np.unique(block_ids)

    fold_metrics = []
    for held_out_block in unique_blocks:
        test_mask = block_ids == held_out_block
        train_mask = ~test_mask

        if test_mask.sum() < 3:
            continue

        # Fit physics on TRAIN only (no leakage)
        physics_model = _fit_physics_on_data(df.loc[train_mask])

        X_train_ml = df.loc[train_mask, ML_FEATURES].values
        X_test_ml = df.loc[test_mask, ML_FEATURES].values
        y_test_actual = df.loc[test_mask, TARGET].values

        # Compute residual on TRAIN
        physics_train = physics_model.predict(df.loc[train_mask, PHYSICS_COLS].fillna(0).values)
        y_train_res = df.loc[train_mask, TARGET].values - physics_train

        # Predict physics on TEST
        physics_test = physics_model.predict(df.loc[test_mask, PHYSICS_COLS].fillna(0).values)

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train_ml)
        X_test_s = scaler.transform(X_test_ml)

        model = model_class(**model_params)
        model.fit(X_train_s, y_train_res)

        y_pred_res = model.predict(X_test_s)
        y_pred = physics_test + y_pred_res

        mae = mean_absolute_error(y_test_actual, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test_actual, y_pred))
        r2 = r2_score(y_test_actual, y_pred)

        # Physics only
        mae_ph = mean_absolute_error(y_test_actual, physics_test)
        r2_ph = r2_score(y_test_actual, physics_test)

        fold_metrics.append({
            "mae": mae, "rmse": rmse, "r2": r2,
            "mae_physics_only": mae_ph, "r2_physics_only": r2_ph,
            "n_test": len(X_test_ml),
        })

    if not fold_metrics:
        return {"mae_mean": None, "rmse_mean": None, "r2_mean": None}

    return {
        "mae_mean": round(np.mean([f["mae"] for f in fold_metrics]), 4),
        "mae_std": round(np.std([f["mae"] for f in fold_metrics]), 4),
        "rmse_mean": round(np.mean([f["rmse"] for f in fold_metrics]), 4),
        "rmse_std": round(np.std([f["rmse"] for f in fold_metrics]), 4),
        "r2_mean": round(np.mean([f["r2"] for f in fold_metrics]), 4),
        "r2_std": round(np.std([f["r2"] for f in fold_metrics]), 4),
        "mae_physics_only": round(np.mean([f["mae_physics_only"] for f in fold_metrics]), 4),
        "r2_physics_only": round(np.mean([f["r2_physics_only"] for f in fold_metrics]), 4),
        "n_folds": len(fold_metrics),
    }


def run_comparison(city):
    """Run full model comparison for a city."""
    print(f"\n{'='*60}")
    print(f"MODEL COMPARISON - {city.upper()}")
    print(f"{'='*60}\n")

    df = load_data(city)

    print(f"ML Features: {len(ML_FEATURES)}")
    print(f"Samples: {len(df)}\n")

    best_alpha = _get_best_alpha(city)
    print(f"Using deployed alpha: {best_alpha}\n")

    models = [
        ("Linear Regression", LinearRegression, {}),
        ("Ridge Regression (deployed)", Ridge, {"alpha": best_alpha}),
        ("Ridge (alpha=1.0)", Ridge, {"alpha": 1.0}),
        ("Random Forest", RandomForestRegressor, {
            "n_estimators": 200, "max_depth": 10, "random_state": 42, "n_jobs": -1,
        }),
    ]

    if HAS_XGBOOST:
        models.append(("XGBoost", xgb.XGBRegressor, {
            "n_estimators": 200, "max_depth": 6, "learning_rate": 0.1,
            "reg_alpha": 0.1, "reg_lambda": 1.0, "subsample": 0.8,
            "colsample_bytree": 0.8, "objective": "reg:squarederror",
            "random_state": 42, "verbosity": 0,
        }))

    results = {}
    for name, cls, params in models:
        print(f"--- {name} ---")
        t0 = time.time()
        res = spatial_cv_physics_ml(cls, params, df)
        elapsed = time.time() - t0

        results[name] = {**res, "time_s": round(elapsed, 2)}

        improvement = (1 - res["mae_mean"] / res["mae_physics_only"]) * 100 if res["mae_physics_only"] else 0
        print(f"  MAE:     {res['mae_mean']:.4f} +/- {res['mae_std']:.4f}")
        print(f"  R2:      {res['r2_mean']:.4f} +/- {res['r2_std']:.4f}")
        print(f"  Physics: MAE={res['mae_physics_only']:.4f} | ML improvement: {improvement:+.1f}%")
        print(f"  Time: {elapsed:.1f}s\n")

    print(f"\n{'='*70}")
    print(f"COMPARISON TABLE")
    print(f"{'='*70}")
    print(f"{'Model':<25} {'MAE (mean+/-std)':<25} {'R2 (mean+/-std)':<25} {'ML Improve':<12}")
    print("-" * 87)
    for name, res in results.items():
        improvement = (1 - res["mae_mean"] / res["mae_physics_only"]) * 100 if res["mae_physics_only"] else 0
        print(f"{name:<25} {res['mae_mean']:.4f}+/-{res['mae_std']:.4f}   {res['r2_mean']:.4f}+/-{res['r2_std']:.4f}   {improvement:+.1f}%")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Model comparison")
    parser.add_argument("--city", default="ahmedabad")
    args = parser.parse_args()

    results = run_comparison(args.city)

    # Save results
    report_path = os.path.join(BASE_DIR, "models", args.city, "validation_report.json")
    with open(report_path) as f:
        report = json.load(f)

    report["model_comparison"] = results

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nSaved comparison to {report_path}")


if __name__ == "__main__":
    main()
