"""
Fetch Land Surface Temperature from ECOSTRESS for validation.

Dataset: NASA/ECOSTRESS/LSTE_GEO/V002
Source: Google Earth Engine Data Catalog

Important:
- ECOSTRESS has MUCH less coverage than Landsat (~70m resolution, irregular revisit)
- Use for validation/hotspot verification, NOT as primary source
- Many grid cells may have no ECOSTRESS data

For UrbanCool: samples ECOSTRESS LST where available for cross-validation with Landsat 8.
"""

import ee
import json
import argparse
from typing import List, Dict


def init_gee(project: str = None):
    """Initialize Google Earth Engine."""
    try:
        ee.Initialize(project=project)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)


def get_ecostress_collection(aoi: ee.Geometry, start_date: str, end_date: str) -> ee.ImageCollection:
    """
    Get ECOSTRESS LST collection.

    Dataset: NASA/ECOSTRESS/LSTE_GEO/V002
    Band: LST (Land Surface Temperature in Kelvin)
    """
    collection = (
        ee.ImageCollection("NASA/ECOSTRESS/LSTE_GEO/V002")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
    )

    def convert_temp(image: ee.Image) -> ee.Image:
        """Convert LST from Kelvin to Celsius."""
        lst_celsius = image.select("LST").subtract(273.15).rename("LST_C")
        return image.addBands(lst_celsius, overwrite=True)

    return collection.map(convert_temp)


def sample_ecostress_at_points(
    collection: ee.ImageCollection, points: List[Dict], scale: int = 70
) -> List[Dict]:
    """
    Sample ECOSTRESS LST at point locations.

    Args:
        collection: ee.ImageCollection with LST_C band
        points: list of {"id": ..., "lat": ..., "lon": ...}
        scale: ~70m native resolution

    Returns:
        list of {"id": ..., "ecostress_lst": ..., "ecostress_count": ...}
    """
    fc = ee.FeatureCollection(
        [ee.Feature(ee.Geometry.Point([p["lon"], p["lat"]]), {"id": p["id"]}) for p in points]
    )

    # Count available images per point
    count_image = collection.select("LST_C").count().rename("count")

    # Compute median LST where available
    median_lst = collection.select("LST_C").median()

    # Sample both
    sampled_count = count_image.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.first(),
        scale=scale,
    )
    sampled_lst = median_lst.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )

    count_results = sampled_count.getInfo()
    lst_results = sampled_lst.getInfo()

    count_map = {}
    for feature in count_results["features"]:
        props = feature["properties"]
        count_map[props.get("id")] = props.get("first")

    output = []
    for feature in lst_results["features"]:
        props = feature["properties"]
        cell_id = props.get("id")
        output.append({
            "id": cell_id,
            "ecostress_lst": round(props.get("mean"), 2) if props.get("mean") is not None else None,
            "ecostress_count": count_map.get(cell_id, 0),
        })

    return output


def fetch_ecostress(grid_path: str, output_path: str, year: int = 2024, project: str = None):
    """
    Fetch ECOSTRESS LST for validation.

    Args:
        grid_path: path to master_grid.geojson
        output_path: path to write lst_ecostress_grid.geojson
        year: year for data
        project: GEE project ID
    """
    init_gee(project)

    with open(grid_path) as f:
        grid = json.load(f)

    points = []
    for feature in grid["features"]:
        props = feature["properties"]
        points.append({
            "id": props["cell_id"],
            "lat": props["centroid_lat"],
            "lon": props["centroid_lon"],
        })

    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    aoi = ee.Geometry.Rectangle([min(lons), min(lats), max(lons), max(lats)])

    # ECOSTRESS has less temporal coverage, use full year
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    print(f"Fetching ECOSTRESS LST for {len(points)} points...")
    print(f"Date range: {start_date} to {end_date}")

    collection = get_ecostress_collection(aoi, start_date, end_date)
    print(f"Collection size: {collection.size().getInfo()} images")

    results = sample_ecostress_at_points(collection, points, scale=70)

    # Convert to GeoJSON FeatureCollection for load_intermediate() compatibility
    features = []
    for r in results:
        features.append({
            "type": "Feature",
            "properties": {
                "cell_id": r["id"],
                "lst_celsius": r["ecostress_lst"],
                "ecostress_count": r["ecostress_count"],
            },
            "geometry": None,
        })

    output = {"type": "FeatureCollection", "features": features}

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    valid = [r for r in results if r["ecostress_lst"] is not None]
    print(f"Results: {len(valid)}/{len(points)} points with ECOSTRESS data")
    print(f"Saved to {output_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch ECOSTRESS LST (validation)")
    parser.add_argument("--grid", default="data/processed/grid.json")
    parser.add_argument("--output", default="data/processed/lst_ecostress.json")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--project", default=None, help="GEE project ID")
    args = parser.parse_args()

    fetch_ecostress(args.grid, args.output, args.year, args.project)
