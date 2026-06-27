"""
Unified Pipeline - Fetch real data from APIs and build UrbanCool model for any city.

Usage:
    python data/scripts/unified_pipeline.py --city gandhinagar
    python data/scripts/unified_pipeline.py --city ahmedabad

Steps:
    1. Generate grid from city config bounds
    2. Fetch ERA5 weather data from CDS API
    3. Fetch OSM roads/buildings from Overpass API
    3b. Fetch CPCB AQI data (optional)
    4. Download MODIS LST + NDVI from NASA Earthdata
    4b. Fetch Landsat 8 LST via GEE (optional)
    4c. Fetch Sentinel-2 LULC via GEE (optional)
    5. Process ERA5 NetCDF -> grid intermediate
    6. Process OSM roads/buildings -> grid intermediate
    7. Feature engineering (merge all layers)
    8. Train model + SHAP explainer
"""

import argparse
import json
import os
import sys
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from config.config_loader import get_city_config, get_available_cities


def run_step(name, cmd, cwd=None):
    """Run a pipeline step and report success/failure."""
    print(f"\n{'='*60}")
    print(f"  STEP: {name}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=cwd or BASE_DIR, capture_output=False)
    if result.returncode != 0:
        print(f"  WARNING: Step '{name}' exited with code {result.returncode}")
        return False
    return True


def step1_generate_grid(city, config):
    """Generate grid cells from city bounds."""
    output_dir = os.path.join(BASE_DIR, "data", city, "processed")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "master_grid.geojson")

    cmd = [
        sys.executable, "data/scripts/master_grid.py",
        "--city", city,
        "--grid-size", str(config.get("grid_size_m", 500)),
        "--output", output_path,
    ]
    return run_step("Generate Grid", cmd)


def step2_fetch_era5(city, config):
    """Fetch ERA5 weather data from CDS API."""
    bounds = config["bounds"]
    output_dir = os.path.join(BASE_DIR, "data", city, "raw", "era5")

    cmd = [
        sys.executable, "data/scripts/fetchers/fetch_era5.py",
        "--city", city,
        "--lat-min", str(bounds["lat_min"]),
        "--lat-max", str(bounds["lat_max"]),
        "--lon-min", str(bounds["lon_min"]),
        "--lon-max", str(bounds["lon_max"]),
        "--output-dir", output_dir,
    ]
    return run_step("Fetch ERA5 Weather Data", cmd)


def step3_fetch_osm(city, config):
    """Fetch OSM roads and buildings from Overpass API."""
    center = config["center"]
    lat_span = (config["bounds"]["lat_max"] - config["bounds"]["lat_min"]) / 2
    lon_span = (config["bounds"]["lon_max"] - config["bounds"]["lon_min"]) / 2
    radius_m = int(max(lat_span, lon_span) * 111320 * 1.2)

    output_dir = os.path.join(BASE_DIR, "data", city, "raw", "osm")

    cmd = [
        sys.executable, "data/scripts/fetchers/fetch_osm.py",
        "--city", city,
        "--center-lat", str(center[0]),
        "--center-lon", str(center[1]),
        "--radius", str(radius_m),
        "--output-dir", output_dir,
    ]
    return run_step("Fetch OSM Roads/Buildings", cmd)


def step4_fetch_modis(city, config):
    """Download MODIS LST + NDVI from NASA Earthdata."""
    bounds = config["bounds"]
    output_dir = os.path.join(BASE_DIR, "data", city, "raw", "satellite")
    grid_path = os.path.join(BASE_DIR, "data", city, "processed", "master_grid.geojson")

    cmd = [
        sys.executable, "data/scripts/process_modis.py",
        "--city", city,
        "--lat-min", str(bounds["lat_min"]),
        "--lat-max", str(bounds["lat_max"]),
        "--lon-min", str(bounds["lon_min"]),
        "--lon-max", str(bounds["lon_max"]),
        "--output-dir", output_dir,
        "--grid", grid_path,
    ]
    return run_step("Download MODIS LST + NDVI", cmd)


def step4b_fetch_landsat8(city, config):
    """Fetch Landsat 8 LST via Google Earth Engine."""
    grid_path = os.path.join(BASE_DIR, "data", city, "processed", "master_grid.geojson")
    output_path = os.path.join(BASE_DIR, "data", city, "intermediate", "lst_landsat8_grid.geojson")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    project = config.get("gee_project", None)
    cmd = [
        sys.executable, "data/scripts/fetch_lst_landsat8.py",
        "--grid", grid_path,
        "--output", output_path,
        "--city", city,
        "--year", "2024",
    ]
    if project:
        cmd.extend(["--project", project])
    return run_step("Fetch Landsat 8 LST (GEE)", cmd)


def step4c_fetch_sentinel2(city, config):
    """Fetch Sentinel-2 LULC (NDVI/NDWI/NDBI) via Google Earth Engine."""
    grid_path = os.path.join(BASE_DIR, "data", city, "processed", "master_grid.geojson")
    output_path = os.path.join(BASE_DIR, "data", city, "intermediate", "lulc_sentinel2_grid.geojson")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    project = config.get("gee_project", None)
    cmd = [
        sys.executable, "data/scripts/fetch_lulc_sentinel2.py",
        "--grid", grid_path,
        "--output", output_path,
        "--city", city,
        "--year", "2024",
    ]
    if project:
        cmd.extend(["--project", project])
    return run_step("Fetch Sentinel-2 LULC (GEE)", cmd)


def step3b_fetch_cpcb(city, config):
    """Fetch CPCB air quality data."""
    output_path = os.path.join(BASE_DIR, "data", city, "intermediate", "cpcb_aqi.json")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    api_key = config.get("cpcb_api_key")
    if not api_key:
        print("  WARNING: No CPCB API key in city config, skipping")
        return True

    cmd = [
        sys.executable, "data/scripts/fetchers/fetch_cpcb.py",
        "--api-key", api_key,
        "--city", city,
        "--output", output_path,
    ]
    return run_step("Fetch CPCB AQI Data", cmd)


def step5_process_era5(city, config):
    """Process ERA5 NetCDF into grid intermediate."""
    city_dir = os.path.join(BASE_DIR, "data", city)
    raw_dir = os.path.join(city_dir, "raw", "era5")
    grid_path = os.path.join(city_dir, "processed", "master_grid.geojson")
    output_path = os.path.join(city_dir, "intermediate", "era5_grid.geojson")

    nc_file = None
    if os.path.exists(raw_dir):
        for f in os.listdir(raw_dir):
            if f.endswith(".nc"):
                nc_file = os.path.join(raw_dir, f)
                break

    if not nc_file:
        print("  WARNING: No ERA5 NetCDF found, skipping")
        return True

    cmd = [
        sys.executable, "data/scripts/process_era5.py",
        "--city", city,
        "--nc", nc_file,
        "--grid", grid_path,
        "--output", output_path,
    ]
    return run_step("Process ERA5 -> Grid", cmd)


def step6_process_osm(city, config):
    """Process OSM roads/buildings into grid intermediate."""
    city_dir = os.path.join(BASE_DIR, "data", city)
    raw_dir = os.path.join(city_dir, "raw", "osm")
    grid_path = os.path.join(city_dir, "processed", "master_grid.geojson")
    output_path = os.path.join(city_dir, "intermediate", "osm_grid.geojson")

    roads_file = None
    buildings_file = None
    if os.path.exists(raw_dir):
        for f in os.listdir(raw_dir):
            if "roads" in f and f.endswith(".geojson"):
                roads_file = os.path.join(raw_dir, f)
            if "buildings" in f and f.endswith(".geojson"):
                buildings_file = os.path.join(raw_dir, f)

    if not roads_file or not buildings_file:
        print("  WARNING: OSM roads/buildings not found, skipping")
        return True

    water_bodies = config.get("water_bodies", [])
    water_args = []
    for wb in water_bodies:
        if isinstance(wb, dict):
            water_args.extend([str(wb["lat"]), str(wb["lon"])])
        else:
            water_args.extend([str(wb[0]), str(wb[1])])

    cmd = [
        sys.executable, "data/scripts/process_osm.py",
        "--city", city,
        "--grid", grid_path,
        "--roads", roads_file,
        "--buildings", buildings_file,
        "--output", output_path,
    ]
    if water_args:
        cmd.extend(["--water-bodies"] + water_args)

    return run_step("Process OSM -> Grid", cmd)


def step7_feature_engineering(city, config):
    """Run feature engineering to merge all data layers."""
    city_dir = os.path.join(BASE_DIR, "data", city)
    processed_dir = os.path.join(city_dir, "processed")
    intermediate_dir = os.path.join(city_dir, "intermediate")

    grid_path = os.path.join(processed_dir, "master_grid.geojson")
    era5_path = os.path.join(intermediate_dir, "era5_grid.geojson")
    osm_path = os.path.join(intermediate_dir, "osm_grid.geojson")
    lst_path = os.path.join(intermediate_dir, "lst_grid.geojson")
    ndvi_path = os.path.join(intermediate_dir, "ndvi_grid.geojson")
    lst_landsat8_path = os.path.join(intermediate_dir, "lst_landsat8_grid.geojson")
    lulc_sentinel2_path = os.path.join(intermediate_dir, "lulc_sentinel2_grid.geojson")
    cpcb_path = os.path.join(intermediate_dir, "cpcb_aqi.json")

    cmd = [
        sys.executable, "data/scripts/feature_engineering.py",
        "--city", city,
        "--grid", grid_path,
        "--output", os.path.join(processed_dir, "heat_grid.geojson"),
    ]

    if os.path.exists(era5_path):
        cmd.extend(["--era5", era5_path])
    if os.path.exists(osm_path):
        cmd.extend(["--osm", osm_path])
    if os.path.exists(lst_path):
        cmd.extend(["--lst", lst_path])
    if os.path.exists(ndvi_path):
        cmd.extend(["--ndvi", ndvi_path])
    if os.path.exists(lst_landsat8_path):
        cmd.extend(["--lst-landsat8", lst_landsat8_path])
    if os.path.exists(lulc_sentinel2_path):
        cmd.extend(["--lulc", lulc_sentinel2_path])
    if os.path.exists(cpcb_path):
        cmd.extend(["--cpcb", cpcb_path])

    return run_step("Feature Engineering", cmd)


def step8_train_model(city, config):
    """Train Ridge Regression model and SHAP explainer."""
    cmd = [
        sys.executable, "data/scripts/train_temperature_model.py",
        "--city", city,
    ]
    return run_step("Train Model + SHAP", cmd)


def main():
    parser = argparse.ArgumentParser(description="Unified UrbanCool Pipeline")
    parser.add_argument("--city", required=True, choices=get_available_cities(),
                        help="City key from config/cities.json")
    parser.add_argument("--skip-grid", action="store_true")
    parser.add_argument("--skip-era5", action="store_true")
    parser.add_argument("--skip-osm", action="store_true")
    parser.add_argument("--skip-modis", action="store_true")
    parser.add_argument("--skip-landsat8", action="store_true")
    parser.add_argument("--skip-sentinel2", action="store_true")
    parser.add_argument("--skip-cpcb", action="store_true")
    parser.add_argument("--skip-process", action="store_true", help="Skip all processing steps")
    parser.add_argument("--skip-features", action="store_true")
    parser.add_argument("--skip-train", action="store_true")
    args = parser.parse_args()

    config = get_city_config(args.city)
    print(f"{'='*60}")
    print(f"  UrbanCool Pipeline: {config['name']}")
    print(f"  Bounds: {config['bounds']}")
    print(f"  Grid size: {config.get('grid_size_m', 500)}m")
    print(f"{'='*60}")

    start = time.time()
    steps = [
        ("Grid", not args.skip_grid, step1_generate_grid),
        ("ERA5 Download", not args.skip_era5, step2_fetch_era5),
        ("OSM Download", not args.skip_osm, step3_fetch_osm),
        ("CPCB Download", not args.skip_cpcb, step3b_fetch_cpcb),
        ("MODIS Download", not args.skip_modis, step4_fetch_modis),
        ("Landsat 8 Download", not args.skip_landsat8, step4b_fetch_landsat8),
        ("Sentinel-2 Download", not args.skip_sentinel2, step4c_fetch_sentinel2),
        ("ERA5 Process", not args.skip_process, step5_process_era5),
        ("OSM Process", not args.skip_process, step6_process_osm),
        ("Feature Engineering", not args.skip_features, step7_feature_engineering),
        ("Model Training", not args.skip_train, step8_train_model),
    ]

    results = {}
    for name, should_run, step_func in steps:
        if should_run:
            results[name] = step_func(args.city, config)
        else:
            print(f"\n  SKIP: {name}")
            results[name] = True

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE ({elapsed:.0f}s)")
    print(f"{'='*60}")
    for name, ok in results.items():
        status = "OK" if ok else "FAILED"
        print(f"  {name}: {status}")

    grid_path = os.path.join(BASE_DIR, "data", args.city, "processed", "heat_grid.geojson")
    if os.path.exists(grid_path):
        with open(grid_path) as f:
            data = json.load(f)
        print(f"\n  Output: {grid_path}")
        print(f"  Cells: {len(data['features'])}")

    # Generate data metadata
    try:
        from generate_data_metadata import generate_metadata
        meta = generate_metadata(args.city, os.path.join("data", args.city))
        meta_path = os.path.join("data", args.city, "processed", "data_metadata.json")
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"\n  Data metadata: {meta_path}")
        for s in meta.get("sources", []):
            print(f"    {s}")
    except Exception as e:
        print(f"\n  Warning: Could not generate data metadata: {e}")


if __name__ == "__main__":
    main()
