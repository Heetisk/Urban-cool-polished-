"""
Feature Engineering Module.

Combines intermediate grid layers into final heat_grid.geojson.
Adds derived features (heat stress score, risk categories).

Input: Intermediate layer GeoJSONs
Output: data/processed/heat_grid.geojson
"""

import json
import os
import argparse
import math
from typing import List, Dict, Optional

# Import physics features module
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from physics_features import compute_all_physics_features


def load_intermediate(path: str) -> Dict[str, Dict]:
    """Load intermediate GeoJSON and return dict keyed by cell_id."""
    if not os.path.exists(path):
        return {}

    with open(path) as f:
        data = json.load(f)

    result = {}
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        cell_id = props.get("cell_id")
        if cell_id:
            result[cell_id] = props

    return result


def compute_heat_stress_score(props: Dict) -> Optional[float]:
    """
    Compute composite heat stress score (0-100).

    Components:
    - Temperature (40%): higher = worse
    - NDVI inverse (25%): less vegetation = worse
    - Built-up density (20%): more concrete = worse
    - Road density (15%): more asphalt = worse
    - Humidity modifier: +10% if >70%, -10% if <30%
    - Wind modifier: reduces score if >5 m/s
    """
    temp = props.get("air_temperature_celsius") or props.get("temperature")
    if temp is None:
        return None

    # Normalize components to 0-1
    temp_norm = max(0, min(1, (temp - 28) / 15))  # 28C=0, 43C=1
    ndvi = props.get("ndvi")
    ndvi_norm = 1 - (ndvi if ndvi is not None else 0.3)
    builtup = props.get("builtup_density")
    builtup_norm = builtup if builtup is not None else 0.5
    road = props.get("road_density_km_km2") or props.get("road_density")
    road_norm = min(1, (road / 80) if road is not None else 0.3)

    # Weighted composite
    score = (
        temp_norm * 40
        + ndvi_norm * 25
        + builtup_norm * 20
        + road_norm * 15
    )

    # Humidity modifier
    humidity = props.get("humidity_pct")
    if humidity is not None:
        if humidity > 70:
            score *= 1.1
        elif humidity < 30:
            score *= 0.9

    # Wind modifier
    wind = props.get("wind_speed_ms")
    if wind is not None and wind > 5:
        score *= max(0.8, 1 - wind / 20)

    return round(min(100, max(0, score)), 1)


def compute_wet_bulb(temp_c: float, rh_pct: float) -> float:
    """
    Compute wet-bulb temperature using Stull approximation.

    Stull, R. (2011). Wet-Bulb Temperature from Relative Humidity and Air Temperature.
    Journal of Applied Meteorology and Climatology, 50(11), 2267-2269.

    Args:
        temp_c: Air temperature in degrees Celsius
        rh_pct: Relative humidity in percent (0-100)

    Returns:
        Wet-bulb temperature in degrees Celsius
    """
    import math
    T = temp_c
    RH = rh_pct
    tw = (
        T * math.atan(0.151977 * math.sqrt(RH + 8.313659))
        + math.atan(T + RH)
        - math.atan(RH - 1.676331)
        + 0.00391838 * RH**1.5 * math.atan(0.023101 * RH)
        - 4.686035
    )
    return round(tw, 2)


def compute_risk_category(score: Optional[float]) -> Optional[str]:
    """Map heat stress score to risk category."""
    if score is None:
        return None
    if score < 30:
        return "low"
    elif score < 50:
        return "moderate"
    elif score < 70:
        return "high"
    else:
        return "severe"


def compute_risk_category_by_temp(temp: Optional[float], thresholds: dict = None) -> Optional[str]:
    """Map temperature directly to risk category using city-specific thresholds."""
    if temp is None:
        return None
    if thresholds is None:
        thresholds = {"severe": 43, "high": 41, "moderate": 38}
    if temp >= thresholds["severe"]:
        return "severe"
    elif temp >= thresholds["high"]:
        return "high"
    elif temp >= thresholds["moderate"]:
        return "moderate"
    else:
        return "low"


def convert_lst_to_air_temp(record: Dict, lst_mean: float = 46.27, era5_mean: float = 33.04) -> Optional[float]:
    """
    Convert Land Surface Temperature (LST) to estimated 2m air temperature.

    Uses ERA5 as absolute anchor + Landsat 8 LST for spatial variation:
    - ERA5 provides the correct regional mean air temperature
    - Landsat 8 provides high-resolution spatial patterns (hot spots, cool parks)
    - LST deviation from mean is scaled by surface type to estimate air temp variation

    Calibrated against ERA5 2m temperature for Ahmedabad:
      Mean LST = 46.27C, Mean ERA5 Ta = 33.04C

    Formula: Ta = ERA5_mean + (LST - LST_mean) * scale
      where scale depends on NDVI and urban fraction:
      - Vegetated areas: scale ~0.40 (air temp follows surface closely)
      - Impervious surfaces: scale ~0.24 (air temp less responsive to surface)

    Args:
        record: Cell record with temperature, ndvi, building_density_per_km2
        lst_mean: Mean LST across all cells (for deviation computation)
        era5_mean: Mean ERA5 2m air temperature (absolute anchor)

    Returns:
        Estimated air temperature in Celsius, or None if no LST available
    """
    lst = record.get("temperature")
    if lst is None:
        return None

    # ERA5 reference for this cell (nearly uniform ~33.0C)
    era5_ref = record.get("lst_era5_celsius")
    if era5_ref is None:
        era5_ref = era5_mean

    # Surface characteristics
    ndvi = record.get("ndvi")
    if ndvi is None:
        ndvi = 0.3

    building_density = record.get("building_density_per_km2", 0)
    urban_frac = min(1.0, building_density / 2000.0)

    # Scale factor: how much LST deviation translates to air temperature deviation
    # Vegetation (NDVI): higher NDVI -> air follows surface more (scale increases)
    # Urban fraction: more impervious -> air less responsive to surface (scale decreases)
    ndvi_factor = 0.12 * ndvi           # +0.036 at ndvi=0.3, +0.096 at ndvi=0.8
    urban_factor = -0.08 * urban_frac   # -0.04 at full urban
    scale = 0.28 + ndvi_factor + urban_factor
    scale = max(0.20, min(0.45, scale))

    # LST deviation from spatial mean
    lst_dev = lst - lst_mean

    # Air temperature = ERA5 anchor + scaled LST deviation
    ta_est = era5_mean + lst_dev * scale

    # Clamp to physically reasonable range
    ta_min = max(28.0, era5_ref - 3.0)
    ta_max = min(45.0, era5_ref + 10.0)
    ta_est = max(ta_min, min(ta_max, ta_est))

    return round(ta_est, 2)


def merge_layers(
    grid_path: str,
    era5_path: str = None,
    osm_path: str = None,
    lst_path: str = None,
    lulc_path: str = None,
    cpcb_path: str = None,
    ndvi_path: str = None,
    lst_landsat8_path: str = None,
    ecostress_path: str = None,
) -> List[Dict]:
    """
    Merge all intermediate layers into a single record per cell.

    Priority for temperature: Landsat 8 LST > MODIS LST > ERA5+spatial model
    Priority for NDVI: Sentinel-2 (GEE) > MODIS > OSM > synthetic

    Args:
        grid_path: master grid GeoJSON
        era5_path: ERA5 intermediate layer
        osm_path: OSM intermediate layer
        lst_path: MODIS LST intermediate (satellite land surface temperature)
        lulc_path: Sentinel-2 LULC intermediate (optional)
        cpcb_path: CPCB AQI data (optional)
        ndvi_path: MODIS NDVI intermediate (satellite vegetation index)
        lst_landsat8_path: Landsat 8 LST intermediate (optional, higher resolution)

    Returns:
        List of enriched cell records
    """
    with open(grid_path) as f:
        grid = json.load(f)

    era5 = load_intermediate(era5_path) if era5_path else {}
    osm = load_intermediate(osm_path) if osm_path else {}
    lst = load_intermediate(lst_path) if lst_path else {}
    lulc = load_intermediate(lulc_path) if lulc_path else {}
    ndvi_sat = load_intermediate(ndvi_path) if ndvi_path else {}
    lst_landsat8 = load_intermediate(lst_landsat8_path) if lst_landsat8_path else {}
    ecostress = load_intermediate(ecostress_path) if ecostress_path else {}

    cpcb_data = {}
    if cpcb_path and os.path.exists(cpcb_path):
        with open(cpcb_path) as f:
            cpcb_list = json.load(f)
        if isinstance(cpcb_list, dict):
            cpcb_data = cpcb_list
        else:
            for reading in cpcb_list:
                station = reading.get("station", "Unknown")
                cpcb_data[station] = reading

    merged = []
    for feature in grid["features"]:
        props = feature["properties"]
        cell_id = props["cell_id"]

        record = {
            "cell_id": cell_id,
            "centroid_lat": props["centroid_lat"],
            "centroid_lon": props["centroid_lon"],
        }

        if cell_id in era5:
            e = era5[cell_id]
            record["lst_era5_celsius"] = e.get("lst_era5_celsius")
            record["humidity_pct"] = e.get("humidity_pct")
            record["wind_speed_ms"] = e.get("wind_speed_ms")
            record["solar_wm2"] = e.get("solar_wm2")

        if cell_id in osm:
            o = osm[cell_id]
            record["road_length_km"] = o.get("road_length_km")
            record["road_density_km_km2"] = o.get("road_density_km_km2")
            record["building_count"] = o.get("building_count")
            record["building_density_per_km2"] = o.get("building_density_per_km2")
            record["builtup_density"] = o.get("builtup_density")
            record["distance_water_m"] = o.get("distance_water_m")
            osm_ndvi = o.get("ndvi")

        # === Landsat 8 LST (30m, highest resolution) ===
        if cell_id in lst_landsat8:
            record["lst_landsat8_celsius"] = lst_landsat8[cell_id].get("lst_celsius")

        # === ECOSTRESS LST (70m, validation) ===
        if cell_id in ecostress:
            record["lst_ecostress_celsius"] = ecostress[cell_id].get("lst_celsius")

        # === MODIS LST (1km) ===
        if cell_id in lst:
            record["lst_satellite_celsius"] = lst[cell_id].get("lst_celsius")

        # === MODIS NDVI (1km) ===
        if cell_id in ndvi_sat:
            record["ndvi_satellite"] = ndvi_sat[cell_id].get("ndvi")

        # === Sentinel-2 LULC (10m) ===
        if cell_id in lulc:
            s = lulc[cell_id]
            record["ndwi"] = s.get("ndwi")
            record["ndbi"] = s.get("ndbi")
            if s.get("ndvi") is not None:
                record["ndvi_sentinel2"] = s.get("ndvi")

        # === CPCB: nearest station AQI merge ===
        if cpcb_data:
            best_station = None
            best_dist = float("inf")
            cell_lat = record["centroid_lat"]
            cell_lon = record["centroid_lon"]
            for station_name, reading in cpcb_data.items():
                s_lat = reading.get("latitude")
                s_lon = reading.get("longitude")
                if s_lat is not None and s_lon is not None:
                    try:
                        s_lat = float(s_lat)
                        s_lon = float(s_lon)
                    except (ValueError, TypeError):
                        continue
                    dist = ((cell_lat - s_lat) ** 2 + (cell_lon - s_lon) ** 2) ** 0.5
                    if dist < best_dist:
                        best_dist = dist
                        best_station = station_name
            if best_station and best_dist < 0.5:
                cpcb = cpcb_data[best_station]
                pollutants = cpcb.get("pollutants", {})
                record["aqi"] = cpcb.get("aqi")
                record["pm25"] = pollutants.get("PM2.5", {}).get("avg")
                record["pm10"] = pollutants.get("PM10", {}).get("avg")
                record["cpcb_station"] = best_station

        # === TEMPERATURE: Landsat 8 > MODIS > ERA5+model ===
        landsat8_lst = record.get("lst_landsat8_celsius")
        modis_lst = record.get("lst_satellite_celsius")
        if landsat8_lst is not None:
            record["temperature"] = round(landsat8_lst, 2)
            record["temperature_source"] = "landsat8_satellite"
        elif modis_lst is not None:
            record["temperature"] = round(modis_lst, 2)
            record["temperature_source"] = "satellite"
        else:
            era5_temp = record.get("lst_era5_celsius")
            if era5_temp is not None:
                builtup = record.get("building_density_per_km2", 0)
                builtup_norm = min(1, builtup / 2000)
                builtup_effect = builtup_norm * 3.0
                road = record.get("road_density_km_km2", 0)
                road_norm = min(1, road / 60)
                road_effect = road_norm * 2.0
                ndvi_val = record.get("ndvi_satellite") or record.get("ndvi")
                if ndvi_val is None:
                    ndvi_val = max(0.1, 0.7 - builtup_norm * 0.5)
                ndvi_effect = -(1 - ndvi_val) * 3.0
                record["temperature"] = round(era5_temp + builtup_effect + road_effect + ndvi_effect, 2)
                record["temperature_source"] = "era5_model"
            else:
                record["temperature"] = None
                record["temperature_source"] = "none"

        # === NDVI: Sentinel-2 (GEE) > MODIS (GEE) > OSM > synthetic ===
        sent2_ndvi = record.get("ndvi_sentinel2")
        modis_ndvi = record.get("ndvi_satellite")
        osm_ndvi_val = record.get("ndvi")
        if sent2_ndvi is not None:
            record["ndvi"] = sent2_ndvi
            record["ndvi_source"] = "sentinel2_satellite"
        elif modis_ndvi is not None:
            record["ndvi"] = modis_ndvi
            record["ndvi_source"] = "modis_satellite"
        elif osm_ndvi_val is not None:
            record["ndvi"] = osm_ndvi_val
            record["ndvi_source"] = "osm_spatial"
        else:
            builtup = record.get("building_density_per_km2", 0)
            builtup_norm = min(1, builtup / 2000)
            synthetic_ndvi = max(0.1, 0.7 - builtup_norm * 0.5)
            record["ndvi"] = round(synthetic_ndvi, 4)
            record["ndvi_source"] = "synthetic"

        merged.append(record)

    # Compute per-city LST and ERA5 means for air temperature conversion
    lst_vals = [r["temperature"] for r in merged if r.get("temperature") is not None]
    era5_vals = [r["lst_era5_celsius"] for r in merged if r.get("lst_era5_celsius") is not None]
    lst_mean = sum(lst_vals) / len(lst_vals) if lst_vals else 46.27
    era5_mean = sum(era5_vals) / len(era5_vals) if era5_vals else 33.04

    # Second pass: convert LST to estimated air temperature
    for record in merged:
        record["air_temperature_celsius"] = convert_lst_to_air_temp(record, lst_mean, era5_mean)

    return merged


def add_derived_features(records: List[Dict], city_config: dict = None) -> List[Dict]:
    """Add computed features to each record."""
    thresholds = city_config.get("risk_thresholds", {"severe": 40, "high": 38, "moderate": 35}) if city_config else {"severe": 40, "high": 38, "moderate": 35}
    rural_temp = city_config.get("rural_baseline_temp", 32.0) if city_config else 32.0
    for record in records:
        record["heat_stress_score"] = compute_heat_stress_score(record)
        air_temp = record.get("air_temperature_celsius") or record.get("temperature")
        record["heat_risk_category"] = compute_risk_category_by_temp(air_temp, thresholds)

        # NDVI inverse (impervious surface proxy)
        ndvi = record.get("ndvi")
        record["ndvi_inverse"] = round(1 - ndvi, 4) if ndvi is not None else None

        # Add physics-based features
        physics_features = compute_all_physics_features(record, rural_temp)
        record.update(physics_features)

        # Wet-bulb temperature (Stull approximation) - uses air temperature, not LST
        air_temp = record.get("air_temperature_celsius") or record.get("temperature")
        humidity = record.get("humidity_pct")
        if air_temp is not None and humidity is not None:
            record["wet_bulb_celsius"] = compute_wet_bulb(air_temp, humidity)
        else:
            record["wet_bulb_celsius"] = None

        # Data quality score (0-100)
        score = 0
        if record.get("lst_landsat8_celsius") is not None:
            score += 35
        elif record.get("lst_satellite_celsius") is not None:
            score += 30
        if record.get("ndvi_sentinel2") is not None or record.get("ndvi_satellite") is not None:
            score += 20
        if record.get("solar_wm2") is not None:
            score += 25
        if record.get("road_density_km_km2") is not None:
            score += 25
        record["data_quality"] = score

    return records


def save_output(records: List[Dict], grid_path: str, output_path: str):
    """Save final heat_grid.geojson."""
    with open(grid_path) as f:
        grid = json.load(f)

    geom_map = {
        feat["properties"]["cell_id"]: feat["geometry"]
        for feat in grid["features"]
    }

    features = []
    for record in records:
        cell_id = record["cell_id"]
        geometry = geom_map.get(cell_id)

        props = {k: v for k, v in record.items() if v is not None}

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": props,
        })

    output = {"type": "FeatureCollection", "features": features}

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    return output


if __name__ == "__main__":
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from config.config_loader import get_city_config

    parser = argparse.ArgumentParser(description="Feature Engineering Module")
    parser.add_argument("--city", default="ahmedabad")
    parser.add_argument("--grid", default="data/processed/master_grid.geojson")
    parser.add_argument("--era5", default="data/intermediate/era5_grid.geojson")
    parser.add_argument("--osm", default="data/intermediate/osm_grid.geojson")
    parser.add_argument("--lst", default=None, help="MODIS LST intermediate GeoJSON")
    parser.add_argument("--lst-landsat8", default=None, help="Landsat 8 LST intermediate GeoJSON (30m)")
    parser.add_argument("--ecostress", default=None, help="ECOSTRESS LST intermediate GeoJSON (70m)")
    parser.add_argument("--lulc", default=None)
    parser.add_argument("--cpcb", default=None, help="CPCB AQI data JSON")
    parser.add_argument("--ndvi", default=None, help="MODIS NDVI intermediate GeoJSON")
    parser.add_argument("--output", default="data/processed/heat_grid.geojson")
    args = parser.parse_args()

    city_config = get_city_config(args.city)

    print("=== Feature Engineering ===")
    print(f"  City: {city_config['name']}")
    print(f"  Landsat 8 LST: {args.lst_landsat8 or 'none'}")
    print(f"  ECOSTRESS LST: {args.ecostress or 'none'}")
    print(f"  MODIS LST: {args.lst or 'none'}")
    print(f"  MODIS NDVI: {args.ndvi or 'none (using synthetic)'}")

    records = merge_layers(args.grid, args.era5, args.osm, args.lst, args.lulc, args.cpcb, args.ndvi, args.lst_landsat8, args.ecostress)
    print(f"Merged {len(records)} cells")

    records = add_derived_features(records, city_config)
    print(f"Computed derived features (including physics-based)")

    output = save_output(records, args.grid, args.output)

    # Summary
    temps = [r["temperature"] for r in records if r.get("temperature")]
    scores = [r["heat_stress_score"] for r in records if r.get("heat_stress_score") is not None]
    cats = {}
    for r in records:
        cat = r.get("heat_risk_category")
        if cat:
            cats[cat] = cats.get(cat, 0) + 1

    print(f"\nOutput: {args.output}")
    print(f"Cells: {len(records)}")
    if temps:
        print(f"Temperature: {min(temps):.1f}C - {max(temps):.1f}C")
    if scores:
        print(f"Heat stress: {min(scores):.1f} - {max(scores):.1f}")
    print(f"Risk categories: {cats}")

    # Data source summary
    temp_sources = {}
    ndvi_sources = {}
    for r in records:
        ts = r.get("temperature_source", "unknown")
        temp_sources[ts] = temp_sources.get(ts, 0) + 1
        ns = r.get("ndvi_source", "unknown")
        ndvi_sources[ns] = ndvi_sources.get(ns, 0) + 1
    print(f"\nTemperature sources: {temp_sources}")
    print(f"NDVI sources: {ndvi_sources}")

    landsat8_count = sum(1 for r in records if r.get("lst_landsat8_celsius") is not None)
    ecostress_count = sum(1 for r in records if r.get("lst_ecostress_celsius") is not None)
    sent2_count = sum(1 for r in records if r.get("ndvi_sentinel2") is not None)
    cpcb_count = sum(1 for r in records if r.get("aqi") is not None)
    wetbulb_count = sum(1 for r in records if r.get("wet_bulb_celsius") is not None)
    print(f"Landsat 8 LST cells: {landsat8_count}/{len(records)}")
    print(f"ECOSTRESS LST cells: {ecostress_count}/{len(records)}")
    print(f"Sentinel-2 NDVI cells: {sent2_count}/{len(records)}")
    print(f"CPCB AQI cells: {cpcb_count}/{len(records)}")
    print(f"Wet-bulb temp cells: {wetbulb_count}/{len(records)}")
