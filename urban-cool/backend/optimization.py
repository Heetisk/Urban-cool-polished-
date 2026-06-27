"""
Greedy Budget-Constrained Optimization for Urban Cooling Interventions.

Algorithm:
  1. For each cell, estimate cooling_impact for each intervention type
  2. Compute cooling_impact_per_dollar for each cell+intervention pair
  3. Sort by impact_per_dollar descending
  4. Greedily select: pick best, deduct cost, repeat until budget exhausted

O(N log N) — instant response for 1258 cells.
"""

import math
from typing import Dict, List, Optional


# Cost per unit intervention (INR)
INTERVENTION_COSTS = {
    "tree_cover": 5000,       # per 1% tree cover increase per cell
    "cool_roof": 8000,        # per 1% cool roof conversion per cell
    "green_roof": 12000,      # per 1% green roof conversion per cell
    "water_body": 50000,      # per water body feature per cell
}

# Temperature reduction per unit intervention (degrees C)
INTERVENTION_COOLING = {
    "tree_cover": 0.08,       # per 1% tree cover
    "cool_roof": 0.05,        # per 1% cool roof
    "green_roof": 0.06,       # per 1% green roof
    "water_body": 0.30,       # per water body feature
}


def estimate_cell_cooling(
    cell_data: Dict,
    intervention_type: str,
    intensity: float,
) -> float:
    """
    Estimate temperature reduction for a cell given an intervention.

    Args:
        cell_data: cell properties (temperature, ndvi, builtup_density, etc.)
        intervention_type: one of "tree_cover", "cool_roof", "green_roof", "water_body"
        intensity: intervention intensity (0-100 for percentage-based, 1 for binary)

    Returns:
        Estimated temperature reduction in degrees C
    """
    base_cooling = INTERVENTION_COOLING.get(intervention_type, 0)
    temp = cell_data.get("temperature", 40)

    # Scale cooling by intensity
    cooling = base_cooling * intensity

    # Modifier: hotter cells benefit more (diminishing returns at low temps)
    temp_factor = max(0.5, min(1.5, (temp - 35) / 10))
    cooling *= temp_factor

    # Modifier: cells with low NDVI benefit more from greening
    if intervention_type in ("tree_cover", "green_roof"):
        ndvi = cell_data.get("ndvi", 0.3)
        ndvi_factor = max(0.7, 1.0 + (0.3 - ndvi) * 0.5)
        cooling *= ndvi_factor

    # Modifier: cells with high built-up benefit more from cool roofs
    if intervention_type == "cool_roof":
        builtup = cell_data.get("builtup_density", 0.5)
        builtup_factor = max(0.7, 0.5 + builtup)
        cooling *= builtup_factor

    return round(max(0, cooling), 4)


def compute_impact_per_dollar(
    cell_data: Dict,
    intervention_type: str,
    intensity: float = 50.0,
) -> Dict:
    """
    Compute cooling impact per dollar for a cell+intervention pair.

    Returns:
        Dict with cell_id, intervention, intensity, cooling, cost, impact_per_dollar
    """
    cooling = estimate_cell_cooling(cell_data, intervention_type, intensity)
    cost_per_unit = INTERVENTION_COSTS[intervention_type]

    cost = cost_per_unit * intensity

    impact_per_dollar = cooling / cost if cost > 0 else 0

    return {
        "cell_id": cell_data.get("cell_id"),
        "lat": cell_data.get("centroid_lat"),
        "lon": cell_data.get("centroid_lon"),
        "intervention": intervention_type,
        "intensity": intensity,
        "estimated_cooling_c": round(cooling, 3),
        "cost_inr": round(cost, 2),
        "impact_per_dollar": round(impact_per_dollar, 8),
        "current_temp": cell_data.get("temperature"),
    }


def greedy_optimize(
    all_cells: Dict[str, Dict],
    budget: float,
    intervention_types: List[str] = None,
    intensity: float = 50.0,
    max_per_cell: int = 1,
) -> Dict:
    """
    Greedy budget-constrained optimization.

    Args:
        all_cells: dict of cell_id -> cell properties
        budget: total budget in INR
        intervention_types: list of allowed interventions (default: all)
        intensity: intervention intensity (0-100)
        max_per_cell: max interventions per cell (default: 1)

    Returns:
        Dict with allocations, summary, and remaining budget
    """
    if intervention_types is None:
        intervention_types = ["tree_cover", "cool_roof", "green_roof"]

    # Build all candidate interventions
    candidates = []
    for cell_id, cell_data in all_cells.items():
        for int_type in intervention_types:
            entry = compute_impact_per_dollar(cell_data, int_type, intensity)
            candidates.append(entry)

    # Sort by impact_per_dollar descending
    candidates.sort(key=lambda x: x["impact_per_dollar"], reverse=True)

    # Greedy selection
    allocations = []
    remaining_budget = budget
    cell_intervention_count = {}

    for candidate in candidates:
        cell_id = candidate["cell_id"]
        int_type = candidate["intervention"]
        cost = candidate["cost_inr"]

        # Check budget
        if cost > remaining_budget:
            continue

        # Check per-cell limit
        cell_key = f"{cell_id}"
        current_count = cell_intervention_count.get(cell_key, 0)
        if current_count >= max_per_cell:
            continue

        # Select this intervention
        allocations.append(candidate)
        remaining_budget -= cost
        cell_intervention_count[cell_key] = current_count + 1

    # Compute summary
    total_cooling = sum(a["estimated_cooling_c"] for a in allocations)
    total_cost = sum(a["cost_inr"] for a in allocations)
    cells_affected = len(set(a["cell_id"] for a in allocations))

    intervention_mix = {}
    for a in allocations:
        int_type = a["intervention"]
        intervention_mix[int_type] = intervention_mix.get(int_type, 0) + 1

    return {
        "allocations": allocations,
        "summary": {
            "total_budget_inr": budget,
            "spent_inr": round(total_cost, 2),
            "remaining_inr": round(remaining_budget, 2),
            "total_estimated_cooling_c": round(total_cooling, 3),
            "avg_cooling_per_cell_c": round(total_cooling / cells_affected, 3) if cells_affected > 0 else 0,
            "cells_affected": cells_affected,
            "total_cells": len(all_cells),
            "intervention_mix": intervention_mix,
            "budget_utilization_pct": round((total_cost / budget) * 100, 1) if budget > 0 else 0,
        },
    }


def compare_scenarios(scenario_a: Dict, scenario_b: Dict) -> Dict:
    """
    Compare two optimization scenarios side by side.

    Args:
        scenario_a: first scenario result from greedy_optimize()
        scenario_b: second scenario result from greedy_optimize()

    Returns:
        Dict with side-by-side comparison
    """
    sa = scenario_a.get("summary", {})
    sb = scenario_b.get("summary", {})

    return {
        "scenario_a": {
            "name": "Scenario A",
            "total_cooling_c": sa.get("total_estimated_cooling_c", 0),
            "total_cost_inr": sa.get("spent_inr", 0),
            "cells_affected": sa.get("cells_affected", 0),
            "intervention_mix": sa.get("intervention_mix", {}),
            "avg_cooling_per_cell_c": sa.get("avg_cooling_per_cell_c", 0),
            "budget_utilization_pct": sa.get("budget_utilization_pct", 0),
        },
        "scenario_b": {
            "name": "Scenario B",
            "total_cooling_c": sb.get("total_estimated_cooling_c", 0),
            "total_cost_inr": sb.get("spent_inr", 0),
            "cells_affected": sb.get("cells_affected", 0),
            "intervention_mix": sb.get("intervention_mix", {}),
            "avg_cooling_per_cell_c": sb.get("avg_cooling_per_cell_c", 0),
            "budget_utilization_pct": sb.get("budget_utilization_pct", 0),
        },
    }
