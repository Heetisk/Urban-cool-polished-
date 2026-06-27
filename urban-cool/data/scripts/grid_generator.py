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


def generate_grid(
    lat_min: float, lat_max: float, lon_min: float, lon_max: float, grid_size_m: int = 500
) -> List[Dict]:
    """Generate a square grid of cells covering the bounding box."""
    mid_lat = (lat_min + lat_max) / 2
    d_lat, d_lon = meters_to_degrees(grid_size_m, mid_lat)

    cells = []
    cell_num = 0
    lat = lat_min
    while lat <= lat_max:
        lon = lon_min
        while lon <= lon_max:
            cell_num += 1
            cell_id = f"G{cell_num:03d}"
            centroid_lat = round(lat + d_lat / 2, 6)
            centroid_lon = round(lon + d_lon / 2, 6)

            # Bounding box of the cell
            cells.append(
                {
                    "cell_id": cell_id,
                    "centroid_lat": centroid_lat,
                    "centroid_lon": centroid_lon,
                    "lat_min": round(lat, 6),
                    "lat_max": round(lat + d_lat, 6),
                    "lon_min": round(lon, 6),
                    "lon_max": round(lon + d_lon, 6),
                }
            )
            lon += d_lon
        lat += d_lat

    return cells


def cells_to_geojson(cells: List[Dict]) -> Dict:
    """Convert grid cells to GeoJSON FeatureCollection (polygons)."""
    features = []
    for cell in cells:
        coords = [
            [
                [cell["lon_min"], cell["lat_min"]],
                [cell["lon_max"], cell["lat_min"]],
                [cell["lon_max"], cell["lat_max"]],
                [cell["lon_min"], cell["lat_max"]],
                [cell["lon_min"], cell["lat_min"]],
            ]
        ]
        feature = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": coords},
            "properties": {
                "cell_id": cell["cell_id"],
                "centroid_lat": cell["centroid_lat"],
                "centroid_lon": cell["centroid_lon"],
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate grid cells for urban heat analysis")
    parser.add_argument("--city", default="ahmedabad", choices=get_available_cities(), help="City to generate grid for")
    parser.add_argument("--lat-min", type=float, help="Override: min latitude")
    parser.add_argument("--lat-max", type=float, help="Override: max latitude")
    parser.add_argument("--lon-min", type=float, help="Override: min longitude")
    parser.add_argument("--lon-max", type=float, help="Override: max longitude")
    parser.add_argument("--grid-size", type=int, default=500, help="Grid cell size in meters")
    parser.add_argument("--output", default="data/processed/grid.json", help="Output path")
    args = parser.parse_args()

    if args.lat_min is not None:
        bounds = {
            "lat_min": args.lat_min,
            "lat_max": args.lat_max,
            "lon_min": args.lon_min,
            "lon_max": args.lon_max,
        }
    else:
        config = get_city_config(args.city)
        bounds = config["bounds"]

    cells = generate_grid(
        bounds["lat_min"], bounds["lat_max"],
        bounds["lon_min"], bounds["lon_max"],
        args.grid_size,
    )

    grid_geojson = cells_to_geojson(cells)

    with open(args.output, "w") as f:
        json.dump(grid_geojson, f, indent=2)

    print(f"Generated {len(cells)} grid cells -> {args.output}")
