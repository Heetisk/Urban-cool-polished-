"""
Fetch Roads and Buildings from OpenStreetMap.

Output: data/raw/osm/osm_{city}_roads.geojson
        data/raw/osm/osm_{city}_buildings.geojson
        data/raw/osm/osm_{city}_meta.json
"""

import json
import math
import os
import argparse
import osmnx as ox
import geopandas as gpd
from typing import Dict, List
import warnings
warnings.filterwarnings("ignore")


def download_city_osm(center_lat: float, center_lon: float, radius_m: int = 15000):
    """Download city-wide road network and buildings."""
    print(f"  Downloading road network ({radius_m}m radius)...")
    G = ox.graph_from_point((center_lat, center_lon), dist=radius_m, network_type="drive")
    roads = ox.graph_to_gdfs(G, nodes=False)
    roads = roads.copy()
    roads_projected = roads.to_crs(epsg=32643)
    roads["length_m"] = roads_projected.length
    print(f"  Got {len(roads)} road segments")

    print(f"  Downloading buildings...")
    tags = {"building": True}
    buildings = ox.features_from_point((center_lat, center_lon), tags=tags, dist=radius_m)
    print(f"  Got {len(buildings)} buildings")

    return roads, buildings


def save_raw_osm(roads: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame, city: str, output_dir: str):
    """Save raw OSM data as GeoJSON."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Save roads (keep only needed columns)
    roads_out = roads[["highway", "length_m", "geometry"]].copy()
    roads_out = roads_out.to_crs(epsg=4326)
    roads_path = os.path.join(output_dir, f"osm_{city}_roads.geojson")
    roads_out.to_file(roads_path, driver="GeoJSON")

    # Save buildings
    buildings_out = buildings[["building", "geometry"]].copy()
    buildings_path = os.path.join(output_dir, f"osm_{city}_buildings.geojson")
    buildings_out.to_file(buildings_path, driver="GeoJSON")

    return roads_path, buildings_path


def save_metadata(city: str, roads_count: int, buildings_count: int, center: Dict, radius_m: int, output_dir: str):
    """Save OSM dataset metadata."""
    meta = {
        "source": "OpenStreetMap",
        "extraction_method": "osmnx",
        "city": city,
        "center": center,
        "radius_m": radius_m,
        "road_segments": roads_count,
        "building_count": buildings_count,
        "road_network_type": "drive",
        "crs": "EPSG:4326",
    }

    meta_path = os.path.join(output_dir, f"osm_{city}_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return meta_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch OSM roads/buildings")
    parser.add_argument("--city", default="ahmedabad")
    parser.add_argument("--output-dir", default="data/raw/osm")
    parser.add_argument("--center-lat", type=float, default=23.076)
    parser.add_argument("--center-lon", type=float, default=72.590)
    parser.add_argument("--radius", type=int, default=15000)
    args = parser.parse_args()

    print(f"=== OSM Data Fetcher ===")
    print(f"City: {args.city}")

    roads, buildings = download_city_osm(args.center_lat, args.center_lon, args.radius)
    roads_path, buildings_path = save_raw_osm(roads, buildings, args.city, args.output_dir)
    meta_path = save_metadata(
        args.city, len(roads), len(buildings),
        {"lat": args.center_lat, "lon": args.center_lon},
        args.radius, args.output_dir,
    )

    print(f"Roads: {roads_path}")
    print(f"Buildings: {buildings_path}")
    print(f"Metadata: {meta_path}")
    print("Done!")
