"""
Download and process ECOSTRESS LST from AppEEARS.

Downloads GeoTIFFs, extracts point values at grid centroids,
computes median LST across dates, outputs GeoJSON FeatureCollection.
"""

import requests
import json
import os
import numpy as np
from pathlib import Path


def download_ecostress_files(task_id, username, password, output_dir):
    """Download all GeoTIFFs from AppEEARS task."""
    r = requests.post(
        "https://appeears.earthdatacloud.nasa.gov/api/login",
        auth=(username, password),
        timeout=30
    )
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get bundle
    r = requests.get(
        f"https://appeears.earthdatacloud.nasa.gov/api/bundle/{task_id}",
        headers=headers,
        timeout=30
    )
    files = r.json().get("files", [])
    os.makedirs(output_dir, exist_ok=True)

    downloaded = []
    for f in files:
        fname = f.get("file_name", "")
        if not fname.endswith(".tif"):
            continue
        file_id = f["file_id"]
        out_path = os.path.join(output_dir, os.path.basename(fname))
        if os.path.exists(out_path):
            downloaded.append(out_path)
            continue
        print(f"  Downloading {fname}...")
        url = f"https://appeears.earthdatacloud.nasa.gov/api/bundle/{task_id}/{file_id}"
        r = requests.get(url, headers=headers, allow_redirects=True, stream=True, timeout=120)
        r.raise_for_status()
        with open(out_path, "wb") as fp:
            for chunk in r.iter_content(chunk_size=8192):
                fp.write(chunk)
        downloaded.append(out_path)

    return downloaded


def extract_points_from_tifs(tif_paths, grid_path):
    """Extract LST values at grid cell centroids from GeoTIFFs."""
    import rasterio

    with open(grid_path) as f:
        grid = json.load(f)

    # Build point list
    points = []
    for feat in grid["features"]:
        props = feat["properties"]
        points.append({
            "cell_id": props["cell_id"],
            "lon": props["centroid_lon"],
            "lat": props["centroid_lat"],
        })

    # For each point, sample all TIFs
    cell_values = {p["cell_id"]: [] for p in points}

    for tif_path in tif_paths:
        try:
            with rasterio.open(tif_path) as src:
                for p in points:
                    # Sample at point (lon, lat)
                    try:
                        row, col = src.index(p["lon"], p["lat"])
                        if 0 <= row < src.height and 0 <= col < src.width:
                            val = src.read(1)[row, col]
                            if val != src.nodata and not np.isnan(val) and val > 0:
                                # Convert from Kelvin to Celsius (scale factor 0.02)
                                temp_c = val * 0.02 - 273.15
                                if 10 < temp_c < 70:  # Physical range check
                                    cell_values[p["cell_id"]].append(temp_c)
                    except Exception:
                        continue
        except Exception as e:
            print(f"  Error reading {tif_path}: {e}")
            continue

    return cell_values


def build_ecostress_geojson(cell_values, grid_path, output_path):
    """Build GeoJSON FeatureCollection with median ECOSTRESS LST."""
    with open(grid_path) as f:
        grid = json.load(f)

    features = []
    for feat in grid["features"]:
        cell_id = feat["properties"]["cell_id"]
        vals = cell_values.get(cell_id, [])
        median_val = round(float(np.median(vals)), 2) if vals else None
        features.append({
            "type": "Feature",
            "properties": {
                "cell_id": cell_id,
                "lst_celsius": median_val,
                "ecostress_count": len(vals),
            },
            "geometry": feat["geometry"],
        })

    output = {"type": "FeatureCollection", "features": features}
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    valid = sum(1 for feat in features if feat["properties"]["lst_celsius"] is not None)
    print(f"ECOSTRESS: {valid}/{len(features)} cells with data")
    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--username", default="heetisk")
    parser.add_argument("--password", default="Heetisk@2007")
    parser.add_argument("--grid", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cache-dir", default="data/raw/ecostress")
    args = parser.parse_args()

    print("Downloading ECOSTRESS files...")
    tifs = download_ecostress_files(args.task_id, args.username, args.password, args.cache_dir)
    print(f"Downloaded {len(tifs)} files")

    print("Extracting point values...")
    cell_values = extract_points_from_tifs(tifs, args.grid)

    print("Building GeoJSON...")
    build_ecostress_geojson(cell_values, args.grid, args.output)
