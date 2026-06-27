"""
UrbanCool AI - Main Pipeline Orchestrator.

Runs the full pipeline:
1. Generate master grid
2. Fetch raw data (ERA5, OSM, Landsat, Sentinel)
3. Aggregate to grid
4. Feature engineering
5. Output heat_grid.geojson

Usage:
    python data/scripts/pipeline.py --city ahmedabad
    python data/scripts/pipeline.py --city ahmedabad --skip-fetch
"""

import json
import os
import sys
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_step(name: str, func, *args, **kwargs):
    """Run a pipeline step with timing."""
    print(f"\n{'='*50}")
    print(f"Step: {name}")
    print(f"{'='*50}")
    start = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - start
    print(f"Completed in {elapsed:.1f}s")
    return result


def main():
    parser = argparse.ArgumentParser(description="UrbanCool AI Pipeline")
    parser.add_argument("--city", default="ahmedabad", help="City name")
    parser.add_argument("--grid-size", type=int, default=500, help="Grid cell size in meters")
    parser.add_argument("--year", type=int, default=2024, help="Data year")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip data fetching (use existing raw)")
    parser.add_argument("--data-dir", default="data", help="Base data directory")
    args = parser.parse_args()

    base_dir = args.data_dir
    raw_dir = os.path.join(base_dir, "raw")
    intermediate_dir = os.path.join(base_dir, "intermediate")
    processed_dir = os.path.join(base_dir, "processed")

    print(f"UrbanCool AI Pipeline")
    print(f"City: {args.city}")
    print(f"Grid: {args.grid_size}m")
    print(f"Year: {args.year}")

    # Step 1: Generate master grid
    from master_grid import generate_master_grid
    grid = run_step(
        "Generate Master Grid",
        generate_master_grid,
        args.city, args.grid_size,
    )
    grid_path = os.path.join(processed_dir, "master_grid.geojson")
    os.makedirs(processed_dir, exist_ok=True)
    with open(grid_path, "w") as f:
        json.dump(grid, f, indent=2)
    print(f"  Saved: {grid_path}")

    cells = grid["features"]
    print(f"  Grid: {len(cells)} cells")

    # Step 2: Fetch raw data
    if not args.skip_fetch:
        # ERA5
        from fetchers.fetch_era5 import download_era5, save_metadata
        era5_bounds = {
            "lat_min": 23.0, "lat_max": 23.15,
            "lon_min": 72.5, "lon_max": 72.68,
        }
        era5_nc = run_step(
            "Fetch ERA5 Weather",
            download_era5,
            era5_bounds, args.city, args.year,
            os.path.join(raw_dir, "era5"),
        )

        # OSM
        from fetchers.fetch_osm import download_city_osm, save_raw_osm, save_metadata as save_osm_meta
        center_lat = sum(f["properties"]["centroid_lat"] for f in cells) / len(cells)
        center_lon = sum(f["properties"]["centroid_lon"] for f in cells) / len(cells)
        roads, buildings = run_step(
            "Fetch OSM Data",
            download_city_osm,
            center_lat, center_lon, 15000,
        )
        osm_dir = os.path.join(raw_dir, "osm")
        roads_path, buildings_path = save_raw_osm(roads, buildings, args.city, osm_dir)
        save_osm_meta(args.city, len(roads), len(buildings), {"lat": center_lat, "lon": center_lon}, 15000, osm_dir)

        print(f"  ERA5: {era5_nc}")
        print(f"  OSM Roads: {roads_path}")
        print(f"  OSM Buildings: {buildings_path}")
    else:
        print("\nSkipping data fetch (using existing raw)")
        era5_nc = os.path.join(raw_dir, "era5", f"era5_{args.city}_{args.year}.nc")
        roads_path = os.path.join(raw_dir, "osm", f"osm_{args.city}_roads.geojson")
        buildings_path = os.path.join(raw_dir, "osm", f"osm_{args.city}_buildings.geojson")

    # Step 3: Aggregate to grid
    from aggregate_to_grid import (
        load_master_grid, aggregate_era5_to_grid,
        aggregate_osm_to_grid, save_intermediate,
    )

    grid_cells = run_step("Load Master Grid", load_master_grid, grid_path)

    # ERA5 aggregation
    if os.path.exists(era5_nc):
        era5_data = run_step("Aggregate ERA5 to Grid", aggregate_era5_to_grid, era5_nc, grid_cells)
        era5_grid_path = save_intermediate(era5_data, "era5", intermediate_dir)
        valid = sum(1 for d in era5_data if d.get("lst_era5_celsius") is not None)
        print(f"  {valid}/{len(grid_cells)} cells with ERA5 data")
    else:
        print(f"\n  ERA5 not found: {era5_nc}")
        era5_grid_path = None

    # OSM aggregation
    if os.path.exists(roads_path):
        osm_data = run_step("Aggregate OSM to Grid", aggregate_osm_to_grid, roads_path, buildings_path, grid_cells)
        osm_grid_path = save_intermediate(osm_data, "osm", intermediate_dir)
        print(f"  {len(grid_cells)} cells aggregated")
    else:
        print(f"\n  OSM not found: {roads_path}")
        osm_grid_path = None

    # Step 4: Feature engineering
    from feature_engineering import merge_layers, add_derived_features, save_output

    records = run_step(
        "Feature Engineering",
        merge_layers,
        grid_path, era5_grid_path, osm_grid_path,
    )

    records = add_derived_features(records)

    output_path = os.path.join(processed_dir, "heat_grid.geojson")
    output = save_output(records, grid_path, output_path)

    # Final summary
    features = output["features"]
    temps = [f["properties"].get("temperature") for f in features if f["properties"].get("temperature")]
    scores = [f["properties"].get("heat_stress_score") for f in features if f["properties"].get("heat_stress_score") is not None]
    cats = {}
    for f in features:
        cat = f["properties"].get("heat_risk_category")
        if cat:
            cats[cat] = cats.get(cat, 0) + 1

    print(f"\n{'='*50}")
    print(f"Pipeline Complete!")
    print(f"{'='*50}")
    print(f"Output: {output_path}")
    print(f"Cells: {len(features)}")
    if temps:
        print(f"Temperature: {min(temps):.1f}C - {max(temps):.1f}C")
    if scores:
        print(f"Heat stress: {min(scores):.1f} - {max(scores):.1f}")
    print(f"Risk categories: {cats}")


if __name__ == "__main__":
    main()
