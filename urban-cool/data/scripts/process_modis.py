"""
Download and process MODIS LST + NDVI from NASA Earthdata.

Uses earthaccess to search/download MODIS HDF4 tiles,
then extracts values at grid cell centroids using netCDF4.

Reads:
- data/{city}/processed/master_grid.geojson

Writes:
- data/{city}/raw/satellite/MOD11A1.*.hdf (LST daily)
- data/{city}/raw/satellite/MOD13A2.*.hdf (NDVI 16-day)
- data/{city}/intermediate/lst_grid.geojson
- data/{city}/intermediate/ndvi_grid.geojson
"""

import json
import os
import sys
import argparse
import math
import numpy as np
import earthaccess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_grid_cells(grid_path: str) -> list:
    with open(grid_path) as f:
        grid = json.load(f)
    return [
        {"cell_id": f["properties"]["cell_id"], "lat": f["properties"]["centroid_lat"], "lon": f["properties"]["centroid_lon"]}
        for f in grid["features"]
    ]


def download_modis_files(bounds: dict, tiles: list, output_dir: str, product: str, start_date: str, end_date: str) -> list:
    """Download MODIS files using earthaccess."""
    os.makedirs(output_dir, exist_ok=True)

    results = earthaccess.search_data(
        short_name=product,
        bounding_box=(bounds["lon_min"], bounds["lat_min"], bounds["lon_max"], bounds["lat_max"]),
        temporal=(start_date, end_date),
        count=50,
    )
    print(f"  Found {len(results)} {product} granules")

    if not results:
        return []

    downloaded = earthaccess.download(results, output_dir)
    paths = [str(d) for d in downloaded if str(d).endswith(".hdf")]
    print(f"  Downloaded {len(paths)} HDF files")
    return paths


def extract_lst_from_hdf(hdf_paths: list, cells: list) -> dict:
    """Extract LST from MODIS HDF4 files using netCDF4 (reads HDF4 natively).
    
    netCDF4 auto-applies scale_factor and add_offset, so values are already in Kelvin.
    """
    import netCDF4 as nc

    cell_values = {}
    for cell in cells:
        cell_values[cell["cell_id"]] = []

    for hdf_path in hdf_paths:
        try:
            ds = nc.Dataset(hdf_path, "r")

            lst_var = None
            qc_var = None
            for var_name in ds.variables:
                if "LST_Day" in var_name and "1km" in var_name:
                    lst_var = ds.variables[var_name]
                if "QC_Day" in var_name:
                    qc_var = ds.variables[var_name]

            if lst_var is None:
                print(f"  WARNING: No LST variable in {os.path.basename(hdf_path)}")
                ds.close()
                continue

            # Get bounds from StructMetadata.0
            struct_meta = ds.getncattr("StructMetadata.0")
            upper_left = None
            lower_right = None
            for line in struct_meta.split("\n"):
                if "UpperLeftPointMtrs" in line:
                    vals = line.split("(")[1].split(")")[0].split(",")
                    upper_left = (float(vals[0]), float(vals[1]))  # x, y
                if "LowerRight" in line and "Mtrs" in line:
                    vals = line.split("(")[1].split(")")[0].split(",")
                    lower_right = (float(vals[0]), float(vals[1]))  # x, y

            if upper_left is None or lower_right is None:
                print(f"  WARNING: Could not parse bounds from {os.path.basename(hdf_path)}")
                ds.close()
                continue

            # Convert from sinusoidal meters to lat/lon
            R = 6371007.181
            ul_x, ul_y = upper_left
            lr_x, lr_y = lower_right

            ul_lat = math.degrees(ul_y / R)
            ul_lon = math.degrees(ul_x / (R * math.cos(math.radians(ul_lat))))
            lr_lat = math.degrees(lr_y / R)
            lr_lon = math.degrees(lr_x / (R * math.cos(math.radians(lr_lat))))

            # Build lat/lon arrays from bounds
            nrows, ncols = lst_var.shape
            lat_arr = np.linspace(ul_lat, lr_lat, nrows)
            lon_arr = np.linspace(ul_lon, lr_lon, ncols)

            # Read the entire array (netCDF4 auto-scales to Kelvin)
            lst_data = lst_var[:]
            qc_data = qc_var[:] if qc_var is not None else None

            for cell in cells:
                lat_idx = np.argmin(np.abs(lat_arr - cell["lat"]))
                lon_idx = np.argmin(np.abs(lon_arr - cell["lon"]))

                raw_val = float(lst_data[lat_idx, lon_idx])
                if np.ma.is_masked(raw_val) or raw_val < 273.15:
                    # Search nearby pixels for valid data
                    found = False
                    for dr in range(-2, 3):
                        for dc in range(-2, 3):
                            r, c = lat_idx + dr, lon_idx + dc
                            if 0 <= r < nrows and 0 <= c < ncols:
                                v = float(lst_data[r, c])
                                if not np.ma.is_masked(v) and v > 273.15:
                                    raw_val = v
                                    found = True
                                    break
                        if found:
                            break
                    if not found:
                        cell_values[cell["cell_id"]].append(None)
                        continue

                temp_c = raw_val - 273.15
                if 15 < temp_c < 65:
                    cell_values[cell["cell_id"]].append(round(temp_c, 2))

            ds.close()
        except Exception as e:
            print(f"  WARNING: Error reading {os.path.basename(hdf_path)}: {e}")

    result = {}
    for cell in cells:
        vals = [v for v in cell_values[cell["cell_id"]] if v is not None]
        if vals:
            result[cell["cell_id"]] = {"lst_celsius": round(np.mean(vals), 2)}

    return result


def extract_ndvi_from_hdf(hdf_paths: list, cells: list) -> dict:
    """Extract NDVI from MODIS HDF4 files using netCDF4.
    
    netCDF4 auto-applies scale_factor and add_offset.
    """
    import netCDF4 as nc

    cell_values = {}
    for cell in cells:
        cell_values[cell["cell_id"]] = []

    for hdf_path in hdf_paths:
        try:
            ds = nc.Dataset(hdf_path, "r")

            ndvi_var = None
            for var_name in ds.variables:
                if "1 km 16 days NDVI" in var_name or "NDVI" in var_name:
                    ndvi_var = ds.variables[var_name]

            if ndvi_var is None:
                print(f"  WARNING: No NDVI variable in {os.path.basename(hdf_path)}")
                ds.close()
                continue

            # Get bounds from StructMetadata.0
            struct_meta = ds.getncattr("StructMetadata.0")
            upper_left = None
            lower_right = None
            for line in struct_meta.split("\n"):
                if "UpperLeftPointMtrs" in line:
                    vals = line.split("(")[1].split(")")[0].split(",")
                    upper_left = (float(vals[0]), float(vals[1]))
                if "LowerRight" in line and "Mtrs" in line:
                    vals = line.split("(")[1].split(")")[0].split(",")
                    lower_right = (float(vals[0]), float(vals[1]))

            if upper_left is None or lower_right is None:
                print(f"  WARNING: Could not parse bounds from {os.path.basename(hdf_path)}")
                ds.close()
                continue

            R = 6371007.181
            ul_x, ul_y = upper_left
            lr_x, lr_y = lower_right
            ul_lat = math.degrees(ul_y / R)
            ul_lon = math.degrees(ul_x / (R * math.cos(math.radians(ul_lat))))
            lr_lat = math.degrees(lr_y / R)
            lr_lon = math.degrees(lr_x / (R * math.cos(math.radians(lr_lat))))

            nrows, ncols = ndvi_var.shape
            lat_arr = np.linspace(ul_lat, lr_lat, nrows)
            lon_arr = np.linspace(ul_lon, lr_lon, ncols)

            # Read entire array
            # MODIS NDVI HDF4: values stored as integer * scale_factor^2
            # scale_factor=10000 but netCDF4 doesn't auto-scale correctly for HDF4
            # Actual NDVI = raw_value / 100000000
            ndvi_data = ndvi_var[:]

            for cell in cells:
                lat_idx = np.argmin(np.abs(lat_arr - cell["lat"]))
                lon_idx = np.argmin(np.abs(lon_arr - cell["lon"]))

                val = float(ndvi_data[lat_idx, lon_idx])
                # Convert from stored integer to actual NDVI
                if not np.ma.is_masked(val) and val != 0:
                    val = val / 100000000.0

                if np.ma.is_masked(val) or val < -1 or val > 1:
                    # Search nearby pixels
                    found = False
                    for dr in range(-2, 3):
                        for dc in range(-2, 3):
                            r, c = lat_idx + dr, lon_idx + dc
                            if 0 <= r < nrows and 0 <= c < ncols:
                                v = float(ndvi_data[r, c])
                                if not np.ma.is_masked(v) and -1 <= v <= 1:
                                    val = v
                                    found = True
                                    break
                        if found:
                            break
                    if not found:
                        cell_values[cell["cell_id"]].append(None)
                        continue

                if -1 <= val <= 1:
                    cell_values[cell["cell_id"]].append(round(val, 4))

            ds.close()
        except Exception as e:
            print(f"  WARNING: Error reading {os.path.basename(hdf_path)}: {e}")

    result = {}
    for cell in cells:
        vals = [v for v in cell_values[cell["cell_id"]] if v is not None]
        if vals:
            result[cell["cell_id"]] = {"ndvi": round(np.mean(vals), 4)}

    return result


def save_intermediate(data: dict, output_path: str):
    features = [{"type": "Feature", "properties": {"cell_id": cid, **vals}, "geometry": None} for cid, vals in data.items()]
    output = {"type": "FeatureCollection", "features": features}
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Download and process MODIS data")
    parser.add_argument("--city", required=True)
    parser.add_argument("--lat-min", type=float, required=True)
    parser.add_argument("--lat-max", type=float, required=True)
    parser.add_argument("--lon-min", type=float, required=True)
    parser.add_argument("--lon-max", type=float, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-date", default="2024-06-01")
    parser.add_argument("--end-date", default="2024-06-30")
    parser.add_argument("--grid", default=None, help="Path to master grid (auto-detected if not provided)")
    args = parser.parse_args()

    bounds = {"lat_min": args.lat_min, "lat_max": args.lat_max, "lon_min": args.lon_min, "lon_max": args.lon_max}
    city_dir = os.path.join(BASE_DIR, "data", args.city)
    grid_path = args.grid or os.path.join(city_dir, "processed", "master_grid.geojson")
    intermediate_dir = os.path.join(city_dir, "intermediate")

    auth = earthaccess.login(strategy="environment")
    if auth is None or not auth.authenticated:
        auth = earthaccess.login(strategy="credentials")

    cells = load_grid_cells(grid_path)
    print(f"Loaded {len(cells)} grid cells")

    # Download MODIS LST (MOD11A1 - daily 1km)
    print("\n--- Downloading MODIS LST (MOD11A1) ---")
    lst_files = download_modis_files(bounds, [], args.output_dir, "MOD11A1", args.start_date, args.end_date)
    if lst_files:
        print("Extracting LST values...")
        lst_data = extract_lst_from_hdf(lst_files, cells)
        valid = len(lst_data)
        print(f"LST: {valid}/{len(cells)} cells with data")
        save_intermediate(lst_data, os.path.join(intermediate_dir, "lst_grid.geojson"))

    # Download MODIS NDVI (MOD13A2 - 16-day 1km)
    print("\n--- Downloading MODIS NDVI (MOD13A2) ---")
    ndvi_files = download_modis_files(bounds, [], args.output_dir, "MOD13A2", args.start_date, args.end_date)
    if ndvi_files:
        print("Extracting NDVI values...")
        ndvi_data = extract_ndvi_from_hdf(ndvi_files, cells)
        valid = len(ndvi_data)
        print(f"NDVI: {valid}/{len(cells)} cells with data")
        save_intermediate(ndvi_data, os.path.join(intermediate_dir, "ndvi_grid.geojson"))

    print("\nDone!")


if __name__ == "__main__":
    main()
