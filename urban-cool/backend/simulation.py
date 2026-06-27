"""
Simulation Module - Spatial cooling intervention simulation.

Uses KDTree for efficient spatial neighbor lookups and Gaussian kernel
convolution to model how interventions cool neighboring cells.

Physics basis:
- Tree canopy provides shade + evapotranspiration cooling
- Cool roofs increase albedo, reducing absorbed radiation
- Green roofs add evapotranspiration + insulation
- Cooling effects spread to neighbors via air circulation
"""

import json
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial import cKDTree


_config = None


def load_config() -> Dict:
    """Load intervention coefficients from config file."""
    global _config
    if _config is None:
        # Use centralized config path
        from config.config_loader import BASE_DIR
        config_path = os.path.join(BASE_DIR, "backend", "config", "interventions.json")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Intervention config not found: {config_path}")
        with open(config_path, encoding="utf-8") as f:
            _config = json.load(f)
    return _config


def gaussian_weight(distance: float, sigma: float) -> float:
    """Gaussian kernel weight for spatial decay."""
    return math.exp(-(distance ** 2) / (2 * sigma ** 2))


def build_spatial_index(
    all_cells: Dict[str, dict],
) -> Tuple[cKDTree, List[str], np.ndarray]:
    """
    Build KDTree for efficient spatial neighbor queries.

    Returns:
        (tree, cell_ids, coords) where coords is Nx2 array of [lat, lon]
    """
    cell_ids = []
    coords = []
    for cell_id, props in all_cells.items():
        lat = props.get("centroid_lat")
        lon = props.get("centroid_lon")
        if lat is not None and lon is not None:
            cell_ids.append(cell_id)
            coords.append([lat, lon])

    coords_arr = np.array(coords)
    tree = cKDTree(coords_arr)
    return tree, cell_ids, coords_arr


def simulate_intervention(
    cell_data: dict,
    tree_cover: float = 0,
    cool_roof: float = 0,
    green_roof: float = 0,
    water_body: float = 0,
    all_cells: Optional[Dict[str, dict]] = None,
    sigma_meters: float = 750,
    spatial_index: Optional[Tuple[cKDTree, List[str], np.ndarray]] = None,
) -> dict:
    """
    Simulate temperature reduction from interventions with spatial effects.

    Uses KDTree for O(log N) neighbor queries instead of O(N) full scan.

    Args:
        cell_data: cell properties dict (must have centroid_lat, centroid_lon, temperature)
        tree_cover: percentage increase in tree cover (0-100)
        cool_roof: percentage of roofs converted to cool roofs (0-100)
        green_roof: percentage of roofs converted to green roofs (0-100)
        all_cells: dict of {cell_id: properties} for neighbor lookup (enables spatial effects)
        sigma_meters: Gaussian kernel width (750m = ~1.5 cell radius)
        spatial_index: pre-built (KDTree, cell_ids, coords) tuple for fast queries

    Returns:
        dict with before/after temps, reduction, per-intervention breakdown,
        and neighbor effects
    """
    config = load_config()
    current_temp = cell_data.get("air_temperature_celsius") or cell_data.get("temperature", 0)
    target_lat = cell_data.get("centroid_lat")
    target_lon = cell_data.get("centroid_lon")
    target_id = cell_data.get("cell_id", "unknown")

    # Compute per-intervention base cooling
    interventions = {}
    total_base_reduction = 0

    if tree_cover > 0:
        coeff = config["tree_cover"]["temp_reduction_per_percent"]
        reduction = coeff * tree_cover
        total_base_reduction += reduction
        interventions["tree_cover"] = {"percent": tree_cover, "reduction": round(reduction, 2)}

    if cool_roof > 0:
        coeff = config["cool_roof"]["temp_reduction_per_percent"]
        reduction = coeff * cool_roof
        total_base_reduction += reduction
        interventions["cool_roof"] = {"percent": cool_roof, "reduction": round(reduction, 2)}

    if green_roof > 0:
        coeff = config["green_roof"]["temp_reduction_per_percent"]
        reduction = coeff * green_roof
        total_base_reduction += reduction
        interventions["green_roof"] = {"percent": green_roof, "reduction": round(reduction, 2)}

    if water_body > 0:
        coeff = config["water_body"]["temp_reduction_per_100sqm"]
        reduction = coeff * (water_body / 100)
        total_base_reduction += reduction
        interventions["water_body"] = {"percent": water_body, "reduction": round(reduction, 2)}

    # Spatial effects on neighbors using KDTree
    neighbor_effects = []
    total_spatial_reduction = 0

    if all_cells and target_lat is not None and total_base_reduction > 0:
        # Build or use pre-built spatial index
        if spatial_index is not None:
            tree, cell_ids, coords = spatial_index
        else:
            tree, cell_ids, coords = build_spatial_index(all_cells)

        # Query all cells within sigma * 3 radius (O(log N))
        search_radius_deg = sigma_meters * 3 / 111320  # approx meters to degrees
        idxs = tree.query_ball_point([target_lat, target_lon], search_radius_deg)

        for idx in idxs:
            nid = cell_ids[idx]
            if nid == target_id:
                continue

            nprops = all_cells[nid]
            n_lat = coords[idx][0]
            n_lon = coords[idx][1]

            # Convert degree distance to meters (accurate at latitude)
            # Use mean latitude for cosine correction
            mean_lat = (target_lat + n_lat) / 2
            lat_rad = math.radians(mean_lat)
            # 1 degree latitude = 111320 meters (approximately constant)
            # 1 degree longitude = 111320 * cos(lat) meters (varies with latitude)
            dist_lat_m = (target_lat - n_lat) * 111320
            dist_lon_m = (target_lon - n_lon) * 111320 * math.cos(lat_rad)
            dist_m = math.sqrt(dist_lat_m ** 2 + dist_lon_m ** 2)

            weight = gaussian_weight(dist_m, sigma_meters)
            spatial_reduction = total_base_reduction * weight

            if spatial_reduction > 0.01:
                n_temp = nprops.get("air_temperature_celsius") or nprops.get("temperature", current_temp)
                neighbor_effects.append({
                    "cell_id": nid,
                    "distance_m": round(dist_m, 0),
                    "weight": round(weight, 4),
                    "reduction": round(spatial_reduction, 3),
                    "temp_before": round(n_temp, 2),
                    "temp_after": round(max(0, n_temp - spatial_reduction), 2),
                })
                total_spatial_reduction += spatial_reduction

    neighbor_effects.sort(key=lambda x: x["distance_m"])

    after_temp = max(0, current_temp - total_base_reduction)

    # Energy balance check (informational)
    rn = cell_data.get("net_radiation", 0)
    h = cell_data.get("sensible_heat_flux", 0)
    le = cell_data.get("latent_heat_flux", 0)
    g = cell_data.get("ground_heat_flux", 0)
    energy_balance_residual = rn - h - le - g if rn else None

    return {
        "before": round(current_temp, 2),
        "after": round(after_temp, 2),
        "reduction": round(current_temp - after_temp, 2),
        "interventions_applied": interventions,
        "spatial_effects": {
            "sigma_meters": sigma_meters,
            "n_neighbors_affected": len(neighbor_effects),
            "total_spatial_reduction": round(total_spatial_reduction, 3),
            "neighbors": neighbor_effects[:10],  # top 10 closest
        },
        "energy_balance": {
            "net_radiation": round(rn, 1) if rn else None,
            "sensible_heat": round(h, 1) if h else None,
            "latent_heat": round(le, 1) if le else None,
            "ground_heat": round(g, 1) if g else None,
            "residual": round(energy_balance_residual, 1) if energy_balance_residual is not None else None,
        },
    }
