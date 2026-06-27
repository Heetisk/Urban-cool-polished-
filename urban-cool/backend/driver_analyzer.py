"""
Driver Analyzer - SHAP-based explanations for temperature predictions.

Architecture:
  Gradient Boosting predicts temperature from spatial + physics features.
  Physics features capture atmospheric conditions that influence temperature.

Supports multiple cities - each city has its own trained model.
"""

import os
import json
import numpy as np
import joblib

from config.config_loader import (
    get_model_path, get_shap_path, get_heat_grid_path, get_city_config
)

# Base spatial features
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

ALL_ML_FEATURES = BASE_FEATURES + PHYSICS_FEATURES + SPATIAL_LAG_FEATURES + ENGINEERED_FEATURES

FEATURE_NAMES = {
    "ndvi": "Vegetation (NDVI)",
    "builtup_density": "Built-up Density",
    "distance_water_m": "Distance to Water",
    "road_density_km_km2": "Road Density",
    "sky_view_factor": "Sky View Factor",
    "building_density_per_km2": "Building Density",
    "albedo": "Surface Albedo",
    "emissivity": "Surface Emissivity",
    "bowen_ratio": "Bowen Ratio",
    "ndvi_spatial_lag": "Neighbor Vegetation",
    "builtup_density_spatial_lag": "Neighbor Built-up",
    "ndvi_x_builtup": "NDVI x Built-up Interaction",
    "distance_x_builtup": "Distance x Built-up Interaction",
}

HEAT_INCREASERS = {
    "builtup_density", "distance_water_m", "road_density_km_km2",
    "building_density_per_km2",
    "ndvi_x_builtup", "distance_x_builtup",
}
HEAT_DECREASERS = {
    "ndvi", "sky_view_factor", "albedo",
    "emissivity",
    "ndvi_spatial_lag", "builtup_density_spatial_lag",
}


class DriverAnalyzer:
    def __init__(self):
        self.model = None
        self.explainer = None
        self.cells = {}
        self.city = None
        self._loaded = False

    def load(self, city: str = "ahmedabad"):
        """Load model, explainer, and data."""
        model_path = get_model_path(city)
        explainer_path = get_shap_path(city)
        data_path = get_heat_grid_path(city)

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"No model found for city '{city}' at {model_path}")

        self.model = joblib.load(model_path)

        if os.path.exists(explainer_path):
            self.explainer = joblib.load(explainer_path)
        else:
            self.explainer = None

        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)

        self.cells = {}
        for feature in data["features"]:
            props = feature["properties"]
            cell_id = props["cell_id"]
            self.cells[cell_id] = props

        self._compute_spatial_lags()
        self._add_engineered_features()
        self.city = city
        self._loaded = True
        print(f"DriverAnalyzer loaded: {len(self.cells)} cells for city '{city}'")

    def _ensure_loaded(self, city: str = None):
        target_city = city or self.city or "ahmedabad"
        if not self._loaded or self.city != target_city:
            self.load(target_city)

    def ensure_loaded(self, city: str = None):
        """Public wrapper for _ensure_loaded."""
        self._ensure_loaded(city)

    def _compute_spatial_lags(self, k=8):
        """Compute spatial lag features for all cells (vectorized)."""
        from scipy.spatial import cKDTree

        cell_ids = list(self.cells.keys())
        coords = []
        for cid in cell_ids:
            c = self.cells[cid]
            coords.append([c.get("centroid_lat", 0), c.get("centroid_lon", 0)])
        coords = np.array(coords)

        tree = cKDTree(coords)
        lag_cols = ["ndvi", "builtup_density"]

        # Vectorized query: get k+1 nearest neighbors for all cells at once
        n_cells = len(cell_ids)
        k_actual = min(k + 1, n_cells)
        dists, idxs = tree.query(coords, k=k_actual)

        # Ensure idxs is 2D (handles case where n_cells == 1)
        if idxs.ndim == 1:
            idxs = idxs.reshape(1, -1)

        for col in lag_cols:
            # Build matrix of feature values
            col_vals = np.array([self.cells[cid].get(col, 0) or 0 for cid in cell_ids])

            # For each cell, compute mean of k nearest neighbors (excluding self)
            for i in range(n_cells):
                neighbor_idxs = idxs[i]
                # Exclude self (first entry is self if k includes it)
                if len(neighbor_idxs) > 1 and neighbor_idxs[0] == i:
                    neighbor_idxs = neighbor_idxs[1:]
                elif len(neighbor_idxs) > 1:
                    neighbor_idxs = neighbor_idxs[:-1]

                vals = col_vals[neighbor_idxs]
                self.cells[cell_ids[i]][f"{col}_spatial_lag"] = float(np.mean(vals)) if len(vals) > 0 else 0.0

    def _add_engineered_features(self):
        """Add interaction and spatial features."""
        for cid, cell in self.cells.items():
            ndvi = cell.get("ndvi", 0) or 0
            builtup = cell.get("builtup_density", 0) or 0
            distance = cell.get("distance_water_m", 0) or 0
            cell["ndvi_x_builtup"] = ndvi * builtup
            cell["distance_x_builtup"] = distance * builtup

    def _get_ml_features(self, cell_id: str) -> np.ndarray:
        """Extract ML feature vector for a cell."""
        cell = self.cells.get(cell_id)
        if cell is None:
            raise ValueError(f"Cell {cell_id} not found")

        features = []
        for feat in ALL_ML_FEATURES:
            val = cell.get(feat)
            if val is None:
                val = 0.0
            features.append(float(val))

        return np.array(features).reshape(1, -1)

    def predict_temperature(self, cell_id: str, city: str = None) -> dict:
        """Predict temperature using Gradient Boosting model."""
        self._ensure_loaded(city)

        if cell_id not in self.cells:
            raise KeyError(f"Cell '{cell_id}' not found in {self.city} data")
        cell = self.cells[cell_id]

        X = self._get_ml_features(cell_id)
        predicted_temp = float(self.model.predict(X)[0])
        actual_temp = cell.get("temperature", 0)

        return {
            "cell_id": cell_id,
            "predicted_temp": round(predicted_temp, 2),
            "actual_temp": round(float(actual_temp), 2),
            "error": round(abs(predicted_temp - actual_temp), 2),
        }

    def analyze_drivers(self, cell_id: str, city: str = None) -> dict:
        """Compute feature contribution analysis using SHAP TreeExplainer."""
        self._ensure_loaded(city)

        if cell_id not in self.cells:
            raise KeyError(f"Cell '{cell_id}' not found in {self.city} data")
        cell = self.cells[cell_id]

        X = self._get_ml_features(cell_id)
        predicted_temp = float(self.model.predict(X)[0])
        actual_temp = cell.get("temperature", 0)

        drivers = []
        if self.explainer is not None:
            shap_values = self.explainer.shap_values(X)
            if isinstance(shap_values, np.ndarray):
                shap_vals = shap_values[0] if len(shap_values.shape) > 1 else shap_values
            else:
                shap_vals = shap_values

            for i, feat in enumerate(ALL_ML_FEATURES):
                value = cell.get(feat, 0) or 0.0
                impact = float(shap_vals[i])
                direction = "increases temperature" if impact > 0 else "decreases temperature"
                drivers.append({
                    "feature": feat,
                    "feature_name": FEATURE_NAMES.get(feat, feat),
                    "value": round(float(value), 4),
                    "impact": round(impact, 4),
                    "direction": direction,
                })
        else:
            for feat in ALL_ML_FEATURES:
                drivers.append({
                    "feature": feat,
                    "feature_name": FEATURE_NAMES.get(feat, feat),
                    "value": round(float(cell.get(feat, 0) or 0), 4),
                    "impact": 0.0,
                    "direction": "unknown",
                })

        drivers.sort(key=lambda x: abs(x["impact"]), reverse=True)

        top_drivers = [d for d in drivers if abs(d["impact"]) > 0.001][:5]
        summary_parts = []
        for d in top_drivers:
            impact_str = f"+{d['impact']:.2f}" if d['impact'] > 0 else f"{d['impact']:.2f}"
            summary_parts.append(f"{d['feature_name']} ({impact_str})")
        summary_parts.append(f"Predicted: {predicted_temp:.1f}C")
        summary = " | ".join(summary_parts)

        return {
            "cell_id": cell_id,
            "predicted_temp": round(predicted_temp, 2),
            "actual_temp": round(float(actual_temp), 2),
            "drivers": drivers,
            "summary": summary,
        }

    def get_global_drivers(self, city: str = None) -> dict:
        """Compute global feature importance using SHAP."""
        self._ensure_loaded(city)

        if self.explainer is None:
            return {"features": ALL_ML_FEATURES, "importance": [1.0/len(ALL_ML_FEATURES)] * len(ALL_ML_FEATURES), "direction": {}, "feature_names": {}}

        cell_ids = list(self.cells.keys())[:200]
        X_all = np.vstack([self._get_ml_features(cid) for cid in cell_ids])

        shap_values = self.explainer.shap_values(X_all)

        if isinstance(shap_values, np.ndarray) and len(shap_values.shape) == 2:
            avg_shap = np.abs(shap_values).mean(axis=0)
        elif isinstance(shap_values, list):
            avg_shap = np.mean([np.abs(sv).mean(axis=0) for sv in shap_values], axis=0)
        else:
            avg_shap = np.abs(shap_values).mean(axis=0).flatten()[:len(ALL_ML_FEATURES)]

        total = avg_shap.sum()
        importance = avg_shap / total if total > 0 else avg_shap

        features_sorted = sorted(zip(ALL_ML_FEATURES, importance), key=lambda x: -x[1])

        result_features = []
        result_importance = []
        result_direction = {}
        for feat, imp in features_sorted:
            result_features.append(feat)
            result_importance.append(round(float(imp), 4))
            result_direction[feat] = "increases temperature" if feat in HEAT_INCREASERS else "decreases temperature"

        return {
            "features": result_features,
            "importance": result_importance,
            "direction": result_direction,
            "feature_names": {f: FEATURE_NAMES.get(f, f) for f in result_features},
        }


analyzer = DriverAnalyzer()
