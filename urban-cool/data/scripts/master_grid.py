"""
Master Grid Generator for UrbanCool AI.

Creates a standardized grid that all datasets will be aggregated into.
Each cell has a unique ID: {CITY}_{ROW:04d}_{COL:04d}

Resolution: 500m x 500m (adjustable)
CRS: WGS84 (EPSG:4326)
Cell naming: AHM_0001_0001 (city prefix + row + col)
"""

import json
import math
import argparse
import sys
import os
from typing import List, Dict, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.config_loader import get_available_cities, get_city_config


def meters_to_degrees(meters: float, lat: float) -> Tuple[float, float]:
    """Convert meters to approximate degree offsets."""
    lat_deg = meters / 111_320
    lon_deg = meters / (111_320 * math.cos(math.radians(lat)))
    return lat_deg, lon_deg


def generate_master_grid(
    city: str,
    grid_size_m: int = 500,
    bounds: Dict = None,
) -> Dict:
    """
    Generate a master grid for the city.

    Args:
        city: city name (for prefix and default bounds)
        grid_size_m: cell size in meters
        bounds: optional override {"lat_min", "lat_max", "lon_min", "lon_max"}

    Returns:
        GeoJSON FeatureCollection with grid cells
    """
    try:
        city_config = get_city_config(city)
    except ValueError:
        city_config = {}
    if bounds is None:
        city_bounds = city_config.get("bounds", {})
        bounds = {
            "lat_min": city_bounds.get("lat_min", 23.0),
            "lat_max": city_bounds.get("lat_max", 23.15),
            "lon_min": city_bounds.get("lon_min", 72.5),
            "lon_max": city_bounds.get("lon_max", 72.68),
        }

    prefix = city_config.get("prefix", city[:3].upper())
    mid_lat = (bounds["lat_min"] + bounds["lat_max"]) / 2
    d_lat, d_lon = meters_to_degrees(grid_size_m, mid_lat)

    features = []
    row = 0
    lat = bounds["lat_min"]

    while lat < bounds["lat_max"]:
        col = 0
        lon = bounds["lon_min"]

        while lon < bounds["lon_max"]:
            cell_id = f"{prefix}_{row:04d}_{col:04d}"
            centroid_lat = round(lat + d_lat / 2, 6)
            centroid_lon = round(lon + d_lon / 2, 6)

            # Bounding box coordinates
            coords = [
                [round(lon, 6), round(lat, 6)],
                [round(lon + d_lon, 6), round(lat, 6)],
                [round(lon + d_lon, 6), round(lat + d_lat, 6)],
                [round(lon, 6), round(lat + d_lat, 6)],
                [round(lon, 6), round(lat, 6)],
            ]

            feature = {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "cell_id": cell_id,
                    "city": city,
                    "row": row,
                    "col": col,
                    "centroid_lat": centroid_lat,
                    "centroid_lon": centroid_lon,
                    "lat_min": round(lat, 6),
                    "lat_max": round(lat + d_lat, 6),
                    "lon_min": round(lon, 6),
                    "lon_max": round(lon + d_lon, 6),
                    "grid_size_m": grid_size_m,
                },
            }
            features.append(feature)

            col += 1
            lon += d_lon
        row += 1
        lat += d_lat

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "city": city,
            "prefix": prefix,
            "grid_size_m": grid_size_m,
            "total_cells": len(features),
            "bounds": bounds,
            "rows": row,
            "cols": max(f["properties"]["col"] for f in features) + 1 if features else 0,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate master grid")
    parser.add_argument("--city", default="ahmedabad", choices=get_available_cities())
    parser.add_argument("--grid-size", type=int, default=500, help="Cell size in meters")
    parser.add_argument("--output", default="data/processed/master_grid.geojson")
    args = parser.parse_args()

    grid = generate_master_grid(args.city, args.grid_size)

    with open(args.output, "w") as f:
        json.dump(grid, f, indent=2)

    meta = grid["metadata"]
    print(f"Generated master grid: {args.city}")
    print(f"  Cells: {meta['total_cells']}")
    print(f"  Grid: {meta['rows']} rows x {meta['cols']} cols")
    print(f"  Size: {meta['grid_size_m']}m x {meta['grid_size_m']}m")
    print(f"  Output: {args.output}")
