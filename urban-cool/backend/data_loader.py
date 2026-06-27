"""
Data Loader - Multi-city data management.

Loads heat_grid.geojson for any configured city.
Provides fast lookup by cell_id for all API endpoints.
"""

import json
import os
import sys
import threading
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config_loader import get_heat_grid_path, get_city_config, get_available_cities


class DataLoader:
    def __init__(self):
        self.cells: Dict[str, dict] = {}
        self.features: List[dict] = []
        self.city: Optional[str] = None
        self._loaded = False
        self._lock = threading.RLock()

    def _load_impl(self, city: str = "ahmedabad"):
        """Load GeoJSON for a specific city (must be called with lock held)."""
        geojson_path = get_heat_grid_path(city)
        if not os.path.exists(geojson_path):
            raise FileNotFoundError(f"No data found for city '{city}' at {geojson_path}")

        with open(geojson_path, encoding="utf-8") as f:
            data = json.load(f)

        self.features = data["features"]
        self.cells = {}
        self.city = city

        for feature in self.features:
            props = feature["properties"]
            cell_id = props["cell_id"]
            self.cells[cell_id] = {
                "geometry": feature["geometry"],
                "properties": props,
            }

        self._loaded = True
        print(f"Loaded {len(self.cells)} cells for city '{city}' from {geojson_path}")

    def load(self, city: str = "ahmedabad"):
        """Load GeoJSON for a specific city (thread-safe)."""
        with self._lock:
            self._load_impl(city)

    def _ensure_loaded(self, city: str = None):
        """Ensure data is loaded for the requested city (thread-safe)."""
        target_city = city or self.city or "ahmedabad"
        # Double-checked locking pattern for thread safety
        if self._loaded and self.city == target_city:
            return
        with self._lock:
            # Re-check after acquiring lock (another thread may have loaded)
            if self._loaded and self.city == target_city:
                return
            self._load_impl(target_city)

    def ensure_loaded(self, city: str = None):
        """Public wrapper for _ensure_loaded."""
        self._ensure_loaded(city)

    def get_all_cells(self, city: str = None) -> List[dict]:
        """Get all cells as GeoJSON features."""
        self._ensure_loaded(city)
        return self.features

    def get_cell(self, cell_id: str, city: str = None) -> Optional[dict]:
        """Get single cell by ID."""
        self._ensure_loaded(city)
        return self.cells.get(cell_id)

    def get_hotspots(self, city: str = None, limit: int = None) -> List[dict]:
        """Get cells sorted by temperature (highest first)."""
        self._ensure_loaded(city)

        cells_with_temp = []
        for feature in self.features:
            props = feature["properties"]
            temp = props.get("temperature")
            if temp is not None:
                cells_with_temp.append({
                    "cell_id": props["cell_id"],
                    "temp": temp,
                    "air_temperature_celsius": props.get("air_temperature_celsius"),
                    "lat": props.get("centroid_lat"),
                    "lon": props.get("centroid_lon"),
                    "ndvi": props.get("ndvi"),
                    "builtup_density": props.get("builtup_density"),
                })

        cells_with_temp.sort(key=lambda x: x["air_temperature_celsius"] or x["temp"], reverse=True)

        if limit:
            cells_with_temp = cells_with_temp[:limit]

        return cells_with_temp

    def get_dashboard_stats(self, city: str = None) -> dict:
        """Get aggregated stats for dashboard."""
        self._ensure_loaded(city)

        temps = []
        risks = {"low": 0, "moderate": 0, "high": 0, "severe": 0}
        temp_sources = {}
        ndvi_sources = {}
        physics_vals = {
            "albedo": [], "emissivity": [], "sky_view_factor": [],
            "net_radiation": [], "sensible_heat_flux": [], "latent_heat_flux": [],
            "ground_heat_flux": [], "bowen_ratio": [],
        }

        for feature in self.features:
            props = feature["properties"]
            temp = props.get("air_temperature_celsius") or props.get("temperature")
            risk = props.get("heat_risk_category")

            if temp is not None:
                temps.append(temp)
            if risk and risk in risks:
                risks[risk] += 1

            ts = props.get("temperature_source", "unknown")
            temp_sources[ts] = temp_sources.get(ts, 0) + 1
            ns = props.get("ndvi_source", "unknown")
            ndvi_sources[ns] = ndvi_sources.get(ns, 0) + 1

            for key in physics_vals:
                val = props.get(key)
                if val is not None:
                    physics_vals[key].append(val)

        physics_averages = {}
        for key, vals in physics_vals.items():
            physics_averages[key] = round(sum(vals) / len(vals), 4) if vals else 0

        radar_metrics = ["albedo", "emissivity", "sky_view_factor", "net_radiation", "sensible_heat_flux", "latent_heat_flux"]
        radar_labels = ["Albedo", "Emissivity", "Sky View", "Net Radiation", "Sensible Heat", "Latent Heat"]
        physics_radar = []
        for key, label in zip(radar_metrics, radar_labels):
            vals = physics_vals.get(key, [])
            if not vals:
                continue
            min_v = min(vals)
            max_v = max(vals)
            avg_v = sum(vals) / len(vals)
            if max_v == min_v:
                norm = 50.0
            else:
                norm = round((avg_v - min_v) / (max_v - min_v) * 100, 1)
            physics_radar.append({
                "subject": label,
                "A": norm,
                "fullMark": 100,
            })

        return {
            "total_cells": len(self.features),
            "avg_temp": round(sum(temps) / len(temps), 2) if temps else 0,
            "max_temp": round(max(temps), 2) if temps else 0,
            "min_temp": round(min(temps), 2) if temps else 0,
            "high_risk_cells": risks["high"] + risks["severe"],
            "moderate_risk_cells": risks["moderate"],
            "low_risk_cells": risks["low"],
            "temperature_sources": temp_sources,
            "ndvi_sources": ndvi_sources,
            "physics_averages": physics_averages,
            "physics_radar": physics_radar,
        }


# Singleton
data_loader = DataLoader()
