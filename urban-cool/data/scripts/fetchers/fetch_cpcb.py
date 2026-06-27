"""
Fetch air quality data from CPCB (Central Pollution Control Board).

Uses the data.gov.in API for real-time AQI data.
Requires API key from https://www.data.gov.in/
"""

import requests
import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class CPCBClient:
    """Client for CPCB AQI API."""

    # data.gov.in API endpoint
    BASE_URL = "https://api.data.gov.in/resource"

    # Ahmedabad monitoring stations (from CPCB API)
    AHMEDABAD_STATIONS = [
        {"id": "guj-ahm-1", "name": "SAC ISRO Bopal", "lat": 23.0487, "lon": 72.5097},
        {"id": "guj-ahm-2", "name": "Rakhial", "lat": 23.0147, "lon": 72.5867},
        {"id": "guj-ahm-3", "name": "Maninagar", "lat": 22.9957, "lon": 72.5957},
        {"id": "guj-ahm-4", "name": "Gyaspur", "lat": 23.0357, "lon": 72.5597},
        {"id": "guj-ahm-5", "name": "Raikhad", "lat": 23.0197, "lon": 72.5697},
        {"id": "guj-ahm-6", "name": "Chandkheda", "lat": 23.0797, "lon": 72.5797},
        {"id": "guj-ahm-7", "name": "SVPI Airport Hansol", "lat": 23.0727, "lon": 72.6297},
        {"id": "guj-ahm-8", "name": "SAC ISRO Satellite", "lat": 23.0267, "lon": 72.5397},
    ]

    # Gandhinagar monitoring stations (from CPCB API)
    GANDHINAGAR_STATIONS = [
        {"id": "guj-gan-1", "name": "IIPHG Lekawada", "lat": 23.1957, "lon": 72.6347},
        {"id": "guj-gan-2", "name": "GIFT City", "lat": 23.1907, "lon": 72.6497},
        {"id": "guj-gan-3", "name": "Sector-10", "lat": 23.2107, "lon": 72.6397},
    ]

    def __init__(self, api_key: str):
        """
        Initialize CPCB client.

        Args:
            api_key: data.gov.in API key
        """
        self.api_key = api_key

    def fetch_realtime_aqi(self, city: str = "Ahmedabad") -> List[Dict]:
        """
        Fetch real-time AQI data for a city.

        Args:
            city: City name

        Returns:
            List of station readings
        """
        url = f"{self.BASE_URL}/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
        params = {
            "api-key": self.api_key,
            "format": "json",
            "filters[state]": "Gujarat",
            "limit": 100,
        }

        try:
            response = requests.get(url, params=params, timeout=90)
            response.raise_for_status()
            data = response.json()

            records = data.get("records", [])
            city_lower = city.lower()
            records = [r for r in records if r.get("city", "").lower() == city_lower]
            print(f"Filtered to {len(records)} records for {city}")
            return self._parse_records(records)

        except Exception as e:
            print(f"Error fetching AQI data: {e}")
            return []

    def _parse_records(self, records: List[Dict]) -> List[Dict]:
        """
        Parse API records into standardized format.

        Args:
            records: Raw API records

        Returns:
            Parsed station readings
        """
        stations = {}

        for record in records:
            station_name = record.get("station", "Unknown")
            pollutant = record.get("pollutant_id")
            avg_value = record.get("avg_value") or record.get("pollutant_avg")

            if not pollutant or avg_value is None or avg_value == "NA":
                continue

            try:
                avg_value = float(avg_value)
            except (ValueError, TypeError):
                continue

            if station_name not in stations:
                stations[station_name] = {
                    "station": station_name,
                    "city": record.get("city"),
                    "state": record.get("state"),
                    "latitude": record.get("latitude"),
                    "longitude": record.get("longitude"),
                    "last_update": record.get("last_update"),
                    "pollutants": {},
                }

            stations[station_name]["pollutants"][pollutant] = {
                "avg": avg_value,
                "min": record.get("min_value") or record.get("pollutant_min"),
                "max": record.get("max_value") or record.get("pollutant_max"),
            }

        # Calculate AQI from pollutant sub-indices
        for station in stations.values():
            station["aqi"] = self._calculate_aqi(station["pollutants"])
            station["aqi_category"] = self._aqi_category(station["aqi"])

        return list(stations.values())

    def _calculate_aqi(self, pollutants: Dict) -> Optional[int]:
        """
        Calculate AQI from pollutant sub-indices.

        AQI = max(sub-index of all pollutants)
        """
        if not pollutants:
            return None

        # AQI sub-index calculation (simplified)
        sub_indices = []
        for pollutant, values in pollutants.items():
            avg = values.get("avg")
            if avg is not None and avg > 0:
                # Use avg as sub-index (CPCB already provides sub-indices)
                sub_indices.append(int(avg))

        return max(sub_indices) if sub_indices else None

    def _aqi_category(self, aqi: Optional[int]) -> str:
        """Map AQI to category."""
        if aqi is None:
            return "unknown"
        if aqi <= 50:
            return "good"
        elif aqi <= 100:
            return "satisfactory"
        elif aqi <= 200:
            return "moderate"
        elif aqi <= 300:
            return "poor"
        elif aqi <= 400:
            return "very_poor"
        else:
            return "severe"

    def fetch_historical_aqi(
        self,
        city: str = "Ahmedabad",
        start_date: str = None,
        end_date: str = None,
    ) -> List[Dict]:
        """
        Fetch historical AQI data.

        Args:
            city: City name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of daily readings
        """
        # Default to last 7 days
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        url = f"{self.BASE_URL}/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
        params = {
            "api-key": self.api_key,
            "format": "json",
            "filters[state]": "Gujarat",
            "filters[date]": f"{start_date} - {end_date}",
            "limit": 500,
        }

        try:
            response = requests.get(url, params=params, timeout=90)
            response.raise_for_status()
            data = response.json()

            records = data.get("records", [])
            city_lower = city.lower()
            records = [r for r in records if r.get("city", "").lower() == city_lower]
            print(f"Filtered to {len(records)} records for {city}")
            return self._parse_records(records)

        except Exception as e:
            print(f"Error fetching historical AQI: {e}")
            return []


def aggregate_aqi_to_grid(
    aqi_data: List[Dict],
    grid_cells: List[Dict],
    radius_km: float = 5.0,
) -> List[Dict]:
    """
    Aggregate AQI data to grid cells using spatial proximity.

    Args:
        aqi_data: List of station readings
        grid_cells: List of grid cell properties
        radius_km: Maximum distance to consider

    Returns:
        List of grid cell records with AQI data
    """
    import math

    def haversine(lat1, lon1, lat2, lon2):
        """Calculate distance between two points in km."""
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    results = []

    for cell in grid_cells:
        cell_lat = cell.get("centroid_lat")
        cell_lon = cell.get("centroid_lon")

        if not cell_lat or not cell_lon:
            continue

        # Find nearest stations
        nearby = []
        for station in aqi_data:
            s_lat = station.get("latitude")
            s_lon = station.get("longitude")

            if not s_lat or not s_lon:
                continue

            try:
                s_lat = float(s_lat)
                s_lon = float(s_lon)
            except (ValueError, TypeError):
                continue

            dist = haversine(cell_lat, cell_lon, s_lat, s_lon)

            if dist <= radius_km:
                nearby.append({"station": station, "distance": dist})

        # Aggregate from nearest stations
        if nearby:
            # Sort by distance
            nearby.sort(key=lambda x: x["distance"])

            # Use nearest station
            nearest = nearby[0]["station"]
            cell["aqi"] = nearest.get("aqi")
            cell["aqi_category"] = nearest.get("aqi_category")
            cell["pm25"] = nearest.get("pollutants", {}).get("PM2.5", {}).get("avg")
            cell["pm10"] = nearest.get("pollutants", {}).get("PM10", {}).get("avg")
            cell["no2"] = nearest.get("pollutants", {}).get("NO2", {}).get("avg")
            cell["so2"] = nearest.get("pollutants", {}).get("SO2", {}).get("avg")
            cell["co"] = nearest.get("pollutants", {}).get("CO", {}).get("avg")
            cell["o3"] = nearest.get("pollutants", {}).get("O3", {}).get("avg")
            cell["nearest_station"] = nearest.get("station")
            cell["station_distance_km"] = round(nearby[0]["distance"], 2)

        results.append(cell)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch CPCB AQI data")
    parser.add_argument("--api-key", required=True, help="data.gov.in API key")
    parser.add_argument("--city", default="Ahmedabad", help="City name")
    parser.add_argument("--output", default="data/raw/cpcb/aqi_data.json", help="Output path")
    parser.add_argument("--mode", choices=["realtime", "historical"], default="realtime")
    args = parser.parse_args()

    client = CPCBClient(args.api_key)

    if args.mode == "realtime":
        data = client.fetch_realtime_aqi(args.city)
    else:
        data = client.fetch_historical_aqi(args.city)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Fetched {len(data)} station readings")
    print(f"Saved to {args.output}")
