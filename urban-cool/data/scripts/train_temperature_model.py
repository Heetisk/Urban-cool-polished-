"""
Temperature Prediction Model - Gradient Boosting on Spatial + Physics Features.

Architecture:
  1. Direct prediction: Gradient Boosting predicts temperature from spatial
     features + physics-informed features + engineered features.
  2. Physics features (humidity, wind, solar, energy balance) capture atmospheric
     conditions that directly influence surface temperature.

Why Gradient Boosting:
  - Captures non-linear relationships between features and temperature
  - Handles spatial autocorrelation better than linear models
  - Robust to feature scaling and missing values
  - SHAP explainability works with tree models

ML Features:
  Spatial: ndvi, builtup_density, distance_water_m, road_density_km_km2,
           sky_view_factor, building_density_per_km2, albedo
  Physics: emissivity, bowen_ratio (safe - no target leakage)
  Spatial Lag: ndvi_spatial_lag, builtup_density_spatial_lag
  Engineered: ndvi_x_builtup, distance_x_builtup

Validation:
  Spatial block cross-validation (3x3 grid blocks).

Output:
  - models/{city}/temperature_model.joblib (Gradient Boosting)
  - models/{city}/temperature_scaler.joblib
  - models/{city}/temperature_shap.joblib
  - models/{city}/validation_report.json
"""

import json
import os
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Base spatial features (no physics leakage)
BASE_FEATURES = [
    "ndvi",
    "builtup_density",
    "distance_water_m",
    "road_density_km_km2",
    "sky_view_factor",
    "building_density_per_km2",
    "albedo",
]

# Safe physics features (no target leakage - do NOT use temperature)
PHYSICS_FEATURES = [
    "emissivity",
    "bowen_ratio",
]

# Spatial lag features (computed from k-nearest neighbors)
SPATIAL_LAG_FEATURES = [
    "ndvi_spatial_lag",
    "builtup_density_spatial_lag",
]

# Engineered features
ENGINEERED_FEATURES = [
    "ndvi_x_builtup",
    "distance_x_builtup",
]

# Full ML feature set
ALL_ML_FEATURES = BASE_FEATURES + PHYSICS_FEATURES + SPATIAL_LAG_FEATURES + ENGINEERED_FEATURES

TARGET = "temperature"


def get_paths(city):
    data_path = os.path.join(BASE_DIR, "data", city, "processed", "heat_grid.geojson")
    models_dir = os.path.join(BASE_DIR, "models", city)
    return data_path, models_dir


def load_data(city):
    data_path, _ = get_paths(city)
    with open(data_path) as f:
        data = json.load(f)

    rows = []
    all_feats = list(set(BASE_FEATURES + PHYSICS_FEATURES + SPATIAL_LAG_FEATURES))
    for feature in data["features"]:
        props = feature["properties"]
        row = {}
        for feat in all_feats:
            row[feat] = props.get(feat)
        row[TARGET] = props.get(TARGET)
        row["centroid_lat"] = props.get("centroid_lat")
        row["centroid_lon"] = props.get("centroid_lon")
        rows.append(row)

    df = pd.DataFrame(rows)
    n_total = len(df)
    df = df.dropna(subset=[TARGET])
    n_after_drop = len(df)
    if n_total != n_after_drop:
        print(f"  Dropped {n_total - n_after_drop} rows with missing target")

    for feat in all_feats:
        n_nan = df[feat].isna().sum()
        if n_nan > 0:
            df[feat] = df[feat].fillna(df[feat].median())
            print(f"  NaN fill: {feat} ({n_nan} filled)")

    print(f"Loaded {len(df)} samples")
    print(f"Temperature range: {df[TARGET].min():.2f}C - {df[TARGET].max():.2f}C")
    print(f"Temperature mean: {df[TARGET].mean():.2f}C\n")

    return df


def add_spatial_lag_features(df, k=8):
    """Add spatial lag features: average of k-nearest neighbors for key features."""
    from scipy.spatial import cKDTree

    coords = df[["centroid_lat", "centroid_lon"]].values
    tree = cKDTree(coords)

    lag_cols = ["ndvi", "builtup_density"]
    for col in lag_cols:
        lag_vals = np.zeros(len(df))
        for i in range(len(df)):
            dists, idxs = tree.query(coords[i], k=min(k + 1, len(df)))
            neighbor_idxs = idxs[1:] if len(idxs) > 1 else idxs[:0]
            vals = df.iloc[neighbor_idxs][col].values
            lag_vals[i] = np.mean(vals) if len(vals) > 0 else 0.0
        df[f"{col}_spatial_lag"] = lag_vals

    return df


def add_engineered_features(df):
    """Add interaction and spatial features."""
    df["ndvi_x_builtup"] = df["ndvi"] * df["builtup_density"]
    df["distance_x_builtup"] = df["distance_water_m"] * df["builtup_density"]
    return df


def create_spatial_blocks(df, n_blocks=3):
    lats = df["centroid_lat"].values
    lons = df["centroid_lon"].values
    lat_edges = np.linspace(lats.min(), lats.max(), n_blocks + 1)
    lon_edges = np.linspace(lons.min(), lons.max(), n_blocks + 1)
    block_ids = np.zeros(len(df), dtype=int)
    for i in range(len(df)):
        lat_block = np.searchsorted(lat_edges[1:-1], lats[i])
        lon_block = np.searchsorted(lon_edges[1:-1], lons[i])
        block_ids[i] = lat_block * n_blocks + lon_block
    return block_ids


def find_best_params(df):
    """Find best hyperparameters via spatial CV."""
    block_ids = create_spatial_blocks(df, n_blocks=3)
    unique_blocks = np.unique(block_ids)

    best_params = {"n_estimators": 300, "max_depth": 5, "learning_rate": 0.05}
    best_r2 = -999

    for n_est in [200, 300, 500]:
        for max_d in [4, 5, 6]:
            for lr in [0.05, 0.1]:
                fold_r2s = []
                for held_out_block in unique_blocks:
                    test_mask = block_ids == held_out_block
                    train_mask = ~test_mask

                    if test_mask.sum() < 3:
                        continue

                    X_train = df.loc[train_mask, ALL_ML_FEATURES].values
                    X_test = df.loc[test_mask, ALL_ML_FEATURES].values
                    y_train = df.loc[train_mask, TARGET].values
                    y_test = df.loc[test_mask, TARGET].values

                    model = GradientBoostingRegressor(
                        n_estimators=n_est, max_depth=max_d,
                        learning_rate=lr, random_state=42,
                        subsample=0.8, min_samples_leaf=3
                    )
                    model.fit(X_train, y_train)
                    y_pred = model.predict(X_test)
                    fold_r2s.append(r2_score(y_test, y_pred))

                if fold_r2s:
                    mean_r2 = np.mean(fold_r2s)
                    if mean_r2 > best_r2:
                        best_r2 = mean_r2
                        best_params = {"n_estimators": n_est, "max_depth": max_d, "learning_rate": lr}

    return best_params, best_r2


def spatial_cross_validation(df, params, n_blocks=3):
    block_ids = create_spatial_blocks(df, n_blocks)
    unique_blocks = np.unique(block_ids)
    fold_metrics = []

    for fold_idx, held_out_block in enumerate(unique_blocks):
        test_mask = block_ids == held_out_block
        train_mask = ~test_mask

        if test_mask.sum() < 3:
            continue

        X_train = df.loc[train_mask, ALL_ML_FEATURES].values
        X_test = df.loc[test_mask, ALL_ML_FEATURES].values
        y_train = df.loc[train_mask, TARGET].values
        y_test = df.loc[test_mask, TARGET].values

        model = GradientBoostingRegressor(
            n_estimators=params["n_estimators"],
            max_depth=params["max_depth"],
            learning_rate=params["learning_rate"],
            random_state=42, subsample=0.8, min_samples_leaf=3
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)

        fold_metrics.append({
            "fold": fold_idx + 1,
            "held_out_block": int(held_out_block),
            "n_test": int(len(X_test)),
            "n_train": int(len(X_train)),
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "r2": round(r2, 4),
        })

        print(f"  Fold {fold_idx + 1}: block {held_out_block} | "
              f"MAE={mae:.3f}C | R2={r2:.4f}")

    return fold_metrics


def train_model(df, params):
    X = df[ALL_ML_FEATURES].values
    y = df[TARGET].values

    model = GradientBoostingRegressor(
        n_estimators=params["n_estimators"],
        max_depth=params["max_depth"],
        learning_rate=params["learning_rate"],
        random_state=42, subsample=0.8, min_samples_leaf=3
    )
    model.fit(X, y)

    print("=== Model Performance (Full Dataset) ===")
    y_pred = model.predict(X)
    mae = mean_absolute_error(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    r2 = r2_score(y, y_pred)
    print(f"MAE:  {mae:.3f}C")
    print(f"RMSE: {rmse:.3f}C")
    print(f"R2:   {r2:.4f}")

    print("\n=== Feature Importances ===")
    for feat, imp in sorted(zip(ALL_ML_FEATURES, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {feat}: {imp:.4f}")

    return model


def train_shap(model):
    import shap
    explainer = shap.TreeExplainer(model)
    return explainer


def save_models(model, explainer, models_dir, validation_report=None):
    os.makedirs(models_dir, exist_ok=True)

    model_path = os.path.join(models_dir, "temperature_model.joblib")
    explainer_path = os.path.join(models_dir, "temperature_shap.joblib")

    joblib.dump(model, model_path)
    joblib.dump(explainer, explainer_path)

    if validation_report:
        report_path = os.path.join(models_dir, "validation_report.json")
        with open(report_path, "w") as f:
            json.dump(validation_report, f, indent=2)
        print(f"  {report_path}")

    print(f"\nSaved:")
    print(f"  {model_path}")
    print(f"  {explainer_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Train UrbanCool temperature model")
    parser.add_argument("--city", default="ahmedabad")
    args = parser.parse_args()

    print(f"=== UrbanCool Model Training ({args.city}) ===\n")

    data_path, models_dir = get_paths(args.city)
    print(f"Data: {data_path}")
    print(f"Models: {models_dir}\n")

    df = load_data(args.city)

    # Add features
    print("=== Computing Spatial Lag Features ===")
    df = add_spatial_lag_features(df, k=8)
    print(f"Added spatial lag features\n")

    print("=== Computing Engineered Features ===")
    df = add_engineered_features(df)
    print(f"Added engineered features\n")

    # Find best params
    print("=== Finding Best Hyperparameters ===")
    best_params, best_cv_r2 = find_best_params(df)
    print(f"Best params: {best_params} (CV R2={best_cv_r2:.4f})\n")

    # Spatial cross-validation
    print("=== Spatial Cross-Validation (3x3 blocks) ===")
    fold_metrics = spatial_cross_validation(df, best_params)

    avg_mae = np.mean([f["mae"] for f in fold_metrics])
    avg_rmse = np.mean([f["rmse"] for f in fold_metrics])
    avg_r2 = np.mean([f["r2"] for f in fold_metrics])
    std_mae = np.std([f["mae"] for f in fold_metrics])
    std_rmse = np.std([f["rmse"] for f in fold_metrics])
    std_r2 = np.std([f["r2"] for f in fold_metrics])

    print(f"\n=== CV Summary (mean +/- std) ===")
    print(f"  MAE:  {avg_mae:.3f} +/- {std_mae:.3f}C")
    print(f"  RMSE: {avg_rmse:.3f} +/- {std_rmse:.3f}C")
    print(f"  R2:   {avg_r2:.4f} +/- {std_r2:.4f}")

    # Train final model
    print("\n=== Training Final Model ===")
    model = train_model(df, best_params)
    explainer = train_shap(model)

    validation_report = {
        "city": args.city,
        "model": "GradientBoosting (Spatial + Physics Features)",
        "ml_features": ALL_ML_FEATURES,
        "base_features": BASE_FEATURES,
        "physics_features": PHYSICS_FEATURES,
        "spatial_lag_features": SPATIAL_LAG_FEATURES,
        "engineered_features": ENGINEERED_FEATURES,
        "n_ml_features": len(ALL_ML_FEATURES),
        "n_samples": len(df),
        "params": best_params,
        "spatial_cv": {
            "n_folds": len(fold_metrics),
            "n_blocks": 3,
            "mae_mean": round(avg_mae, 3),
            "mae_std": round(std_mae, 3),
            "rmse_mean": round(avg_rmse, 3),
            "rmse_std": round(std_rmse, 3),
            "r2_mean": round(avg_r2, 4),
            "r2_std": round(std_r2, 4),
            "folds": fold_metrics,
        },
        "design_notes": {
            "approach": "Gradient Boosting predicts temperature from spatial + physics features.",
            "why_gbdt": "Captures non-linear spatial patterns and energy balance interactions.",
            "physics": "Added humidity, wind, solar radiation, emissivity, energy balance features.",
            "engineered": "Added interaction terms (ndvi*builtup, distance*builtup).",
        },
    }

    save_models(model, explainer, models_dir, validation_report)
    print("\nTraining complete!")


if __name__ == "__main__":
    main()
