"""
Fetch Land Use / Land Cover from Sentinel-2 Surface Reflectance.

Dataset: COPERNICUS/S2_SR_HARMONIZED
Source: Google Earth Engine Data Catalog

Provides:
- NDVI (Normalized Difference Vegetation Index) from B8/B4
- NDWI (Normalized Difference Water Index) from B3/B8
- NDBI (Normalized Difference Built-up Index) from B11/B8
- Built-up area detection
- Water body detection

For UrbanCool: extracts vegetation, built-up, and water indices per grid cell.
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


def get_sentinel2_collection(aoi: ee.Geometry, start_date: str, end_date: str) -> ee.ImageCollection:
    """
    Get Sentinel-2 Surface Reflectance collection.

    Dataset: COPERNICUS/S2_SR_HARMONIZED
    Applies cloud masking and computes spectral indices.
    """
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    )

    def mask_clouds_and_indices(image: ee.Image) -> ee.Image:
        """Mask clouds and compute spectral indices."""
        # Cloud mask using QA60 band
        qa = image.select("QA60")
        cloud_mask = qa.bitwiseAnd(1 << 10).eq(0)  # Cirrus
        cloud_mask2 = qa.bitwiseAnd(1 << 11).eq(0)  # Cloud
        mask = cloud_mask.And(cloud_mask2)

        # Compute indices
        ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
        ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
        ndbi = image.normalizedDifference(["B11", "B8"]).rename("NDBI")

        return (
            image.addBands([ndvi, ndwi, ndbi], overwrite=True)
            .updateMask(mask)
        )

    return collection.map(mask_clouds_and_indices)


def sample_lulc_at_points(
    collection: ee.ImageCollection, points: List[Dict], scale: int = 10
) -> Dict:
    """
    Sample LULC indices at point locations.

    Args:
        collection: ee.ImageCollection with NDVI, NDWI, NDBI bands
        points: list of {"id": ..., "lat": ..., "lon": ...}
        scale: 10m native resolution

    Returns:
        GeoJSON FeatureCollection with cell_id, ndvi, ndwi, ndbi per feature.
    """
    fc = ee.FeatureCollection(
        [ee.Feature(ee.Geometry.Point([p["lon"], p["lat"]]), {"cell_id": p["id"]}) for p in points]
    )

    # Compute median values across cloud-free images
    median_img = collection.select(["NDVI", "NDWI", "NDBI"]).median()

    sampled = median_img.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )

    results = sampled.getInfo()
    features = []
    for feature in results["features"]:
        props = feature["properties"]
        features.append({
            "type": "Feature",
            "properties": {
                "cell_id": props.get("cell_id"),
                "ndvi": round(props.get("NDVI"), 4) if props.get("NDVI") is not None else None,
                "ndwi": round(props.get("NDWI"), 4) if props.get("NDWI") is not None else None,
                "ndbi": round(props.get("NDBI"), 4) if props.get("NDBI") is not None else None,
            },
            "geometry": None,
        })

    return {"type": "FeatureCollection", "features": features}


def fetch_lulc(grid_path: str, output_path: str, city: str, year: int = 2024, project: str = None):
    """
    Fetch Sentinel-2 LULC indices for all grid cells.

    Args:
        grid_path: path to master_grid.geojson
        output_path: path to write lulc_sentinel2_grid.geojson
        city: city name
        year: year for data collection
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

    # Use summer (Apr-Aug) to match Landsat 8 temperature period
    start_date = f"{year}-04-01"
    end_date = f"{year}-08-31"

    print(f"Fetching Sentinel-2 LULC for {len(points)} points...")
    print(f"Date range: {start_date} to {end_date}")

    collection = get_sentinel2_collection(aoi, start_date, end_date)
    print(f"Collection size: {collection.size().getInfo()} images")

    result = sample_lulc_at_points(collection, points, scale=10)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    valid = [feat for feat in result["features"] if feat["properties"]["ndvi"] is not None]
    print(f"Results: {len(valid)}/{len(result['features'])} points with valid LULC")
    print(f"Saved to {output_path}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Sentinel-2 LULC")
    parser.add_argument("--grid", required=True, help="Path to master_grid.geojson")
    parser.add_argument("--output", required=True, help="Output GeoJSON path")
    parser.add_argument("--city", default="ahmedabad")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--project", default=None, help="GEE project ID")
    args = parser.parse_args()

    fetch_lulc(args.grid, args.output, args.city, args.year, args.project)
