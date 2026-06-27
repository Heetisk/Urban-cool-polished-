"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


VALID_INTERVENTION_TYPES = {"tree_cover", "cool_roof", "green_roof", "water_body"}


class SimulateRequest(BaseModel):
    cell_id: str
    tree_cover: float = Field(0, ge=0, le=100, description="Tree cover percentage (0-100)")
    cool_roof: float = Field(0, ge=0, le=100, description="Cool roof percentage (0-100)")
    green_roof: float = Field(0, ge=0, le=100, description="Green roof percentage (0-100)")
    water_body: float = Field(0, ge=0, le=100, description="Water body intensity (0-100)")


class OptimizeRequest(BaseModel):
    budget: float = Field(..., gt=0, description="Total budget in INR")
    intervention_types: Optional[List[str]] = Field(
        None,
        description="Allowed interventions: tree_cover, cool_roof, green_roof, water_body",
    )
    intensity: float = Field(50.0, ge=1, le=100, description="Intervention intensity (1-100)")
    max_per_cell: int = Field(1, ge=1, le=5, description="Max interventions per cell")

    @field_validator("intervention_types")
    @classmethod
    def validate_intervention_types(cls, v):
        if v is not None:
            invalid = set(v) - VALID_INTERVENTION_TYPES
            if invalid:
                raise ValueError(f"Invalid intervention types: {invalid}. Valid: {VALID_INTERVENTION_TYPES}")
        return v


class ScenarioCompareRequest(BaseModel):
    scenario_a: dict
    scenario_b: dict
