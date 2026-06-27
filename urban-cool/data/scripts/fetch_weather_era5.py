"""
Fetch Weather Data from ERA5 Land Hourly.

Dataset: ECMWF/ERA5_LAND/HOURLY
Source: Google Earth Engine Data Catalog

Provides:
- Air Temperature (2m) - temp
- Relative Humidity (2m) - relative_humidity
- Wind Speed (10m) - wind_speed
- Solar Radiation - solar_radiation

For UrbanCool: extracts weather parameters per grid cell for heat analysis.
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


def get_era5_collection(aoi: ee.Geometry, start_date: str, end_date: str) -> ee.ImageCollection:
    """
    Get ERA5 Land Hourly collection.

    Dataset: ECMWF/ERA5_LAND/HOURLY
    Key bands:
    - temperature_2m: Air temperature at 2m (Kelvin)
    - relative_humidity_2m: Relative humidity at 2m (%)
    - u_component_of_wind_10m: U-component of wind at 10m
    - v_component_of_wind_10m: V-component of wind at 10m
    - surface_solar_radiation_downwards: Solar radiation (J/m²)
    """
    collection = (
        ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
    )

    def process_bands(image: ee.Image) -> ee.Image:
        """Convert units and compute derived metrics."""
        # Temperature: Kelvin to Celsius
        temp_celsius = image.select("temperature_2m").subtract(273.15).rename("temp_celsius")

        # Wind speed from components
        wind_speed = (
            image.select("u_component_of_wind_10m").pow(2)
            .add(image.select("v_component_of_wind_10m").pow(2))
            .sqrt()
            .rename("wind_speed_ms")
        )

        # Solar radiation: J/m² to W/m² (divide by 3600 for hourly average)
        solar = image.select("surface_solar_radiation_downwards").divide(3600).rename("solar_wm2")

        return image.addBands([temp_celsius, wind_speed, solar], overwrite=True)

    return collection.map(process_bands)


def sample_weather_at_points(
    collection: ee.ImageCollection, points: List[Dict], scale: int = 11132
) -> List[Dict]:
    """
    Sample weather data at point locations.

    ERA5 Land has ~11km resolution, so use scale=11132m.

    Args:
        collection: ee.ImageCollection with processed weather bands
        points: list of {"id": ..., "lat": ..., "lon": ...}
        scale: ~11km native resolution

    Returns:
        list of {"id": ..., "temp_celsius": ..., "humidity_pct": ..., "wind_speed_ms": ..., "solar_wm2": ...}
    """
    fc = ee.FeatureCollection(
        [ee.Feature(ee.Geometry.Point([p["lon"], p["lat"]]), {"id": p["id"]}) for p in points]
    )

    # Select bands to sample
    bands = ["temp_celsius", "relative_humidity_2m", "wind_speed_ms", "solar_wm2"]
    available_bands = collection.first().bandNames().getInfo()
    bands = [b for b in bands if b in available_bands]

    median_img = collection.select(bands).median()

    sampled = median_img.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )

    results = sampled.getInfo()
    output = []
    for feature in results["features"]:
        props = feature["properties"]
        output.append({
            "id": props.get("id"),
            "temp_celsius": round(props.get("temp_celsius"), 2) if props.get("temp_celsius") is not None else None,
            "humidity_pct": round(props.get("relative_humidity_2m"), 2) if props.get("relative_humidity_2m") is not None else None,
            "wind_speed_ms": round(props.get("wind_speed_ms"), 2) if props.get("wind_speed_ms") is not None else None,
            "solar_wm2": round(props.get("solar_wm2"), 2) if props.get("solar_wm2") is not None else None,
        })

    return output


def fetch_weather(grid_path: str, output_path: str, year: int = 2024, project: str = None):
    """
    Fetch ERA5 weather data for all grid cells.

    Args:
        grid_path: path to grid.json
        output_path: path to write weather_results.json
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

    # Summer months for maximum heat signal
    start_date = f"{year}-04-01"
    end_date = f"{year}-08-31"

    print(f"Fetching ERA5 weather for {len(points)} points...")
    print(f"Date range: {start_date} to {end_date}")

    collection = get_era5_collection(aoi, start_date, end_date)
    print(f"Collection size: {collection.size().getInfo()} images")

    results = sample_weather_at_points(collection, points, scale=11132)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    valid = [r for r in results if r["temp_celsius"] is not None]
    print(f"Results: {len(valid)}/{len(points)} points with valid weather")
    print(f"Saved to {output_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch ERA5 weather data")
    parser.add_argument("--grid", default="data/processed/grid.json")
    parser.add_argument("--output", default="data/processed/weather_era5.json")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--project", default=None, help="GEE project ID")
    args = parser.parse_args()

    fetch_weather(args.grid, args.output, args.year, args.project)
