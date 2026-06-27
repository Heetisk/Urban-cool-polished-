"""
Physics-Based Features Module.

Adds physically meaningful features to grid cells:
1. Albedo - Surface reflectivity (affects energy absorption)
2. Emissivity - Surface thermal emissivity (affects thermal radiation)
3. Sky View Factor (SVF) - Fraction of sky visible from surface
4. Surface Energy Balance components (simplified)
5. Urban Heat Island (UHI) intensity

These features are grounded in thermodynamics and urban climatology.
"""

import math
from typing import Dict, Optional


def compute_albedo(ndvi: Optional[float], ndbi: Optional[float] = None) -> float:
    """
    Estimate surface albedo from NDVI and NDBI.

    Physics basis:
    - Vegetation (high NDVI) has moderate albedo (0.15-0.25)
    - Built-up areas (high NDBI) have lower albedo (0.10-0.20)
    - Bare soil has higher albedo (0.20-0.35)
    - Water has low albedo (0.06-0.10)

    Reference: Liang (2001), "Narrowband and broadband surface albedos"

    Args:
        ndvi: Normalized Difference Vegetation Index (-1 to 1)
        ndbi: Normalized Difference Built-up Index (-1 to 1)

    Returns:
        Estimated albedo (0-1)
    """
    if ndvi is None:
        ndvi = 0.3  # Default urban NDVI

    # Vegetation albedo increases with NDVI
    veg_albedo = 0.15 + 0.10 * max(0, ndvi)

    # Built-up albedo decreases with NDBI
    if ndbi is not None:
        builtup_albedo = 0.20 - 0.05 * max(0, ndbi)
    else:
        builtup_albedo = 0.15

    # Blend based on NDVI (higher NDVI = more vegetation influence)
    veg_fraction = max(0, min(1, (ndvi + 0.1) / 0.6))
    albedo = veg_albedo * veg_fraction + builtup_albedo * (1 - veg_fraction)

    return round(max(0.05, min(0.40, albedo)), 4)


def compute_emissivity(
    ndvi: Optional[float],
    builtup_density: Optional[float] = None,
) -> float:
    """
    Estimate surface emissivity from NDVI and built-up density.

    Physics basis:
    - Vegetation has high emissivity (0.95-0.98)
    - Concrete/asphalt has moderate emissivity (0.90-0.95)
    - Bare soil has variable emissivity (0.85-0.95)
    - Water has high emissivity (0.95-0.99)

    Reference: Valor & Caselles (1996), "Mapping land surface emissivity"

    Args:
        ndvi: NDVI value (-1 to 1)
        builtup_density: Built-up density (0-1)

    Returns:
        Estimated emissivity (0.8-1.0)
    """
    if ndvi is None:
        ndvi = 0.3

    # Vegetation emissivity increases with NDVI
    veg_emissivity = 0.95 + 0.03 * min(1, max(0, ndvi))

    # Built-up emissivity is moderate
    builtup_emissivity = 0.92

    # Blend based on NDVI
    veg_fraction = max(0, min(1, (ndvi + 0.1) / 0.6))
    emissivity = veg_emissivity * veg_fraction + builtup_emissivity * (1 - veg_fraction)

    # Reduce emissivity in dense built-up areas
    if builtup_density is not None and builtup_density > 0.7:
        emissivity *= 0.98

    return round(max(0.85, min(0.99, emissivity)), 4)


def compute_sky_view_factor(
    building_density_per_km2: Optional[float],
    road_density_km_km2: Optional[float] = None,
) -> float:
    """
    Estimate Sky View Factor (SVF) from building and road density.

    Physics basis:
    - SVF is the fraction of sky visible from a point on the ground
    - Low SVF = urban canyon effect (heat trapped)
    - High SVF = open area (heat escapes)
    - Typical urban SVF: 0.3-0.7
    - Open rural SVF: 0.9-1.0

    Reference: Oke (1981), "Canyon geometry"

    Args:
        building_density_per_km2: Buildings per km²
        road_density_km_km2: Road density in km/km²

    Returns:
        Estimated SVF (0-1)
    """
    if building_density_per_km2 is None:
        building_density_per_km2 = 500

    # Building density reduces SVF
    # 0 buildings/km² → SVF ~0.95
    # 2000 buildings/km² → SVF ~0.35
    building_effect = max(0, 1 - (building_density_per_km2 / 2500))

    # Road density also reduces SVF (indicates urban development)
    if road_density_km_km2 is not None:
        road_effect = max(0, 1 - (road_density_km_km2 / 100))
        svf = 0.3 * building_effect + 0.1 * road_effect + 0.6 * building_effect
    else:
        svf = 0.3 * building_effect + 0.7 * building_effect

    return round(max(0.2, min(0.95, svf)), 4)


def compute_uhi_intensity(
    temperature: Optional[float],
    rural_temp: float = 32.0,
) -> float:
    """
    Calculate Urban Heat Island (UHI) intensity.

    Physics basis:
    - UHI = Urban temperature - Rural temperature
    - Strong UHI indicates urban heating effect
    - Typical UHI: 2-8°C in cities

    Args:
        temperature: Cell temperature in °C
        rural_temp: Rural baseline temperature (default 32°C for Ahmedabad)

    Returns:
        UHI intensity in °C
    """
    if temperature is None:
        return 0.0

    uhi = temperature - rural_temp
    return round(max(-5, min(15, uhi)), 2)


def compute_surface_energy_balance(
    solar_wm2: Optional[float],
    albedo: float,
    temperature: Optional[float],
    humidity_pct: Optional[float],
    wind_speed_ms: Optional[float],
    svf: float,
) -> Dict[str, float]:
    """
    Compute simplified surface energy balance components.

    Physics basis:
    - Net Radiation (Rn) = (1-albedo) * Solar + Longwave in - Longwave out
    - Sensible Heat (H) = Rn * (1 - Bowen ratio)
    - Latent Heat (LE) = Rn * Bowen ratio
    - Ground Heat (G) ≈ 0.1 * Rn (during daytime)

    Simplified for urban heat analysis.

    Args:
        solar_wm2: Incoming solar radiation (W/m²)
        albedo: Surface albedo
        temperature: Surface temperature (°C)
        humidity_pct: Relative humidity (%)
        wind_speed_ms: Wind speed (m/s)
        svf: Sky view factor

    Returns:
        Dictionary of energy balance components (W/m²)
    """
    if solar_wm2 is None:
        solar_wm2 = 200

    # Net shortwave radiation
    rn_shortwave = solar_wm2 * (1 - albedo)

    # Longwave radiation (simplified)
    temp_k = (temperature or 35) + 273.15
    stefan_boltzmann = 5.67e-8
    emissivity = 0.95
    lw_out = emissivity * stefan_boltzmann * (temp_k ** 4)

    # Sky temperature (approximate - clear sky ~285K, cloudy ~295K)
    sky_temp_k = 298  # ~25°C typical summer (effective atmospheric)
    sky_emissivity = 0.85
    lw_in = sky_emissivity * stefan_boltzmann * (sky_temp_k ** 4) * svf

    # Net radiation
    rn = rn_shortwave + lw_in - lw_out

    # Bowen ratio (sensible/latent heat ratio)
    # Higher humidity → more latent heat → lower Bowen ratio
    if humidity_pct is not None:
        humidity_frac = humidity_pct / 100
        bowen_ratio = 1.5 - humidity_frac  # ~0.5 (humid) to 1.5 (dry)
    else:
        bowen_ratio = 1.0

    # Sensible and latent heat
    h = rn * (bowen_ratio / (1 + bowen_ratio))
    le = rn * (1 / (1 + bowen_ratio))

    # Ground heat flux
    g = 0.1 * rn

    return {
        "net_radiation": round(rn, 2),
        "sensible_heat": round(h, 2),
        "latent_heat": round(le, 2),
        "ground_heat": round(g, 2),
        "bowen_ratio": round(bowen_ratio, 2),
    }


def compute_all_physics_features(props: Dict, rural_temp: float = 32.0) -> Dict:
    """
    Compute all physics-based features for a grid cell.

    Args:
        props: Dictionary of cell properties
        rural_temp: Rural baseline temperature for UHI calculation

    Returns:
        Dictionary of physics features to add
    """
    ndvi = props.get("ndvi")
    ndbi = props.get("ndbi")
    builtup_density = props.get("builtup_density")
    building_density = props.get("building_density_per_km2")
    road_density = props.get("road_density_km_km2")
    solar = props.get("solar_wm2")
    temperature = props.get("temperature")
    humidity = props.get("humidity_pct")
    wind = props.get("wind_speed_ms")

    albedo = compute_albedo(ndvi, ndbi)
    emissivity = compute_emissivity(ndvi, builtup_density)
    svf = compute_sky_view_factor(building_density, road_density)
    uhi = compute_uhi_intensity(temperature, rural_temp)

    energy = compute_surface_energy_balance(
        solar, albedo, temperature, humidity, wind, svf
    )

    return {
        "albedo": albedo,
        "emissivity": emissivity,
        "sky_view_factor": svf,
        "uhi_intensity": uhi,
        "net_radiation": energy["net_radiation"],
        "sensible_heat_flux": energy["sensible_heat"],
        "latent_heat_flux": energy["latent_heat"],
        "ground_heat_flux": energy["ground_heat"],
        "bowen_ratio": energy["bowen_ratio"],
    }
