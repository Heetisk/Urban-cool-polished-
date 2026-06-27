"""
Process ERA5 NetCDF into grid intermediate layer.

Reads:
- data/{city}/raw/era5/era5_{city}_*.nc (NetCDF from CDS API)
- data/{city}/processed/master_grid.geojson

Writes:
- data/{city}/intermediate/era5_grid.geojson

Output format per cell:
{
    "cell_id": "AHM_0000_0000",
    "lst_era5_celsius": 33.03,
    "humidity_pct": 45.67,
    "wind_speed_ms": 2.01,
    "solar_wm2": 233.59
}
"""

import json
import os
import sys
import argparse
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_grid_cells(grid_path: str) -> list:
    """Load grid cell centroids from master grid."""
    with open(grid_path) as f:
        grid = json.load(f)
    return [
        {"cell_id": f["properties"]["cell_id"], "lat": f["properties"]["centroid_lat"], "lon": f["properties"]["centroid_lon"]}
        for f in grid["features"]
    ]


def extract_era5_at_points(nc_path: str, cells: list) -> list:
    """Extract ERA5 variables at grid cell centroids using nearest-neighbor."""
    import netCDF4 as nc

    ds = nc.Dataset(nc_path, "r")
    lats = ds.variables["latitude"][:]
    lons = ds.variables["longitude"][:]

    t2m = ds.variables["t2m"][:]
    d2m = ds.variables.get("d2m", None)
    u10 = ds.variables.get("u10", None)
    v10 = ds.variables.get("v10", None)
    ssrd = ds.variables.get("ssrd", None)

    # Compute time-mean for each grid point
    t2m_mean = np.mean(t2m, axis=0)  # shape: (n_lat, n_lon)
    d2m_mean = np.mean(d2m, axis=0) if d2m is not None else None
    u10_mean = np.mean(u10, axis=0) if u10 is not None else None
    v10_mean = np.mean(v10, axis=0) if v10 is not None else None

    # ssrd is ACCUMULATED from forecast start (J/m2), not per-timestep.
    # Must take diffs and divide by timestep interval to get W/m2.
    ssrd_mean = None
    if ssrd is not None:
        time_var = ds.variables.get("valid_time") or ds.variables.get("time")
        time_vals = np.array(time_var[:], dtype=float)
        time_diffs = np.diff(time_vals)  # seconds between timesteps

        ssrd_diffs = np.diff(ssrd, axis=0)  # per-step accumulated delta

        # For each grid point, compute per-timestep W/m2 and average valid values
        n_lat, n_lon = ssrd.shape[1], ssrd.shape[2]
        ssrd_wm2 = np.zeros((n_lat, n_lon))
        for li in range(n_lat):
            for lj in range(n_lon):
                step_radiation = ssrd_diffs[:, li, lj]
                step_seconds = time_diffs
                # Only use positive diffs with positive time intervals (skip forecast resets)
                valid = (step_radiation > 0) & (step_seconds > 0)
                if valid.any():
                    wm2_per_step = step_radiation[valid] / step_seconds[valid]
                    ssrd_wm2[li, lj] = np.mean(wm2_per_step)
                else:
                    ssrd_wm2[li, lj] = 0
        ssrd_mean = ssrd_wm2

    results = []
    for cell in cells:
        lat, lon = cell["lat"], cell["lon"]
        lat_idx = np.argmin(np.abs(lats - lat))
        lon_idx = np.argmin(np.abs(lons - lon))

        temp_k = float(t2m_mean[lat_idx, lon_idx])
        temp_c = temp_k - 273.15

        humidity = None
        if d2m_mean is not None:
            d2m_val = float(d2m_mean[lat_idx, lon_idx])
            sat_vp = 6.112 * np.exp((17.67 * (temp_k - 273.15)) / ((temp_k - 273.15) + 243.5))
            act_vp = 6.112 * np.exp((17.67 * (d2m_val - 273.15)) / ((d2m_val - 273.15) + 243.5))
            humidity = round(min(100, max(0, (act_vp / sat_vp) * 100)), 2)

        wind = None
        if u10_mean is not None and v10_mean is not None:
            u_val = float(u10_mean[lat_idx, lon_idx])
            v_val = float(v10_mean[lat_idx, lon_idx])
            wind = round(np.sqrt(u_val**2 + v_val**2), 2)

        solar = None
        if ssrd_mean is not None:
            solar = round(max(0, float(ssrd_mean[lat_idx, lon_idx])), 2)

        results.append({
            "cell_id": cell["cell_id"],
            "lst_era5_celsius": round(temp_c, 2),
            "humidity_pct": humidity,
            "wind_speed_ms": wind,
            "solar_wm2": solar,
        })

    ds.close()
    return results


def main():
    parser = argparse.ArgumentParser(description="Process ERA5 NetCDF to grid")
    parser.add_argument("--city", required=True)
    parser.add_argument("--nc", required=True, help="Path to ERA5 NetCDF file")
    parser.add_argument("--grid", required=True, help="Path to master grid GeoJSON")
    parser.add_argument("--output", required=True, help="Output intermediate GeoJSON")
    args = parser.parse_args()

    print("=== ERA5 Processing ===")
    cells = load_grid_cells(args.grid)
    print(f"Loaded {len(cells)} grid cells")

    print(f"Reading ERA5: {args.nc}")
    records = extract_era5_at_points(args.nc, cells)

    valid = sum(1 for r in records if r.get("lst_era5_celsius") is not None)
    print(f"Valid cells: {valid}/{len(cells)}")

    output = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": r, "geometry": None} for r in records]}
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
