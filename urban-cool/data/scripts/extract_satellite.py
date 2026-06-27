"""
Extract satellite data from downloaded GeoTIFFs to grid cells.

Reads:
- data/raw/satellite/*.tif (from AppEEARS)
- data/processed/master_grid.geojson (grid cell centroids)

Writes:
- data/intermediate/lst_grid.geojson (LST per cell)
- data/intermediate/lulc_grid.geojson (NDVI/NDWI/NDBI per cell)
"""

import json
import os
import sys
import glob
import numpy as np
import rasterio
from rasterio.transform import rowcol

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_grid_cells(grid_path: str) -> list:
    """Load grid cell centroids from master grid."""
    with open(grid_path) as f:
        grid = json.load(f)

    cells = []
    for feature in grid["features"]:
        props = feature["properties"]
        cells.append({
            "cell_id": props["cell_id"],
            "lat": props["centroid_lat"],
            "lon": props["centroid_lon"],
        })

    return cells


def extract_value_at_point(
    src: rasterio.DatasetReader,
    lat: float,
    lon: float,
) -> float:
    """
    Extract pixel value at a lat/lon point from a raster.

    Args:
        src: Open rasterio dataset
        lat: Latitude
        lon: Longitude

    Returns:
        Pixel value or None if out of bounds
    """
    try:
        # Convert lat/lon to row/col
        row, col = rowcol(src.transform, lon, lat)

        # Check bounds
        if row < 0 or row >= src.height or col < 0 or col >= src.width:
            return None

        # Read value
        value = src.read(1)[row, col]

        # Check for nodata
        if src.nodata is not None and value == src.nodata:
            return None

        if np.isnan(value) or np.isinf(value):
            return None

        return float(value)

    except Exception:
        return None


def find_tif_files(satellite_dir: str) -> dict:
    """
    Find and categorize downloaded GeoTIFFs.

    Returns dict with keys: lst, ndvi, ndwi, ndbi, sr_b4, sr_b5
    """
    tif_files = glob.glob(os.path.join(satellite_dir, "*.tif"))

    result = {
        "lst": [],
        "ndvi": [],
        "ndwi": [],
        "ndbi": [],
        "sr_b4": [],
        "sr_b5": [],
        "lst_modis": [],
    }

    for f in tif_files:
        fname = os.path.basename(f).lower()
        if "lst" in fname and "mod" in fname:
            result["lst_modis"].append(f)
        elif "lst" in fname or "lste" in fname:
            result["lst"].append(f)
        elif "ndvi" in fname:
            result["ndvi"].append(f)
        elif "ndwi" in fname:
            result["ndwi"].append(f)
        elif "ndbi" in fname:
            result["ndbi"].append(f)
        elif "sr_b4" in fname:
            result["sr_b4"].append(f)
        elif "sr_b5" in fname:
            result["sr_b5"].append(f)
        elif "sr_b" in fname:
            # Could be either B4 or B5, check band number
            if "b4" in fname:
                result["sr_b4"].append(f)
            elif "b5" in fname:
                result["sr_b5"].append(f)

    return result


def extract_lst(
    tif_path: str,
    cells: list,
    is_modis: bool = False,
) -> list:
    """
    Extract LST values from GeoTIFF to grid cells.

    Args:
        tif_path: Path to LST GeoTIFF
        cells: List of cell dicts with lat/lon
        is_modis: If True, multiply by 0.02 to convert to Kelvin

    Returns:
        List of cell records with lst_celsius
    """
    results = []

    with rasterio.open(tif_path) as src:
        for cell in cells:
            value = extract_value_at_point(src, cell["lat"], cell["lon"])

            if value is not None:
                # MODIS LST is in Kelvin * 0.02 scale factor
                if is_modis:
                    value = value * 0.02

                # Convert Kelvin to Celsius
                if value > 100:  # Likely Kelvin
                    value = value - 273.15

                results.append({
                    "cell_id": cell["cell_id"],
                    "lst_celsius": round(value, 2),
                })
            else:
                results.append({
                    "cell_id": cell["cell_id"],
                    "lst_celsius": None,
                })

    return results


def extract_ndvi_from_bands(
    sr_b4_path: str,
    sr_b5_path: str,
    cells: list,
) -> list:
    """
    Extract NDVI from Landsat 8 surface reflectance bands.

    NDVI = (NIR - Red) / (NIR + Red)
    SR_B4 = Red (650nm), SR_B5 = NIR (865nm)

    Landsat 8 ARD has scale factor 2.75e-5 and offset -0.2
    """
    results = []

    with rasterio.open(sr_b4_path) as src_b4, rasterio.open(sr_b5_path) as src_b5:
        for cell in cells:
            b4 = extract_value_at_point(src_b4, cell["lat"], cell["lon"])
            b5 = extract_value_at_point(src_b5, cell["lat"], cell["lon"])

            if b4 is not None and b5 is not None:
                # Apply scale factor and offset for Landsat 8 ARD
                b4 = b4 * 2.75e-5 - 0.2
                b5 = b5 * 2.75e-5 - 0.2

                # Compute NDVI
                denominator = b5 + b4
                if abs(denominator) > 1e-10:
                    ndvi = (b5 - b4) / denominator
                    ndvi = max(-1, min(1, ndvi))  # Clamp to valid range
                else:
                    ndvi = 0.0

                results.append({
                    "cell_id": cell["cell_id"],
                    "ndvi": round(ndvi, 4),
                    "sr_b4": round(b4, 6),
                    "sr_b5": round(b5, 6),
                })
            else:
                results.append({
                    "cell_id": cell["cell_id"],
                    "ndvi": None,
                    "sr_b4": None,
                    "sr_b5": None,
                })

    return results


def extract_indices(
    tif_path: str,
    cells: list,
    index_name: str,
) -> list:
    """
    Extract vegetation/water/built-up index from GeoTIFF.

    Args:
        tif_path: Path to index GeoTIFF
        cells: List of cell dicts
        index_name: Name of the index (ndvi, ndwi, ndbi)

    Returns:
        List of cell records
    """
    results = []

    with rasterio.open(tif_path) as src:
        for cell in cells:
            value = extract_value_at_point(src, cell["lat"], cell["lon"])

            results.append({
                "cell_id": cell["cell_id"],
                index_name: round(value, 4) if value is not None else None,
            })

    return results


def merge_results(*result_lists: list) -> dict:
    """
    Merge multiple result lists by cell_id.

    Returns:
        Dict keyed by cell_id with merged properties
    """
    merged = {}
    for result_list in result_lists:
        for record in result_list:
            cell_id = record["cell_id"]
            if cell_id not in merged:
                merged[cell_id] = {"cell_id": cell_id}
            merged[cell_id].update(record)

    return merged


def save_intermediate(records: dict, output_path: str):
    """Save merged records as intermediate GeoJSON."""
    features = []
    for cell_id, props in records.items():
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": None,  # Geometry comes from master grid
        })

    output = {"type": "FeatureCollection", "features": features}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {len(features)} records to {output_path}")


def main():
    """Extract satellite data from GeoTIFFs to grid cells."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract satellite data from GeoTIFFs")
    parser.add_argument("--satellite-dir", default="data/raw/satellite", help="Directory with GeoTIFFs")
    parser.add_argument("--grid", default="data/processed/master_grid.geojson", help="Master grid path")
    parser.add_argument("--output-dir", default="data/intermediate", help="Output directory")
    args = parser.parse_args()

    satellite_dir = os.path.join(BASE_DIR, args.satellite_dir)
    grid_path = os.path.join(BASE_DIR, args.grid)
    output_dir = os.path.join(BASE_DIR, args.output_dir)

    print("=== Satellite Data Extraction ===\n")

    # Load grid cells
    cells = load_grid_cells(grid_path)
    print(f"Loaded {len(cells)} grid cells")

    # Find GeoTIFFs
    tif_files = find_tif_files(satellite_dir)
    print(f"Found GeoTIFFs:")
    for key, files in tif_files.items():
        if files:
            print(f"  {key}: {len(files)} files")

    # Extract LST if available
    lst_records = []
    if tif_files["lst"]:
        print("\nExtracting Landsat/ECOSTRESS LST...")
        for tif in tif_files["lst"]:
            records = extract_lst(tif, cells, is_modis=False)
            lst_records.extend(records)
            valid = sum(1 for r in records if r["lst_celsius"] is not None)
            print(f"  {os.path.basename(tif)}: {valid}/{len(cells)} valid")
    elif tif_files["lst_modis"]:
        print("\nExtracting MODIS LST...")
        for tif in tif_files["lst_modis"]:
            records = extract_lst(tif, cells, is_modis=True)
            lst_records.extend(records)
            valid = sum(1 for r in records if r["lst_celsius"] is not None)
            print(f"  {os.path.basename(tif)}: {valid}/{len(cells)} valid")

    # Extract NDVI from bands if available
    ndvi_records = []
    if tif_files["sr_b4"] and tif_files["sr_b5"]:
        print("\nComputing NDVI from Landsat 8 bands...")
        for b4, b5 in zip(tif_files["sr_b4"], tif_files["sr_b5"]):
            records = extract_ndvi_from_bands(b4, b5, cells)
            ndvi_records.extend(records)
            valid = sum(1 for r in records if r["ndvi"] is not None)
            print(f"  {os.path.basename(b4)} + {os.path.basename(b5)}: {valid}/{len(cells)} valid")

    # Extract pre-computed indices
    for index_name in ["ndvi", "ndwi", "ndbi"]:
        if tif_files[index_name]:
            print(f"\nExtracting {index_name.upper()}...")
            for tif in tif_files[index_name]:
                records = extract_indices(tif, cells, index_name)
                # Merge with existing ndvi records
                for rec in records:
                    if rec.get(index_name) is not None:
                        # Find matching record
                        for ndvi_rec in ndvi_records:
                            if ndvi_rec["cell_id"] == rec["cell_id"]:
                                ndvi_rec[index_name] = rec[index_name]
                                break
                        else:
                            ndvi_records.append(rec)
                valid = sum(1 for r in records if r.get(index_name) is not None)
                print(f"  {os.path.basename(tif)}: {valid}/{len(cells)} valid")

    # Merge and save
    if lst_records:
        # Merge LST into single dict
        lst_merged = {}
        for rec in lst_records:
            cell_id = rec["cell_id"]
            if cell_id not in lst_merged or rec.get("lst_celsius") is not None:
                lst_merged[cell_id] = rec
        save_intermediate(lst_merged, os.path.join(output_dir, "lst_grid.geojson"))

    if ndvi_records:
        ndvi_merged = merge_results(ndvi_records)
        save_intermediate(ndvi_merged, os.path.join(output_dir, "lulc_grid.geojson"))

    # Summary
    print("\n=== Extraction Summary ===")
    if lst_records:
        valid_lst = sum(1 for r in lst_records if r.get("lst_celsius") is not None)
        print(f"LST: {valid_lst}/{len(cells)} cells with valid data")
    if ndvi_records:
        valid_ndvi = sum(1 for r in ndvi_records if r.get("ndvi") is not None)
        print(f"NDVI: {valid_ndvi}/{len(cells)} cells with valid data")


if __name__ == "__main__":
    main()
