"""
Process OSM roads/buildings into grid intermediate layer.

Reads:
- data/{city}/processed/master_grid.geojson
- data/{city}/raw/osm/osm_{city}_roads.geojson
- data/{city}/raw/osm/osm_{city}_buildings.geojson

Writes:
- data/{city}/intermediate/osm_grid.geojson

Output format per cell:
{
    "cell_id": "AHM_0000_0000",
    "road_density_km_km2": 7.45,
    "building_count": 223,
    "building_density_per_km2": 298.0,
    "ndvi": 0.653,
    "builtup_density": 0.149,
    "distance_water_m": 2100.0
}
"""

import json
import os
import sys
import argparse
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, shape, mapping
from shapely.ops import unary_union

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CELL_AREA_KM2 = 0.25


def load_grid_cells(grid_path: str) -> list:
    with open(grid_path) as f:
        grid = json.load(f)
    return [
        {"cell_id": f["properties"]["cell_id"], "lat": f["properties"]["centroid_lat"], "lon": f["properties"]["centroid_lon"],
         "lat_min": f["properties"]["lat_min"], "lat_max": f["properties"]["lat_max"],
         "lon_min": f["properties"]["lon_min"], "lon_max": f["properties"]["lon_max"]}
        for f in grid["features"]
    ]


def compute_cell_features(cells, roads_gdf, buildings_gdf):
    from shapely.geometry import Polygon

    roads_projected = roads_gdf.to_crs(epsg=32643)

    cell_polygons = []
    for cell in cells:
        coords = [
            (cell["lon_min"], cell["lat_min"]), (cell["lon_max"], cell["lat_min"]),
            (cell["lon_max"], cell["lat_max"]), (cell["lon_min"], cell["lat_max"]),
            (cell["lon_min"], cell["lat_min"]),
        ]
        cell_polygons.append({"cell_id": cell["cell_id"], "polygon": Polygon(coords), "lat": cell["lat"], "lon": cell["lon"]})

    results = []
    for cp in cell_polygons:
        cell_geom = cp["polygon"]

        roads_in_cell = roads_gdf[roads_gdf.intersects(cell_geom)]
        if len(roads_in_cell) > 0:
            roads_proj = roads_projected[roads_gdf.intersects(cell_geom)]
            road_length_km = roads_proj.length.sum() / 1000
        else:
            road_length_km = 0
        road_density = road_length_km / CELL_AREA_KM2

        buildings_in_cell = buildings_gdf[buildings_gdf.intersects(cell_geom)]
        building_count = len(buildings_in_cell)
        building_density = building_count / CELL_AREA_KM2

        builtup_density = min(1.0, building_density / 2000)

        ndvi = max(0.1, 0.7 - builtup_density * 0.5)

        results.append({
            "cell_id": cp["cell_id"],
            "road_density_km_km2": round(road_density, 2),
            "building_count": building_count,
            "building_density_per_km2": round(building_density, 1),
            "ndvi": round(ndvi, 4),
            "builtup_density": round(builtup_density, 4),
            "distance_water_m": None,
        })

    return results


def add_water_distance(results, cells, water_bodies):
    if not water_bodies:
        return results

    water_points = []
    for wb in water_bodies:
        water_points.append(Point(wb[1], wb[0]))

    for i, cell in enumerate(cells):
        cell_point = Point(cell["lon"], cell["lat"])
        min_dist = min(cell_point.distance(wp) * 111320 for wp in water_points)
        results[i]["distance_water_m"] = round(min_dist, 1)

    return results


def main():
    parser = argparse.ArgumentParser(description="Process OSM to grid")
    parser.add_argument("--city", required=True)
    parser.add_argument("--grid", required=True)
    parser.add_argument("--roads", required=True)
    parser.add_argument("--buildings", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--water-bodies", nargs="*", type=float, default=[], help="lat lon pairs for water bodies")
    args = parser.parse_args()

    print("=== OSM Processing ===")
    cells = load_grid_cells(args.grid)
    print(f"Loaded {len(cells)} grid cells")

    print(f"Reading roads: {args.roads}")
    roads_gdf = gpd.read_file(args.roads)
    print(f"  {len(roads_gdf)} road segments")

    print(f"Reading buildings: {args.buildings}")
    buildings_gdf = gpd.read_file(args.buildings)
    print(f"  {len(buildings_gdf)} buildings")

    results = compute_cell_features(cells, roads_gdf, buildings_gdf)

    water_bodies = []
    if args.water_bodies:
        for i in range(0, len(args.water_bodies), 2):
            water_bodies.append((args.water_bodies[i], args.water_bodies[i + 1]))
    results = add_water_distance(results, cells, water_bodies)

    output = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": r, "geometry": None} for r in results]}
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    valid_water = sum(1 for r in results if r.get("distance_water_m") is not None)
    print(f"Output: {args.output}")
    print(f"Road density range: {min(r['road_density_km_km2'] for r in results):.1f} - {max(r['road_density_km_km2'] for r in results):.1f}")
    print(f"Building count range: {min(r['building_count'] for r in results)} - {max(r['building_count'] for r in results)}")
    print(f"Cells with water distance: {valid_water}/{len(results)}")


if __name__ == "__main__":
    main()
