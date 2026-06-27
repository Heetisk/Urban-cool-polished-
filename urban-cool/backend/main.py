"""
UrbanCool AI - FastAPI Backend (Multi-City)

Endpoints:
  GET  /cities              - List available cities
  GET  /cells               - All cells for a city
  GET  /cells/{id}          - Full cell details
  GET  /cells/{id}/drivers  - SHAP driver analysis
  GET  /hotspots            - Hottest cells
  POST /simulate            - Run cooling simulation (spatial)
  GET  /dashboard           - Aggregated stats
  GET  /drivers/global      - Global feature importance
  GET  /priority            - Priority rankings
  GET  /priority/top        - Top priority zones
  GET  /data-info           - Data source timeline
  GET  /validation          - Model validation metrics
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# Path setup: backend/ imports from itself (data_loader, models, etc.)
# and from project root (config.config_loader, ranking.*, etc.)
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


_MAX_CACHE_SIZE = 10

from data_loader import data_loader
from models import SimulateRequest, OptimizeRequest, ScenarioCompareRequest
from simulation import simulate_intervention, build_spatial_index
from optimization import greedy_optimize, compare_scenarios
from driver_analyzer import analyzer
from ranking.priority_score import compute_priority_scores, get_score_distribution
from ranking.recommendation_engine import enrich_rankings
from config.config_loader import get_available_cities, get_city_config, list_cities_with_data


# CORS origins from environment variable, with fallback defaults
_cors_env = os.environ.get("CORS_ORIGINS", "")
ALLOWED_ORIGINS = (
    [origin.strip() for origin in _cors_env.split(",") if origin.strip()]
    if _cors_env
    else [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]
)

# Valid city keys (loaded once at startup for path traversal validation)
_VALID_CITY_KEYS = None


def _get_valid_city_keys():
    global _VALID_CITY_KEYS
    if _VALID_CITY_KEYS is None:
        _VALID_CITY_KEYS = set(get_available_cities())
    return _VALID_CITY_KEYS


def _validate_city_key(city: str) -> str:
    """Validate city key to prevent path traversal attacks."""
    import re
    if not re.match(r'^[a-zA-Z0-9_]+$', city):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid city key: '{city}'. City keys must contain only alphanumeric characters and underscores.",
        )
    valid_keys = _get_valid_city_keys()
    if city not in valid_keys:
        raise HTTPException(
            status_code=404,
            detail=f"City '{city}' not found. Available cities: {list(valid_keys)}",
        )
    return city

# Cache spatial indices per city (built once, reused across requests)
_spatial_indices = {}

# LST-to-air-temp conversion constants (calibrated from feature_engineering.py)
_LST_MEAN = 46.27
_ERA5_MEAN = 33.04


def convert_lst_to_air_temp(predicted_lst: float, cell_props: dict) -> float:
    """Convert predicted LST to estimated 2m air temperature.

    Uses ERA5 as absolute anchor + LST deviation for spatial variation:
      Ta = ERA5_mean + (LST - LST_mean) * scale
      scale depends on NDVI and urban fraction:
        - Vegetated areas: scale ~0.40 (air follows surface)
        - Impervious surfaces: scale ~0.24 (air less responsive)
    """
    ndvi = cell_props.get("ndvi") or 0.3
    building_density = cell_props.get("building_density_per_km2", 0)
    urban_frac = min(1.0, building_density / 2000.0)

    ndvi_factor = 0.12 * ndvi
    urban_factor = -0.08 * urban_frac
    scale = 0.28 + ndvi_factor + urban_factor
    scale = max(0.20, min(0.45, scale))

    lst_dev = predicted_lst - _LST_MEAN
    ta_est = _ERA5_MEAN + lst_dev * scale

    era5_ref = cell_props.get("lst_era5_celsius") or _ERA5_MEAN
    ta_min = max(28.0, era5_ref - 3.0)
    ta_max = min(45.0, era5_ref + 10.0)
    ta_est = max(ta_min, min(ta_max, ta_est))

    return round(ta_est, 2)
_MAX_CACHE_SIZE = 10


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load city data on startup. Other cities are lazy-loaded on first request."""
    cities = list_cities_with_data()
    if cities:
        data_loader.load(cities[0])
        analyzer.load(cities[0])
    print(f"Available cities: {get_available_cities()}")
    print(f"Cities with data: {cities}")
    yield
    # Cleanup on shutdown
    _spatial_indices.clear()
    print("Server shut down cleanly.")


app = FastAPI(
    title="UrbanCool AI API",
    description="Urban heat mitigation and cooling strategies via AI/ML",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_CITY = "ahmedabad"


def _ensure_city_data(city: str):
    """Ensure city data is loaded, raise 404 if not available."""
    city = _validate_city_key(city)
    cities_with_data = list_cities_with_data()
    if city not in cities_with_data:
        raise HTTPException(
            status_code=404,
            detail=f"City '{city}' not found or data not available. Available cities: {get_available_cities()}",
        )
    try:
        data_loader.ensure_loaded(city)
        analyzer.ensure_loaded(city)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Data files for city '{city}' are missing.",
        )


@app.get("/cities")
def get_cities():
    """List all available cities and which ones have data."""
    all_cities = get_available_cities()
    cities_with_data = list_cities_with_data()
    result = []
    for city_key in all_cities:
        config = get_city_config(city_key)
        result.append({
            "key": city_key,
            "name": config["name"],
            "state": config.get("state", ""),
            "center": config["center"],
            "zoom": config["zoom"],
            "has_data": city_key in cities_with_data,
        })
    return result


@app.get("/cells")
def get_cells(city: str = Query(DEFAULT_CITY, description="City key")):
    """Get all cells with basic info + geometry for map rendering."""
    _ensure_city_data(city)
    features = data_loader.get_all_cells(city)
    result = []
    for feature in features:
        props = feature["properties"]
        cell_id = props["cell_id"]
        pred = analyzer.predict_temperature(cell_id, city)
        predicted_air = convert_lst_to_air_temp(pred["predicted_temp"], props)
        result.append({
            "type": "Feature",
            "geometry": feature["geometry"],
            "properties": {
                "cell_id": cell_id,
                "temp": props.get("temperature"),
                "air_temperature_celsius": props.get("air_temperature_celsius"),
                "predicted_temp": pred["predicted_temp"],
                "predicted_air_temp": predicted_air,
                "lat": props.get("centroid_lat"),
                "lon": props.get("centroid_lon"),
                "temperature_source": props.get("temperature_source"),
            },
        })
    return result


@app.get("/cells/{cell_id}")
def get_cell(cell_id: str, city: str = Query(DEFAULT_CITY, description="City key")):
    """Get full details for a single cell."""
    _ensure_city_data(city)
    cell = data_loader.get_cell(cell_id, city)
    if cell is None:
        raise HTTPException(status_code=404, detail=f"Cell {cell_id} not found in {city}")

    props = cell["properties"]
    actual_cell_id = props["cell_id"]
    pred = analyzer.predict_temperature(actual_cell_id, city)

    predicted_air = convert_lst_to_air_temp(pred["predicted_temp"], props)
    actual_air = props.get("air_temperature_celsius") or 0
    prediction_error_air = round(abs(predicted_air - actual_air), 2) if actual_air else None

    return {
        "cell_id": props["cell_id"],
        "temp": props.get("temperature"),
        "air_temperature_celsius": props.get("air_temperature_celsius"),
        "predicted_temp": pred["predicted_temp"],
        "predicted_air_temp": predicted_air,
        "prediction_error": pred["error"],
        "prediction_error_air": prediction_error_air,
        "ndvi": props.get("ndvi"),
        "builtup_density": props.get("builtup_density"),
        "road_density_km_km2": props.get("road_density_km_km2"),
        "distance_water_m": props.get("distance_water_m"),
        "humidity_pct": props.get("humidity_pct"),
        "wind_speed_ms": props.get("wind_speed_ms"),
        "solar_wm2": props.get("solar_wm2"),
        "building_count": props.get("building_count"),
        "building_density_per_km2": props.get("building_density_per_km2"),
        # Satellite data
        "lst_satellite_celsius": props.get("lst_satellite_celsius"),
        "lst_landsat8_celsius": props.get("lst_landsat8_celsius"),
        "lst_ecostress_celsius": props.get("lst_ecostress_celsius"),
        "ndvi_satellite": props.get("ndvi_satellite"),
        "ndvi_sentinel2": props.get("ndvi_sentinel2"),
        "temperature_source": props.get("temperature_source"),
        "ndvi_source": props.get("ndvi_source"),
        # CPCB air quality
        "aqi": props.get("aqi"),
        "pm25": props.get("pm25"),
        "pm10": props.get("pm10"),
        "cpcb_station": props.get("cpcb_station"),
        # Heat stress
        "wet_bulb_celsius": props.get("wet_bulb_celsius"),
        "data_quality": props.get("data_quality"),
        # Physics-informed features
        "albedo": props.get("albedo"),
        "emissivity": props.get("emissivity"),
        "sky_view_factor": props.get("sky_view_factor"),
        "uhi_intensity": props.get("uhi_intensity"),
        "heat_stress_score": props.get("heat_stress_score"),
        "net_radiation": props.get("net_radiation"),
        "sensible_heat_flux": props.get("sensible_heat_flux"),
        "latent_heat_flux": props.get("latent_heat_flux"),
        "ground_heat_flux": props.get("ground_heat_flux"),
        "bowen_ratio": props.get("bowen_ratio"),
    }


@app.get("/hotspots")
def get_hotspots(
    city: str = Query(DEFAULT_CITY, description="City key"),
    min_temp: Optional[float] = Query(None, description="Minimum temperature threshold"),
    limit: Optional[int] = Query(20, description="Max number of results"),
):
    """Get hottest cells, optionally filtered by minimum temperature."""
    _ensure_city_data(city)
    hotspots = data_loader.get_hotspots(city, limit=limit)

    if min_temp is not None:
        hotspots = [h for h in hotspots if h["temp"] >= min_temp]

    return hotspots


@app.post("/simulate")
def run_simulation(
    request: SimulateRequest,
    city: str = Query(DEFAULT_CITY, description="City key"),
):
    """Run cooling intervention simulation with spatial neighbor effects."""
    _ensure_city_data(city)
    cell = data_loader.get_cell(request.cell_id, city)
    if cell is None:
        raise HTTPException(status_code=404, detail=f"Cell {request.cell_id} not found")

    # Build or retrieve cached spatial index for this city
    if city not in _spatial_indices:
        # Evict oldest entry if cache is full
        if len(_spatial_indices) >= _MAX_CACHE_SIZE:
            oldest_key = next(iter(_spatial_indices))
            del _spatial_indices[oldest_key]
        all_cells_data = {}
        for feature in data_loader.get_all_cells(city):
            props = feature["properties"]
            all_cells_data[props["cell_id"]] = props
        _spatial_indices[city] = (all_cells_data, build_spatial_index(all_cells_data))

    all_cells_data, spatial_index = _spatial_indices[city]

    result = simulate_intervention(
        cell_data=cell["properties"],
        tree_cover=request.tree_cover,
        cool_roof=request.cool_roof,
        green_roof=request.green_roof,
        water_body=request.water_body,
        all_cells=all_cells_data,
        spatial_index=spatial_index,
    )

    return {
        "cell_id": request.cell_id,
        **result,
    }


@app.get("/dashboard")
def get_dashboard(city: str = Query(DEFAULT_CITY, description="City key")):
    """Get aggregated stats for dashboard cards."""
    _ensure_city_data(city)
    return data_loader.get_dashboard_stats(city)


@app.get("/cells/{cell_id}/drivers")
def get_cell_drivers(
    cell_id: str,
    city: str = Query(DEFAULT_CITY, description="City key"),
):
    """Get SHAP-based driver analysis for a cell."""
    _ensure_city_data(city)
    cell = data_loader.get_cell(cell_id, city)
    if cell is None:
        raise HTTPException(status_code=404, detail=f"Cell {cell_id} not found")
    actual_cell_id = cell["properties"]["cell_id"]
    return analyzer.analyze_drivers(actual_cell_id, city)


@app.get("/drivers/global")
def get_global_drivers(city: str = Query(DEFAULT_CITY, description="City key")):
    """Get global feature importance across all cells."""
    _ensure_city_data(city)
    return analyzer.get_global_drivers(city)


@app.get("/priority")
def get_priority_rankings(
    city: str = Query(DEFAULT_CITY, description="City key"),
    sort_by: str = Query("score", description="Sort by: score or temperature"),
):
    """Get all cells ranked by priority score with recommendations."""
    _ensure_city_data(city)
    rankings = compute_priority_scores(city)
    rankings = enrich_rankings(rankings)
    if sort_by == "temperature":
        rankings.sort(key=lambda x: x.get("air_temperature_celsius") or x.get("temperature", 0), reverse=True)
        for i, r in enumerate(rankings):
            r["rank"] = i + 1
    summary = get_score_distribution(rankings)
    return {"rankings": rankings, "summary": summary}


@app.get("/priority/top")
def get_top_priority(
    city: str = Query(DEFAULT_CITY, description="City key"),
    n: int = Query(10, description="Number of top priority zones to return"),
):
    """Get top N priority locations with recommendations."""
    _ensure_city_data(city)
    rankings = compute_priority_scores(city)
    rankings = enrich_rankings(rankings)
    summary = get_score_distribution(rankings)
    return {"rankings": rankings[:n], "summary": summary}


@app.get("/data-info")
def get_data_info(city: str = Query(DEFAULT_CITY, description="City key")):
    """Get data source timeline and freshness info."""
    city = _validate_city_key(city)
    _ensure_city_data(city)
    # Use config_loader for safe path resolution
    from config.config_loader import get_city_processed_dir
    meta_path = os.path.join(get_city_processed_dir(city), "data_metadata.json")
    if not os.path.exists(meta_path):
        return {"city": city, "sources": [], "generated_at": None}
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/validation")
def get_validation(city: str = Query(DEFAULT_CITY, description="City key")):
    """Get model validation metrics from spatial cross-validation."""
    city = _validate_city_key(city)
    _ensure_city_data(city)
    # Use config_loader for safe path resolution
    from config.config_loader import get_city_models_dir
    report_path = os.path.join(get_city_models_dir(city), "validation_report.json")
    if not os.path.exists(report_path):
        return {"city": city, "available": False, "message": "No validation report found. Run train_temperature_model.py first."}
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    report["available"] = True
    return report


@app.post("/optimize")
def run_optimization(
    request: OptimizeRequest,
    city: str = Query(DEFAULT_CITY, description="City key"),
):
    """Run greedy budget-constrained optimization for city-wide intervention placement."""
    _ensure_city_data(city)
    features = data_loader.get_all_cells(city)
    all_cells = {}
    for feature in features:
        props = feature["properties"]
        all_cells[props["cell_id"]] = props

    result = greedy_optimize(
        all_cells=all_cells,
        budget=request.budget,
        intervention_types=request.intervention_types,
        intensity=request.intensity,
        max_per_cell=request.max_per_cell,
    )
    return result


@app.post("/scenarios/compare")
def compare_two_scenarios(
    request: ScenarioCompareRequest,
    city: str = Query(DEFAULT_CITY, description="City key"),
):
    """Compare two optimization scenarios side by side."""
    _ensure_city_data(city)
    return compare_scenarios(request.scenario_a, request.scenario_b)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
