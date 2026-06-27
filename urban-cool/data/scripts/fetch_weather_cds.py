"""
Fetch ERA5 Land Hourly weather data via CDS API (Free, no GEE needed).

Dataset: ERA5-Land hourly
Source: Copernicus Climate Data Store (CDS)

Provides:
- Air Temperature (2m) - temp_celsius
- Relative Humidity (2m) - humidity_pct
- Wind Speed (10m) - wind_speed_ms
- Solar Radiation - solar_wm2

For UrbanCool: extracts weather parameters per grid cell for heat analysis.
"""

import cdsapi
import json
import os
import zipfile
import argparse
import xarray as xr
import numpy as np
from typing import List, Dict


CDS_URL = "https://cds.climate.copernicus.eu/api"
CDS_KEY = "c4c1047c-656d-4242-bafb-1ea88c1a0b4c"

CITIES = {
    "ahmedabad": {"lat_min": 23.0, "lat_max": 23.15, "lon_min": 72.5, "lon_max": 72.68},
    "delhi": {"lat_min": 28.4, "lat_max": 28.7, "lon_min": 77.0, "lon_max": 77.4},
    "mumbai": {"lat_min": 18.88, "lat_max": 19.1, "lon_min": 72.78, "lon_max": 72.98},
}


def download_era5(bounds: Dict, year: int, output_nc: str) -> str:
    """
    Download ERA5-Land hourly data from CDS.

    Args:
        bounds: {"lat_min", "lat_max", "lon_min", "lon_max"}
        year: year to download
        output_nc: output NetCDF path

    Returns:
        path to downloaded file
    """
    client = cdsapi.Client(url=CDS_URL, key=CDS_KEY)

    months = [f"{m:02d}" for m in range(4, 9)]  # April-August (summer)

    request = {
        "product_type": "reanalysis",
        "variable": [
            "2m_temperature",
            "2m_dewpoint_temperature",
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "surface_solar_radiation_downwards",
        ],
        "year": str(year),
        "month": months,
        "day": [
            "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
            "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
            "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31",
        ],
        "time": [
            "06:00", "09:00", "12:00", "15:00", "18:00",
        ],
        "area": [
            bounds["lat_max"],  # North
            bounds["lon_min"],  # West
            bounds["lat_min"],  # South
            bounds["lon_max"],  # East
        ],
        "format": "netcdf",
    }

    print(f"Downloading ERA5-Land data...")
    print(f"  Area: {bounds}")
    print(f"  Year: {year}, Months: April-August")
    print(f"  Variables: temperature, dewpoint, wind, solar radiation")
    print(f"  This may take 5-15 minutes...")

    zip_path = output_nc + ".zip"
    client.retrieve("reanalysis-era5-land", request, zip_path)

    # CDS returns a zip archive - extract it
    with zipfile.ZipFile(zip_path, "r") as z:
        nc_filename = z.namelist()[0]
        z.extractall(os.path.dirname(output_nc))
        extracted_path = os.path.join(os.path.dirname(output_nc), nc_filename)
        os.rename(extracted_path, output_nc)
    os.remove(zip_path)

    print(f"  Downloaded to: {output_nc}")
    return output_nc


def extract_at_points(nc_path: str, points: List[Dict]) -> List[Dict]:
    """
    Extract weather variables at point locations from NetCDF.

    Args:
        nc_path: path to ERA5 NetCDF file
        points: list of {"id": ..., "lat": ..., "lon": ...}

    Returns:
        list of {"id": ..., "temp_celsius": ..., "humidity_pct": ..., "wind_speed_ms": ..., "solar_wm2": ...}
    """
    ds = xr.open_dataset(nc_path)

    results = []
    for point in points:
        cell_id = point["id"]
        lat = point["lat"]
        lon = point["lon"]

        try:
            # Select nearest point (ERA5 Land ~9km grid)
            sample = ds.sel(latitude=lat, longitude=lon, method="nearest")

            # Temperature: K → °C
            temp_k = float(sample["t2m"].mean().values)
            temp_c = round(temp_k - 273.15, 2)

            # Dewpoint: K → °C
            dew_k = float(sample["d2m"].mean().values)
            dew_c = dew_k - 273.15

            # Relative humidity from temperature and dewpoint (Magnus formula)
            a, b = 17.27, 237.7
            alpha_t = (a * temp_c) / (b + temp_c)
            alpha_d = (a * dew_c) / (b + dew_c)
            humidity = round(100 * np.exp(alpha_d - alpha_t), 2)
            humidity = max(0, min(100, humidity))

            # Wind speed: sqrt(u² + v²)
            u = float(sample["u10"].mean().values)
            v = float(sample["v10"].mean().values)
            wind = round(np.sqrt(u**2 + v**2), 2)

            # Solar radiation: ssrd is cumulative J/m² through the day
            # Compute per-hour values by taking differences
            solar_j = sample["ssrd"].values
            # Diff between consecutive timesteps gives J/m² per interval
            solar_diff = np.diff(solar_j, prepend=solar_j[0])
            # Only positive values (reset to 0 at day boundary)
            solar_diff = np.where(solar_diff > 0, solar_diff, 0)
            # Convert J/m² to W/m² (divide by seconds in interval: ~3h = 10800s)
            solar_w = round(float(np.mean(solar_diff)) / 10800, 2)

            results.append({
                "id": cell_id,
                "temp_celsius": temp_c,
                "humidity_pct": humidity,
                "wind_speed_ms": wind,
                "solar_wm2": solar_w,
            })

        except Exception as e:
            print(f"  Warning: {cell_id} failed: {e}")
            results.append({
                "id": cell_id,
                "temp_celsius": None,
                "humidity_pct": None,
                "wind_speed_ms": None,
                "solar_wm2": None,
            })

    ds.close()
    return results


def fetch_weather(
    grid_path: str,
    output_path: str,
    city: str = "ahmedabad",
    year: int = 2024,
    download_dir: str = "data/rasters",
):
    """
    Main function: fetch ERA5 weather for all grid cells.

    Args:
        grid_path: path to grid.json with cell centroids
        output_path: path to write weather_era5.json
        city: city name
        year: year for data
        download_dir: directory for NetCDF downloads
    """
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

    # Get bounds
    if city in CITIES:
        bounds = CITIES[city]
    else:
        lats = [p["lat"] for p in points]
        lons = [p["lon"] for p in points]
        bounds = {"lat_min": min(lats), "lat_max": max(lats), "lon_min": min(lons), "lon_max": max(lons)}

    # Download
    os.makedirs(download_dir, exist_ok=True)
    nc_path = os.path.join(download_dir, f"era5_{city}_{year}.nc")

    if not os.path.exists(nc_path):
        download_era5(bounds, year, nc_path)
    else:
        print(f"Using existing: {nc_path}")

    # Extract
    print(f"\nExtracting weather at {len(points)} grid cells...")
    results = extract_at_points(nc_path, points)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    valid = [r for r in results if r["temp_celsius"] is not None]
    print(f"Results: {len(valid)}/{len(points)} points with valid weather")
    print(f"Saved to {output_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch ERA5 weather via CDS API")
    parser.add_argument("--grid", default="data/processed/grid.json")
    parser.add_argument("--output", default="data/processed/weather_era5.json")
    parser.add_argument("--city", default="ahmedabad", choices=list(CITIES.keys()))
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--download-dir", default="data/rasters")
    args = parser.parse_args()

    fetch_weather(args.grid, args.output, args.city, args.year, args.download_dir)
