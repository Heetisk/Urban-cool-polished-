"""
Fetch Roads and Buildings from OpenStreetMap (Optimized).

Source: OpenStreetMap via osmnx library

Strategy: Downloads city-wide OSM data ONCE, then computes per-cell metrics
using spatial intersections. Much faster than per-cell queries.

Provides:
- Road density (km of road per km² of grid cell)
- Building count and density
"""

import json
import math
import argparse
import osmnx as ox
import geopandas as gpd
import pandas as pd
from shapely.geometry import box, mapping
from typing import List, Dict
import warnings
warnings.filterwarnings("ignore")


def fetch_city_osm(center_lat: float, center_lon: float, radius_m: int = 15000):
    """
    Download city-wide road network and buildings in one request.

    Args:
        center_lat, center_lon: city center
        radius_m: download radius in meters (~covers most of Ahmedabad)

    Returns:
        (roads_gdf, buildings_gdf)
    """
    print(f"  Downloading road network ({radius_m}m radius)...")
    G = ox.graph_from_point(
        (center_lat, center_lon),
        dist=radius_m,
        network_type="drive",
    )
    roads = ox.graph_to_gdfs(G, nodes=False)
    roads = roads.copy()
    # Project to metric CRS (UTM zone 43N for Ahmedabad/India) for accurate length
    roads_projected = roads.to_crs(epsg=32643)
    roads["length_km"] = roads_projected.length / 1000
    print(f"  Got {len(roads)} road segments")

    print(f"  Downloading buildings...")
    tags = {"building": True}
    buildings = ox.features_from_point(
        (center_lat, center_lon),
        tags=tags,
        dist=radius_m,
    )
    print(f"  Got {len(buildings)} buildings")

    return roads, buildings


def compute_cell_metrics(
    cell_polygon,
    roads: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
) -> Dict:
    """
    Compute road and building density for a single cell using spatial intersection.

    Args:
        cell_polygon: shapely polygon of the grid cell (EPSG:4326)
        roads: city-wide roads GeoDataFrame (with length_km column)
        buildings: city-wide buildings GeoDataFrame

    Returns:
        {"road_density": float, "building_count": int, "building_density_per_km2": float}
    """
    # Clip roads to cell using pre-computed length_km
    cell_roads = gpd.clip(roads, cell_polygon)
    road_length_km = cell_roads["length_km"].sum() if len(cell_roads) > 0 else 0.0

    # Clip buildings to cell
    cell_buildings = gpd.clip(buildings, cell_polygon)
    building_count = len(cell_buildings)

    # Cell area in km² using projected CRS (UTM 43N)
    from pyproj import Transformer
    from shapely.ops import transform as shapely_transform
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
    cell_projected = shapely_transform(transformer.transform, cell_polygon)
    area_km2 = cell_projected.area / 1e6

    road_density = round(road_length_km / area_km2, 4) if area_km2 > 0 else 0.0
    building_density = round(building_count / area_km2, 2) if area_km2 > 0 else 0.0

    return {
        "road_density": road_density,
        "building_count": building_count,
        "building_density_per_km2": building_density,
    }


def fetch_osm_for_grid(
    grid_path: str,
    output_path: str,
    city: str,
    center_lat: float = None,
    center_lon: float = None,
    radius_m: int = 15000,
) -> List[Dict]:
    """
    Fetch OSM data efficiently for all grid cells.

    Downloads city-wide data once, then computes per-cell metrics.
    """
    with open(grid_path) as f:
        grid = json.load(f)

    features = grid["features"]

    # Auto-detect center from grid
    if center_lat is None or center_lon is None:
        lats = [f["properties"]["centroid_lat"] for f in features]
        lons = [f["properties"]["centroid_lon"] for f in features]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

    print(f"Fetching OSM data for {city}...")
    print(f"  Center: {center_lat}, {center_lon}")
    print(f"  Radius: {radius_m}m")

    roads, buildings = fetch_city_osm(center_lat, center_lon, radius_m)

    # Build cell polygons and compute metrics
    print(f"\nComputing per-cell metrics for {len(features)} cells...")
    results = []

    for i, feature in enumerate(features):
        props = feature["properties"]
        cell_id = props["cell_id"]
        coords = feature["geometry"]["coordinates"][0]

        # Create polygon from GeoJSON coordinates
        from shapely.geometry import Polygon
        polygon = Polygon(coords)

        metrics = compute_cell_metrics(polygon, roads, buildings)
        metrics["cell_id"] = cell_id
        results.append(metrics)

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(features)} cells...")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults: {len(results)} cells")
    print(f"Saved to {output_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch OSM roads/buildings (optimized)")
    parser.add_argument("--grid", default="data/processed/grid.json")
    parser.add_argument("--output", default="data/processed/osm_roads_buildings.json")
    parser.add_argument("--city", default="ahmedabad")
    parser.add_argument("--center-lat", type=float, default=None)
    parser.add_argument("--center-lon", type=float, default=None)
    parser.add_argument("--radius", type=int, default=15000, help="Download radius in meters")
    args = parser.parse_args()

    fetch_osm_for_grid(
        args.grid, args.output, args.city,
        args.center_lat, args.center_lon, args.radius,
    )
