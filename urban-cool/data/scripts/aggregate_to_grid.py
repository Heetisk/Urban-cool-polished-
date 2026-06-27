"""
Grid Aggregation Module.

Takes raw data layers and aggregates them into master grid cells.
Each source produces an intermediate GeoJSON with cell-level statistics.

Resolution handling:
- Raster data (Landsat 30m, Sentinel 10m, ERA5 9km) → aggregate to 500m grid
- Vector data (OSM) → spatial intersection + density calculation
"""

import json
import math
import os
import argparse
import numpy as np
from typing import List, Dict, Optional
from shapely.geometry import Polygon, shape, mapping
from shapely.ops import transform as shapely_transform
from pyproj import Transformer

# CRS transformers
_transformer_to_utm = None
_utm_zone = None


def get_utm_transformer(lat: float, lon: float):
    """Get appropriate UTM transformer for the location."""
    global _transformer_to_utm, _utm_zone
    zone = int((lon + 180) / 6) + 1
    if zone != _utm_zone:
        _utm_zone = zone
        _transformer_to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:326{zone:02d}", always_xy=True)
    return _transformer_to_utm


def cell_area_km2(lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> float:
    """Compute cell area in km² using projected CRS."""
    poly = Polygon([
        (lon_min, lat_min), (lon_max, lat_min),
        (lon_max, lat_max), (lon_min, lat_max),
        (lon_min, lat_min),
    ])
    mid_lat = (lat_min + lat_max) / 2
    mid_lon = (lon_min + lon_max) / 2
    transformer = get_utm_transformer(mid_lat, mid_lon)
    projected = shapely_transform(transformer.transform, poly)
    return projected.area / 1e6


def load_master_grid(grid_path: str) -> List[Dict]:
    """Load master grid and return list of cell records."""
    with open(grid_path) as f:
        grid = json.load(f)

    cells = []
    for feature in grid["features"]:
        props = feature["properties"]
        cells.append({
            "cell_id": props["cell_id"],
            "centroid_lat": props["centroid_lat"],
            "centroid_lon": props["centroid_lon"],
            "lat_min": props["lat_min"],
            "lat_max": props["lat_max"],
            "lon_min": props["lon_min"],
            "lon_max": props["lon_max"],
            "geometry": shape(feature["geometry"]),
        })
    return cells


def aggregate_era5_to_grid(nc_path: str, cells: List[Dict]) -> List[Dict]:
    """
    Aggregate ERA5 data to grid cells.

    ERA5 is ~9km resolution, so multiple cells share the same value.
    Uses nearest-neighbor sampling.
    """
    import xarray as xr

    ds = xr.open_dataset(nc_path)
    results = []

    for cell in cells:
        try:
            sample = ds.sel(latitude=cell["centroid_lat"], longitude=cell["centroid_lon"], method="nearest")

            # Temperature: K → °C
            temp_k = float(sample["t2m"].mean().values)
            temp_c = round(temp_k - 273.15, 2)

            # Dewpoint → Humidity (Magnus formula)
            dew_k = float(sample["d2m"].mean().values)
            dew_c = dew_k - 273.15
            a, b = 17.27, 237.7
            alpha_t = (a * temp_c) / (b + temp_c)
            alpha_d = (a * dew_c) / (b + dew_c)
            humidity = round(float(100 * np.exp(alpha_d - alpha_t)), 2)
            humidity = max(0, min(100, humidity))

            # Wind speed
            u = float(sample["u10"].mean().values)
            v = float(sample["v10"].mean().values)
            wind = round(float(np.sqrt(u**2 + v**2)), 2)

            # Solar radiation (cumulative → per-hour)
            solar_j = sample["ssrd"].values
            solar_diff = np.diff(solar_j, prepend=solar_j[0])
            solar_diff = np.where(solar_diff > 0, solar_diff, 0)
            solar_w = round(float(np.mean(solar_diff)) / 10800, 2)

            results.append({
                "cell_id": cell["cell_id"],
                "lst_era5_celsius": temp_c,
                "humidity_pct": humidity,
                "wind_speed_ms": wind,
                "solar_wm2": solar_w,
            })

        except Exception as e:
            results.append({
                "cell_id": cell["cell_id"],
                "lst_era5_celsius": None,
                "humidity_pct": None,
                "wind_speed_ms": None,
                "solar_wm2": None,
            })

    ds.close()
    return results


def aggregate_osm_to_grid(roads_path: str, buildings_path: str, cells: List[Dict]) -> List[Dict]:
    """
    Aggregate OSM vector data to grid cells.

    Computes per-cell:
    - road_density: km of road per km²
    - building_count: number of buildings
    - building_density: buildings per km²
    """
    import geopandas as gpd

    roads = gpd.read_file(roads_path)
    buildings = gpd.read_file(buildings_path)

    results = []
    for cell in cells:
        poly = cell["geometry"]

        # Clip roads
        cell_roads = gpd.clip(roads, poly)
        road_length_km = cell_roads["length_m"].sum() / 1000 if len(cell_roads) > 0 else 0.0

        # Clip buildings
        cell_buildings = gpd.clip(buildings, poly)
        building_count = len(cell_buildings)

        # Area
        area = cell_area_km2(cell["lat_min"], cell["lat_max"], cell["lon_min"], cell["lon_max"])

        results.append({
            "cell_id": cell["cell_id"],
            "road_length_km": round(road_length_km, 4),
            "road_density_km_km2": round(road_length_km / area, 4) if area > 0 else 0.0,
            "building_count": building_count,
            "building_density_per_km2": round(building_count / area, 2) if area > 0 else 0.0,
        })

    return results


def save_intermediate(data: List[Dict], name: str, output_dir: str) -> str:
    """Save intermediate aggregation results."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}_grid.geojson")

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {k: v for k, v in item.items() if k != "geometry"},
                "geometry": None,
            }
            for item in data
        ],
    }

    with open(path, "w") as f:
        json.dump(geojson, f, indent=2)

    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grid Aggregation Module")
    parser.add_argument("--grid", default="data/processed/master_grid.geojson")
    parser.add_argument("--era5-nc", default="data/raw/era5/era5_ahmedabad_2024.nc")
    parser.add_argument("--osm-roads", default="data/raw/osm/osm_ahmedabad_roads.geojson")
    parser.add_argument("--osm-buildings", default="data/raw/osm/osm_ahmedabad_buildings.geojson")
    parser.add_argument("--output-dir", default="data/intermediate")
    args = parser.parse_args()

    print("=== Grid Aggregation ===")

    cells = load_master_grid(args.grid)
    print(f"Loaded {len(cells)} grid cells")

    # ERA5
    if os.path.exists(args.era5_nc):
        print("\nAggregating ERA5...")
        era5_data = aggregate_era5_to_grid(args.era5_nc, cells)
        path = save_intermediate(era5_data, "era5", args.output_dir)
        valid = sum(1 for d in era5_data if d["lst_era5_celsius"] is not None)
        print(f"  {valid}/{len(cells)} cells with ERA5 data -> {path}")

    # OSM
    if os.path.exists(args.osm_roads):
        print("\nAggregating OSM...")
        osm_data = aggregate_osm_to_grid(args.osm_roads, args.osm_buildings, cells)
        path = save_intermediate(osm_data, "osm", args.output_dir)
        print(f"  {len(cells)} cells aggregated -> {path}")

    print("\nDone!")
