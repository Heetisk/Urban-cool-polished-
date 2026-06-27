"""
Fetch real hourly temperature data from Open-Meteo API for validation.

Open-Meteo provides free historical weather data without API keys.
Uses ERA5 backtest (reanalysis) and IMD station data where available.
"""

import requests
import json
import os
from datetime import datetime, timedelta


def fetch_open_meteo_archive(lat, lon, start_date, end_date):
    """
    Fetch hourly temperature from Open-Meteo Archive API.
    
    Uses ERA5 backtest data which is calibrated against IMD stations.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "timezone": "Asia/Kolkata",
    }
    
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def compute_daily_stats(hourly_data):
    """Compute daily min/max/mean from hourly data."""
    dates = hourly_data.get("time", [])
    temps = hourly_data.get("temperature_2m", [])
    
    daily = {}
    for dt_str, temp in zip(dates, temps):
        if temp is None:
            continue
        date = dt_str[:10]
        if date not in daily:
            daily[date] = []
        daily[date].append(temp)
    
    stats = {}
    for date, vals in daily.items():
        if len(vals) >= 6:  # At least 6 hours of data
            stats[date] = {
                "min": round(min(vals), 1),
                "max": round(max(vals), 1),
                "mean": round(sum(vals) / len(vals), 1),
                "n_hours": len(vals),
            }
    return stats


def main():
    cities = {
        "ahmedabad": {"lat": 23.0225, "lon": 72.5714},
        "gandhinagar": {"lat": 23.2156, "lon": 72.6369},
    }
    
    # April-August 2024 (same period as Landsat 8)
    start_date = "2024-04-01"
    end_date = "2024-08-31"
    
    output_dir = os.path.join(os.path.dirname(__file__), "..", "raw", "openmeteo")
    os.makedirs(output_dir, exist_ok=True)
    
    for city, coords in cities.items():
        print(f"\nFetching Open-Meteo data for {city}...")
        print(f"  Coordinates: {coords['lat']}, {coords['lon']}")
        print(f"  Period: {start_date} to {end_date}")
        
        try:
            data = fetch_open_meteo_archive(
                coords["lat"], coords["lon"], start_date, end_date
            )
            
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            
            print(f"  Hourly records: {len(times)}")
            
            # Compute daily stats
            daily_stats = compute_daily_stats(hourly)
            print(f"  Days with data: {len(daily_stats)}")
            
            # Overall stats
            all_temps = [t for t in temps if t is not None]
            if all_temps:
                print(f"  Overall: min={min(all_temps):.1f}C, max={max(all_temps):.1f}C, mean={sum(all_temps)/len(all_temps):.1f}C")
            
            # Summer stats (June-August)
            summer_temps = []
            for dt_str, temp in zip(times, temps):
                if temp is not None and dt_str[:7] in ["2024-06", "2024-07", "2024-08"]:
                    summer_temps.append(temp)
            if summer_temps:
                print(f"  Summer (Jun-Aug): min={min(summer_temps):.1f}C, max={max(summer_temps):.1f}C, mean={sum(summer_temps)/len(summer_temps):.1f}C")
            
            # Save
            output = {
                "city": city,
                "lat": coords["lat"],
                "lon": coords["lon"],
                "period": f"{start_date} to {end_date}",
                "source": "Open-Meteo Archive API (ERA5 backtest)",
                "overall": {
                    "min": round(min(all_temps), 1) if all_temps else None,
                    "max": round(max(all_temps), 1) if all_temps else None,
                    "mean": round(sum(all_temps) / len(all_temps), 1) if all_temps else None,
                    "n_hours": len(all_temps),
                },
                "daily_stats": daily_stats,
            }
            
            out_path = os.path.join(output_dir, f"{city}_temp_2024.json")
            with open(out_path, "w") as f:
                json.dump(output, f, indent=2)
            print(f"  Saved to: {out_path}")
            
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    main()
