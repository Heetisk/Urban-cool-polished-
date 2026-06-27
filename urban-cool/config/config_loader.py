"""
Config Loader - Centralized city configuration management.

Loads city configs from config/cities.json and provides
path helpers for data and model directories.
"""

import json
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "cities.json")

# Load .env from project root
load_dotenv(os.path.join(BASE_DIR, ".env"))

_config_cache = None


def load_cities_config():
    """Load all city configs from cities.json."""
    global _config_cache
    if _config_cache is None:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            _config_cache = json.load(f)
    return _config_cache


def get_city_config(city: str) -> dict:
    """Get config for a specific city."""
    config = load_cities_config()
    if city not in config:
        available = list(config.keys())
        raise ValueError(f"Unknown city '{city}'. Available: {available}")
    city_config = config[city].copy()
    # CPCB API key from environment variable, not config file
    city_config["cpcb_api_key"] = os.environ.get("CPCB_API_KEY")
    return city_config


def get_cpcb_api_key() -> str:
    """Get CPCB API key from environment variable."""
    return os.environ.get("CPCB_API_KEY")


def get_available_cities():
    """Get list of available city keys."""
    return list(load_cities_config().keys())


def get_city_data_dir(city: str) -> str:
    """Get data directory path for a city."""
    return os.path.join(BASE_DIR, "data", city)


def get_city_processed_dir(city: str) -> str:
    """Get processed data directory for a city."""
    return os.path.join(get_city_data_dir(city), "processed")


def get_city_models_dir(city: str) -> str:
    """Get models directory for a city."""
    return os.path.join(BASE_DIR, "models", city)


def get_heat_grid_path(city: str) -> str:
    """Get path to heat_grid.geojson for a city."""
    return os.path.join(get_city_processed_dir(city), "heat_grid.geojson")


def get_model_path(city: str) -> str:
    """Get path to trained model for a city."""
    return os.path.join(get_city_models_dir(city), "temperature_model.joblib")


def get_shap_path(city: str) -> str:
    """Get path to SHAP explainer for a city."""
    return os.path.join(get_city_models_dir(city), "temperature_shap.joblib")


def get_scaler_path(city: str) -> str:
    """Get path to StandardScaler for a city."""
    return os.path.join(get_city_models_dir(city), "temperature_scaler.joblib")


def get_city_bounds(city: str) -> dict:
    """Get geographic bounds for a city."""
    config = get_city_config(city)
    return config["bounds"]


def get_city_prefix(city: str) -> str:
    """Get cell ID prefix for a city."""
    return get_city_config(city)["prefix"]


def list_cities_with_data():
    """List cities that have processed data available."""
    available = get_available_cities()
    cities_with_data = []
    for city in available:
        grid_path = get_heat_grid_path(city)
        if os.path.exists(grid_path):
            cities_with_data.append(city)
    return cities_with_data
