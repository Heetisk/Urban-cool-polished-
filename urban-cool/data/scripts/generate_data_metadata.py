"""
Extract data timestamps from raw file names and ERA5 NetCDF.

Generates data_metadata.json for each city with:
- MODIS LST date range
- MODIS NDVI composites
- ERA5 time coverage
- Pipeline run timestamp
"""

import json
import os
import re
from datetime import datetime, timedelta


def julian_day_to_date(year: int, day_of_year: int) -> str:
    """Convert year + day-of-year to ISO date string."""
    base = datetime(year, 1, 1) + timedelta(days=day_of_year - 1)
    return base.strftime("%Y-%m-%d")


def extract_modis_dates(satellite_dir: str) -> dict:
    """Extract dates from MODIS HDF filenames."""
    lst_dates = []
    ndvi_dates = []

    if not os.path.isdir(satellite_dir):
        return {"lst": {}, "ndvi": {}}

    for fname in os.listdir(satellite_dir):
        if not fname.endswith(".hdf"):
            continue

        # MOD11A1.A2024153.h24v06.061.2024157191928.hdf
        match = re.match(r"(MOD11A1|MOD13A2)\.A(\d{4})(\d{3})\.", fname)
        if not match:
            continue

        product = match.group(1)
        year = int(match.group(2))
        day = int(match.group(3))
        date_str = julian_day_to_date(year, day)

        if product == "MOD11A1":
            lst_dates.append(date_str)
        elif product == "MOD13A2":
            ndvi_dates.append(date_str)

    lst_dates.sort()
    ndvi_dates.sort()

    result = {}
    if lst_dates:
        result["lst"] = {
            "product": "MOD11A1 (Daily 1km)",
            "start_date": lst_dates[0],
            "end_date": lst_dates[-1],
            "num_days": len(lst_dates),
            "dates": lst_dates,
        }
    if ndvi_dates:
        result["ndvi"] = {
            "product": "MOD13A2 (16-day 1km)",
            "dates": ndvi_dates,
            "num_composites": len(ndvi_dates),
        }

    return result


def extract_era5_dates(nc_path: str) -> dict:
    """Extract time range from ERA5 NetCDF."""
    if not os.path.exists(nc_path):
        return {}

    try:
        import netCDF4 as nc

        ds = nc.Dataset(nc_path, "r")
        times = ds.variables.get("valid_time") or ds.variables.get("time")
        if times is None:
            ds.close()
            return {}

        # Get first and last timestamps
        t_first = times[0]
        t_last = times[-1]

        # Convert to date strings
        units = times.units
        # e.g., "seconds since 1979-01-01T00:00:00"
        match = re.match(r"\w+ since (\d{4}-\d{2}-\d{2})", units)
        base_date = match.group(1) if match else "1979-01-01"

        try:
            start = nc.num2date(t_first, units=units)
            end = nc.num2date(t_last, units=units)
            start_str = start.strftime("%Y-%m-%d %H:%M")
            end_str = end.strftime("%Y-%m-%d %H:%M")
        except Exception:
            start_str = base_date
            end_str = "unknown"

        ds.close()
        return {
            "product": "ERA5-Land Reanalysis",
            "start_date": start_str,
            "end_date": end_str,
        }
    except Exception as e:
        return {"error": str(e)}


def extract_gee_dates(geojson_path: str) -> dict:
    """Extract cell count from a GEE intermediate GeoJSON."""
    if not os.path.exists(geojson_path):
        return {}

    try:
        with open(geojson_path) as f:
            data = json.load(f)

        return {
            "count": len(data.get("features", [])),
        }
    except Exception as e:
        return {"error": str(e)}


def extract_cpcb_dates(cpcb_path: str) -> dict:
    """Extract metadata from CPCB AQI JSON."""
    if not os.path.exists(cpcb_path):
        return {}

    try:
        with open(cpcb_path) as f:
            data = json.load(f)

        if isinstance(data, list):
            stations = len(data)
        elif isinstance(data, dict):
            stations = len(data)
        else:
            stations = 0

        return {
            "stations": stations,
            "source": "CPCB API (real-time)",
        }
    except Exception as e:
        return {"error": str(e)}


def generate_metadata(city: str, city_dir: str) -> dict:
    """Generate full metadata for a city."""
    satellite_dir = os.path.join(city_dir, "raw", "satellite")
    era5_path = os.path.join(city_dir, "raw", "era5", f"era5_{city}_2024.nc")
    intermediate_dir = os.path.join(city_dir, "intermediate")

    # Also check old locations (pre-per-city restructuring)
    if not os.path.exists(satellite_dir) or not os.listdir(satellite_dir):
        satellite_dir = os.path.join("data", "raw")
    if not any(f.endswith(".hdf") for f in os.listdir(satellite_dir) if os.path.isfile(os.path.join(satellite_dir, f))):
        for sub in ["satellite", "modis", "."]:
            candidate = os.path.join("data", "raw", sub) if sub != "." else os.path.join("data", "raw")
            if os.path.isdir(candidate) and any(f.endswith(".hdf") for f in os.listdir(candidate) if os.path.isfile(os.path.join(candidate, f))):
                satellite_dir = candidate
                break
    if not os.path.exists(era5_path):
        era5_path = os.path.join("data", "raw", "era5", f"era5_{city}_2024.nc")
    if not os.path.exists(era5_path):
        era5_path = os.path.join("data", "rasters", f"era5_{city}_2024.nc")

    modis = extract_modis_dates(satellite_dir)
    era5 = extract_era5_dates(era5_path)

    # GEE sources
    landsat8_path = os.path.join(intermediate_dir, "lst_landsat8_grid.geojson")
    sentinel2_path = os.path.join(intermediate_dir, "lulc_sentinel2_grid.geojson")
    cpcb_path = os.path.join(intermediate_dir, "cpcb_aqi.json")

    landsat8 = extract_gee_dates(landsat8_path)
    sentinel2 = extract_gee_dates(sentinel2_path)
    cpcb = extract_cpcb_dates(cpcb_path)

    # Build human-readable summary
    sources = []
    if landsat8 and "count" in landsat8:
        sources.append(f"Landsat 8 LST (GEE, 30m): {landsat8['count']} cells")
    if "lst" in modis:
        d = modis["lst"]
        sources.append(f"MODIS LST (fallback, 1km): {d['start_date']} to {d['end_date']} ({d['num_days']} days)")
    if sentinel2 and "count" in sentinel2:
        sources.append(f"Sentinel-2 NDVI (GEE, 10m): {sentinel2['count']} cells")
    if "ndvi" in modis:
        d = modis["ndvi"]
        dates_str = ", ".join(d["dates"])
        sources.append(f"MODIS NDVI (fallback, 1km): {dates_str} ({d['num_composites']} composites)")
    if era5 and "start_date" in era5:
        sources.append(f"ERA5 Reanalysis: {era5['start_date']} to {era5['end_date']}")
    if cpcb and "stations" in cpcb:
        sources.append(f"CPCB AQI: {cpcb['stations']} stations (real-time API)")
    sources.append("OSM: Roads, buildings, water bodies (current)")

    return {
        "city": city,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": sources,
        "landsat8": landsat8,
        "sentinel2": sentinel2,
        "modis": modis,
        "era5": era5,
        "cpcb": cpcb,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate data metadata")
    parser.add_argument("--city", required=True, help="City key")
    args = parser.parse_args()

    city_dir = os.path.join("data", args.city)
    meta = generate_metadata(args.city, city_dir)

    out_path = os.path.join(city_dir, "processed", "data_metadata.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Generated {out_path}")
    for s in meta["sources"]:
        print(f"  {s}")
