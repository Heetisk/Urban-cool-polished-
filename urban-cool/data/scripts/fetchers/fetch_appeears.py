"""
Fetch satellite data using NASA AppEEARS API.

Data products:
- ECOSTRESS LST (ECO_L2T_LSTE.002) - Land Surface Temperature at 70m
- Landsat 8 Surface Reflectance (L08.002) - SR_B4 (Red) + SR_B5 (NIR) for NDVI at 30m

NDVI is computed as (SR_B5 - SR_B4) / (SR_B5 + SR_B4)

Requires NASA Earthdata Login credentials.
"""

import requests
import json
import time
import os
from typing import Dict, List, Optional


class AppEEARSClient:
    """Client for NASA AppEEARS API."""

    BASE_URL = "https://appeears.earthdatacloud.nasa.gov/api"

    def __init__(self, username: str, password: str):
        self.token = self._get_token(username, password)

    def _get_token(self, username: str, password: str) -> str:
        """Get authentication token using HTTP Basic Auth."""
        url = f"{self.BASE_URL}/login"
        response = requests.post(url, auth=(username, password))
        response.raise_for_status()
        return response.json()["token"]

    def _headers(self) -> Dict:
        return {"Authorization": f"Bearer {self.token}"}

    def submit_area_request(
        self,
        geojson: Dict,
        product: str,
        layers: List[str],
        start_date: str,
        end_date: str,
        task_name: str = "UrbanCool-Fetch",
    ) -> str:
        """
        Submit an area sample request.

        Args:
            geojson: GeoJSON FeatureCollection with polygon
            product: AppEEARS product ID
            layers: List of layer names
            start_date: Start date (MM-DD-YYYY)
            end_date: End date (MM-DD-YYYY)
            task_name: Name for the task

        Returns:
            Task ID string
        """
        url = f"{self.BASE_URL}/task"

        task = {
            "task_type": "area",
            "task_name": task_name,
            "params": {
                "dates": [
                    {
                        "startDate": start_date,
                        "endDate": end_date,
                        "recurring": False,
                    }
                ],
                "layers": [
                    {"product": product, "layer": layer} for layer in layers
                ],
                "geo": geojson,
                "output": {
                    "format": {
                        "type": "geotiff",
                        "filename_date": "calendar",
                    },
                    "projection": "geographic",
                },
            },
        }

        response = requests.post(url, json=task, headers=self._headers())
        response.raise_for_status()
        return response.json()["task_id"]

    def get_task_status(self, task_id: str) -> Dict:
        url = f"{self.BASE_URL}/task/{task_id}"
        response = requests.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def wait_for_task(self, task_id: str, poll_interval: int = 20, max_wait: int = 3600) -> Dict:
        elapsed = 0
        while elapsed < max_wait:
            # Use /status endpoint for progress
            url = f"{self.BASE_URL}/status/{task_id}"
            response = requests.get(url, headers=self._headers())
            response.raise_for_status()
            status = response.json()
            state = status.get("status", "unknown")

            if state == "done":
                return status
            elif state == "failed":
                raise RuntimeError(f"Task {task_id} failed: {status}")

            print(f"  Task {task_id}: {state} ({elapsed}s elapsed)")
            time.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"Task {task_id} did not complete within {max_wait}s")

    def list_task_files(self, task_id: str) -> List[Dict]:
        url = f"{self.BASE_URL}/bundle/{task_id}"
        response = requests.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json().get("files", [])

    def download_file(self, task_id: str, file_id: str, output_path: str) -> str:
        url = f"{self.BASE_URL}/bundle/{task_id}/{file_id}"
        response = requests.get(
            url, headers=self._headers(), allow_redirects=True, stream=True
        )
        response.raise_for_status()

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return output_path


def create_ahmedabad_geojson() -> Dict:
    """Create a GeoJSON FeatureCollection for Ahmedabad city bounds."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [72.5, 23.0],
                            [72.7, 23.0],
                            [72.7, 23.15],
                            [72.5, 23.15],
                            [72.5, 23.0],
                        ]
                    ],
                },
                "properties": {},
            }
        ],
    }


def fetch_lst_appeears(
    username: str,
    password: str,
    output_dir: str,
    city: str = "ahmedabad",
    year: int = 2024,
) -> Optional[str]:
    """
    Fetch ECOSTRESS LST using AppEEARS.

    Product: ECO_L2T_LSTE.002 (Tiled Land Surface Temperature)
    Resolution: 70m
    """
    print("Fetching ECOSTRESS LST via AppEEARS...")

    client = AppEEARSClient(username, password)
    aoi = create_ahmedabad_geojson()

    start_date = f"04-01-{year}"
    end_date = f"08-31-{year}"

    try:
        task_id = client.submit_area_request(
            geojson=aoi,
            product="ECO_L2T_LSTE.002",
            layers=["LST"],
            start_date=start_date,
            end_date=end_date,
            task_name=f"Ahmedabad-ECOSTRESS-LST-{year}",
        )
        print(f"  Task submitted: {task_id}")

        status = client.wait_for_task(task_id)
        print(f"  Task complete: {task_id}")

        files = client.list_task_files(task_id)
        os.makedirs(output_dir, exist_ok=True)

        downloaded_path = None
        for file_info in files:
            file_id = file_info["file_id"]
            filename = file_info.get("file_name", f"{file_id}.tif")
            if not filename.endswith(".tif"):
                continue
            output_path = os.path.join(output_dir, filename)
            client.download_file(task_id, file_id, output_path)
            print(f"  Downloaded: {filename}")
            downloaded_path = output_path

        return downloaded_path

    except Exception as e:
        print(f"  Error fetching ECOSTRESS LST: {e}")
        return None


def fetch_ndvi_appeears(
    username: str,
    password: str,
    output_dir: str,
    city: str = "ahmedabad",
    year: int = 2024,
) -> Optional[List[str]]:
    """
    Fetch Landsat 8 Surface Reflectance bands for NDVI calculation.

    Product: L08.002 (Landsat 8 ARD Surface Reflectance)
    Bands: SR_B4 (Red, 650nm) + SR_B5 (NIR, 865nm)
    NDVI = (SR_B5 - SR_B4) / (SR_B5 + SR_B4)
    Resolution: 30m
    """
    print("Fetching Landsat 8 Surface Reflectance for NDVI via AppEEARS...")

    client = AppEEARSClient(username, password)
    aoi = create_ahmedabad_geojson()

    start_date = f"04-01-{year}"
    end_date = f"08-31-{year}"

    try:
        task_id = client.submit_area_request(
            geojson=aoi,
            product="L08.002",
            layers=["SR_B4", "SR_B5"],
            start_date=start_date,
            end_date=end_date,
            task_name=f"Ahmedabad-Landsat8-NDVI-{year}",
        )
        print(f"  Task submitted: {task_id}")

        status = client.wait_for_task(task_id)
        print(f"  Task complete: {task_id}")

        files = client.list_task_files(task_id)
        os.makedirs(output_dir, exist_ok=True)

        downloaded_files = []
        for file_info in files:
            file_id = file_info["file_id"]
            filename = file_info.get("file_name", f"{file_id}.tif")
            if not filename.endswith(".tif"):
                continue
            output_path = os.path.join(output_dir, filename)
            client.download_file(task_id, file_id, output_path)
            print(f"  Downloaded: {filename}")
            downloaded_files.append(output_path)

        return downloaded_files

    except Exception as e:
        print(f"  Error fetching Landsat 8 NDVI: {e}")
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch satellite data via AppEEARS")
    parser.add_argument("--username", required=True, help="NASA Earthdata username")
    parser.add_argument("--password", required=True, help="NASA Earthdata password")
    parser.add_argument("--city", default="ahmedabad", help="City name")
    parser.add_argument("--year", type=int, default=2024, help="Year")
    parser.add_argument("--output-dir", default="data/raw/satellite", help="Output directory")
    parser.add_argument("--product", choices=["lst", "ndvi", "both"], default="both", help="Product to fetch")
    args = parser.parse_args()

    if args.product in ("lst", "both"):
        fetch_lst_appeears(args.username, args.password, args.output_dir, args.city, args.year)

    if args.product in ("ndvi", "both"):
        fetch_ndvi_appeears(args.username, args.password, args.output_dir, args.city, args.year)
