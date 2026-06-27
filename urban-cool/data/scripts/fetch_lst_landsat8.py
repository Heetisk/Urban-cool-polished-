"""
Fetch Land Surface Temperature from Landsat 8 Collection 2 Level 2.

Dataset: LANDSAT/LC08/C02/T1_L2
Source: Google Earth Engine Data Catalog

Provides:
- Surface Temperature (ST_B10) - in Kelvin, scaled by 0.00341802
- Surface Reflectance for all optical bands

For UrbanCool: extracts mean LST per grid cell centroid.
Output: GeoJSON FeatureCollection compatible with feature_engineering.py.
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


def get_lst_collection(aoi: ee.Geometry, start_date: str, end_date: str) -> ee.ImageCollection:
    """
    Get Landsat 8 Collection 2 Level 2 surface temperature collection.

    Returns cloud-masked collection with ST band scaled to Celsius.
    """
    collection = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUD_COVER", 30))
    )

    def mask_clouds(image: ee.Image) -> ee.Image:
        """Cloud mask using QA_PIXEL band."""
        qa = image.select("QA_PIXEL")
        cloud_mask = qa.bitwiseAnd(1 << 3).eq(0)  # Cloud
        cloud_shadow_mask = qa.bitwiseAnd(1 << 4).eq(0)  # Cloud shadow
        mask = cloud_mask.And(cloud_shadow_mask)

        # Scale ST_B10 to Celsius (Collection 2 Level 2: scale=0.00341802, offset=149.0)
        lst = image.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15)

        return image.addBands(lst.rename("LST"), overwrite=True).updateMask(mask)

    return collection.map(mask_clouds)


def sample_lst_at_points(
    collection: ee.ImageCollection, points: List[Dict], scale: int = 30
) -> Dict:
    """
    Sample LST at point locations from the collection.

    Args:
        collection: ee.ImageCollection with LST band
        points: list of {"id": ..., "lat": ..., "lon": ...}
        scale: resolution in meters

    Returns:
        GeoJSON FeatureCollection with cell_id and lst_celsius per feature.
    """
    fc = ee.FeatureCollection(
        [ee.Feature(ee.Geometry.Point([p["lon"], p["lat"]]), {"cell_id": p["id"]}) for p in points]
    )

    # Compute median LST across all cloud-free images
    median_lst = collection.select("LST").median()

    # Sample at points
    sampled = median_lst.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )

    results = sampled.getInfo()
    features = []
    for feature in results["features"]:
        props = feature["properties"]
        lst = round(props.get("mean"), 2) if props.get("mean") is not None else None
        features.append({
            "type": "Feature",
            "properties": {
                "cell_id": props.get("cell_id"),
                "lst_celsius": lst,
            },
            "geometry": None,
        })

    return {"type": "FeatureCollection", "features": features}


def fetch_lst(grid_path: str, output_path: str, city: str, year: int = 2024, project: str = None):
    """
    Main function: fetch LST for all grid cells.

    Args:
        grid_path: path to master_grid.geojson with cell centroids
        output_path: path to write lst_landsat8_grid.geojson
        city: city name for date range selection
        year: year for data collection
        project: GEE project ID
    """
    init_gee(project)

    with open(grid_path) as f:
        grid = json.load(f)

    # Extract centroids as points
    points = []
    for feature in grid["features"]:
        props = feature["properties"]
        points.append({
            "id": props["cell_id"],
            "lat": props["centroid_lat"],
            "lon": props["centroid_lon"],
        })

    # Define AOI from grid bounds
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    aoi = ee.Geometry.Rectangle([min(lons), min(lats), max(lons), max(lats)])

    # Date range: summer months for maximum heat signal
    start_date = f"{year}-04-01"
    end_date = f"{year}-08-31"

    print(f"Fetching Landsat 8 LST for {len(points)} points...")
    print(f"Date range: {start_date} to {end_date}")

    collection = get_lst_collection(aoi, start_date, end_date)
    print(f"Collection size: {collection.size().getInfo()} images")

    result = sample_lst_at_points(collection, points, scale=30)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    valid = [feat for feat in result["features"] if feat["properties"]["lst_celsius"] is not None]
    print(f"Results: {len(valid)}/{len(result['features'])} points with valid LST")
    print(f"Saved to {output_path}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Landsat 8 LST")
    parser.add_argument("--grid", required=True, help="Path to master_grid.geojson")
    parser.add_argument("--output", required=True, help="Output GeoJSON path")
    parser.add_argument("--city", default="ahmedabad")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--project", default=None, help="GEE project ID")
    args = parser.parse_args()

    fetch_lst(args.grid, args.output, args.city, args.year, args.project)
