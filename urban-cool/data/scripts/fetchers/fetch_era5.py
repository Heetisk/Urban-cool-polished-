"""
Fetch ERA5 Land Hourly weather data via CDS API.

Output: data/raw/era5/era5_{city}_{year}.nc (raw NetCDF)
        data/raw/era5/era5_{city}_{year}.json (metadata)
"""

import cdsapi
import json
import os
import zipfile
import argparse
from typing import Dict
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env"))

CDS_URL = os.environ.get("CDS_URL", "https://cds.climate.copernicus.eu/api")
CDS_KEY = os.environ.get("CDS_API_KEY")


def download_era5(bounds: Dict, city: str, year: int, output_dir: str) -> str:
    """Download ERA5-Land hourly data from CDS."""
    os.makedirs(output_dir, exist_ok=True)
    nc_path = os.path.join(output_dir, f"era5_{city}_{year}.nc")

    if os.path.exists(nc_path):
        print(f"  Using existing: {nc_path}")
        return nc_path

    client = cdsapi.Client(url=CDS_URL, key=CDS_KEY)

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
        "month": [f"{m:02d}" for m in range(4, 9)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": ["06:00", "09:00", "12:00", "15:00", "18:00"],
        "area": [bounds["lat_max"], bounds["lon_min"], bounds["lat_min"], bounds["lon_max"]],
        "format": "netcdf",
    }

    print(f"  Downloading ERA5-Land from CDS...")
    zip_path = nc_path + ".zip"
    client.retrieve("reanalysis-era5-land", request, zip_path)

    with zipfile.ZipFile(zip_path, "r") as z:
        nc_filename = z.namelist()[0]
        z.extractall(output_dir)
        extracted_path = os.path.join(output_dir, nc_filename)
        os.rename(extracted_path, nc_path)
    os.remove(zip_path)

    print(f"  Downloaded: {nc_path}")
    return nc_path


def save_metadata(bounds: Dict, city: str, year: int, nc_path: str, output_dir: str):
    """Save ERA5 dataset metadata."""
    meta = {
        "source": "ERA5-Land Hourly",
        "dataset_id": "ECMWF/ERA5_LAND/HOURLY",
        "cds_dataset": "reanalysis-era5-land",
        "city": city,
        "year": year,
        "bounds": bounds,
        "variables": ["t2m", "d2m", "u10", "v10", "ssrd"],
        "variable_names": {
            "t2m": "2m_temperature",
            "d2m": "2m_dewpoint_temperature",
            "u10": "10m_u_component_of_wind",
            "v10": "10m_v_component_of_wind",
            "ssrd": "surface_solar_radiation_downwards",
        },
        "resolution_km": 9,
        "units": {
            "t2m": "Kelvin",
            "d2m": "Kelvin",
            "u10": "m/s",
            "v10": "m/s",
            "ssrd": "J/m2 (cumulative)",
        },
        "file": nc_path,
    }

    meta_path = os.path.join(output_dir, f"era5_{city}_{year}_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return meta_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch ERA5 weather data")
    parser.add_argument("--city", default="ahmedabad")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--output-dir", default="data/raw/era5")
    parser.add_argument("--lat-min", type=float, default=23.0)
    parser.add_argument("--lat-max", type=float, default=23.15)
    parser.add_argument("--lon-min", type=float, default=72.5)
    parser.add_argument("--lon-max", type=float, default=72.68)
    args = parser.parse_args()

    bounds = {
        "lat_min": args.lat_min, "lat_max": args.lat_max,
        "lon_min": args.lon_min, "lon_max": args.lon_max,
    }

    print(f"=== ERA5 Data Fetcher ===")
    print(f"City: {args.city}, Year: {args.year}")

    nc_path = download_era5(bounds, args.city, args.year, args.output_dir)
    meta_path = save_metadata(bounds, args.city, args.year, nc_path, args.output_dir)

    print(f"Metadata: {meta_path}")
    print("Done!")
