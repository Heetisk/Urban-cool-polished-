"""
Priority Score Engine - Computes priority scores for urban heat intervention.

Formula:
  priority_score = (heat_normalized x 0.7) + (builtup_normalized x 0.2) + (population_proxy x 0.1)

All factors normalized to 0-1 using min-max scaling.
Supports multiple cities via config.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.data_loader import data_loader


WEIGHTS = {
    "heat": 0.7,
    "builtup": 0.2,
    "population": 0.1,
}


def load_cell_data(city: str = "ahmedabad"):
    """Load all cells from heat_grid.geojson for a city via data_loader."""
    data_loader.ensure_loaded(city)
    return data_loader.features


def min_max_normalize(values):
    """Normalize array to 0-1 using min-max scaling.

    When all values are identical (max == min), returns 0.0 for all.
    This ensures uniform priority when no variation exists.
    """
    arr = np.array(values, dtype=float)
    min_val = np.min(arr)
    max_val = np.max(arr)
    if max_val == min_val:
        # All values identical — no differentiation possible
        return np.zeros_like(arr)
    return (arr - min_val) / (max_val - min_val)


def compute_priority_scores(city: str = "ahmedabad"):
    """Compute priority scores for all cells in a city."""
    features = load_cell_data(city)

    temperatures = []
    builtups = []
    building_densities = []
    cells = []

    for feat in features:
        props = feat["properties"]
        cells.append(props)
        temperatures.append(props.get("temperature", 0))
        builtups.append(props.get("builtup_density", 0))
        building_densities.append(props.get("building_density_per_km2", 0))

    heat_norm = min_max_normalize(temperatures)
    builtup_norm = min_max_normalize(builtups)
    pop_norm = min_max_normalize(building_densities)

    rankings = []
    for i, props in enumerate(cells):
        score = (
            WEIGHTS["heat"] * heat_norm[i]
            + WEIGHTS["builtup"] * builtup_norm[i]
            + WEIGHTS["population"] * pop_norm[i]
        )

        rankings.append({
            "cell_id": props["cell_id"],
            "temperature": round(props.get("temperature", 0), 2),
            "air_temperature_celsius": round(props.get("air_temperature_celsius") or props.get("temperature", 0), 2),
            "builtup_density": round(props.get("builtup_density", 0), 4),
            "building_density_per_km2": round(props.get("building_density_per_km2", 0), 1),
            "ndvi": round(props.get("ndvi", 0), 4),
            "heat_stress_score": round(props.get("heat_stress_score", 0), 2),
            "priority_score": round(float(score), 4),
            "lat": props.get("centroid_lat"),
            "lon": props.get("centroid_lon"),
        })

    rankings.sort(key=lambda x: x["priority_score"], reverse=True)

    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    return rankings


def get_score_distribution(rankings):
    """Get summary of score distribution."""
    critical = sum(1 for r in rankings if r["priority_score"] >= 0.8)
    high = sum(1 for r in rankings if 0.6 <= r["priority_score"] < 0.8)
    moderate = sum(1 for r in rankings if 0.4 <= r["priority_score"] < 0.6)
    low = sum(1 for r in rankings if r["priority_score"] < 0.4)

    return {
        "total_cells": len(rankings),
        "critical_zones": critical,
        "high_priority_zones": high,
        "moderate_zones": moderate,
        "low_priority_zones": low,
    }
