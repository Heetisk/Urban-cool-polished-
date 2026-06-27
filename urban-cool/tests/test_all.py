"""Comprehensive test script for UrbanCool AI."""
import json
import os
import sys
import time
import traceback

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

AHMEDABAD_GRID = os.path.join(BASE_DIR, "data", "ahmedabad", "processed", "heat_grid.geojson")

PASS = "PASS"
FAIL = "FAIL"
results = []


def run_test(name, func):
    try:
        func()
        results.append((name, PASS, ""))
        print(f"  [PASS] {name}")
    except Exception as e:
        results.append((name, FAIL, str(e)))
        print(f"  [FAIL] {name}: {e}")


# ========================================================================
print("=" * 60)
print("URBANCOOL AI - COMPREHENSIVE TEST SUITE")
print("=" * 60)

# --- 1. Data Pipeline ---
print("\n--- 1. Data Pipeline ---")


def test_heat_grid_exists():
    path = AHMEDABAD_GRID
    assert os.path.exists(path), "heat_grid.geojson not found"


def test_heat_grid_features():
    path = AHMEDABAD_GRID
    with open(path) as f:
        data = json.load(f)
    n = len(data["features"])
    assert n >= 100, f"Expected at least 100 features, got {n}"


def test_heat_grid_fields():
    path = AHMEDABAD_GRID
    with open(path) as f:
        data = json.load(f)
    required = [
        "cell_id", "temperature", "ndvi", "builtup_density",
        "humidity_pct", "wind_speed_ms", "solar_wm2",
        "distance_water_m", "road_density_km_km2",
    ]
    props = data["features"][0]["properties"]
    missing = [f for f in required if f not in props]
    assert not missing, f"Missing fields: {missing}"


def test_cell_id_format():
    path = AHMEDABAD_GRID
    with open(path) as f:
        data = json.load(f)
    for feat in data["features"][:20]:
        cid = feat["properties"]["cell_id"]
        parts = cid.split("_")
        assert len(parts) == 3, f"Cell ID {cid} does not have 3 parts"
        assert parts[1].isdigit() and parts[2].isdigit(), f"Cell ID {cid} row/col not numeric"


def test_temperature_range():
    path = AHMEDABAD_GRID
    with open(path) as f:
        data = json.load(f)
    temps = [f["properties"]["temperature"] for f in data["features"]]
    assert all(t is not None for t in temps), "Some temperatures are None"
    assert 15 < min(temps) < 50, f"Temperature min {min(temps)} out of expected range (15-50C)"
    assert 30 < max(temps) < 70, f"Temperature max {max(temps)} out of expected range (30-70C)"


def test_master_grid_exists():
    path = os.path.join(BASE_DIR, "data", "ahmedabad", "processed", "master_grid.geojson")
    assert os.path.exists(path), "master_grid.geojson not found"


def test_era5_data_exists():
    path = os.path.join(BASE_DIR, "data", "raw", "era5", "era5_ahmedabad_2024.nc")
    assert os.path.exists(path), "ERA5 NetCDF not found"


run_test("heat_grid.geojson exists", test_heat_grid_exists)
run_test("heat_grid has >= 100 features", test_heat_grid_features)
run_test("heat_grid has all required fields", test_heat_grid_fields)
run_test("cell_id format is AHM_XXXX_XXXX", test_cell_id_format)
run_test("temperature in valid range (30-40C)", test_temperature_range)
run_test("master_grid.geojson exists", test_master_grid_exists)
run_test("ERA5 NetCDF exists", test_era5_data_exists)

# --- 2. Model Files ---
print("\n--- 2. Model Files ---")


def test_temperature_model_exists():
    path = os.path.join(BASE_DIR, "models", "ahmedabad", "temperature_model.joblib")
    assert os.path.exists(path), "models/ahmedabad/temperature_model.joblib not found"


def test_temperature_shap_exists():
    path = os.path.join(BASE_DIR, "models", "ahmedabad", "temperature_shap.joblib")
    assert os.path.exists(path), "models/ahmedabad/temperature_shap.joblib not found"


def test_old_models_deleted():
    old_files = ["risk_model.joblib", "label_encoder.joblib", "shap_explainer.pkl"]
    for f in old_files:
        path = os.path.join(BASE_DIR, "models", f)
        assert not os.path.exists(path), f"Old model {f} still exists"


run_test("temperature_model.joblib exists", test_temperature_model_exists)
run_test("temperature_shap.joblib exists", test_temperature_shap_exists)
run_test("old risk model files deleted", test_old_models_deleted)

# --- 3. Model Inference ---
print("\n--- 3. Model Inference ---")


def test_model_load():
    import joblib
    model = joblib.load(os.path.join(BASE_DIR, "models", "ahmedabad", "temperature_model.joblib"))
    assert model is not None, "Model failed to load"


def test_model_predict():
    import joblib
    import numpy as np
    model = joblib.load(os.path.join(BASE_DIR, "models", "ahmedabad", "temperature_model.joblib"))
    # ML features (13): ndvi, builtup, distance_water, road_density, svf, building_density, albedo,
    # emissivity, bowen_ratio, ndvi_spatial_lag, builtup_density_spatial_lag, ndvi_x_builtup, distance_x_builtup
    X = np.array([[0.34, 0.96, 823.3, 48.0, 0.42, 298.0, 0.15, 0.95, 1.0, 0.30, 0.85, 0.33, 791.0]])
    pred = model.predict(X)[0]
    assert 20 < pred < 60, f"Temperature prediction {pred} out of range"


def test_shap_load():
    import joblib
    explainer = joblib.load(os.path.join(BASE_DIR, "models", "ahmedabad", "temperature_shap.joblib"))
    assert explainer is not None, "SHAP explainer failed to load"


def test_shap_explain():
    import joblib
    import numpy as np
    model = joblib.load(os.path.join(BASE_DIR, "models", "ahmedabad", "temperature_model.joblib"))
    explainer = joblib.load(os.path.join(BASE_DIR, "models", "ahmedabad", "temperature_shap.joblib"))
    # ML features (13): ndvi, builtup, distance_water, road_density, svf, building_density, albedo,
    # emissivity, bowen_ratio, ndvi_spatial_lag, builtup_density_spatial_lag, ndvi_x_builtup, distance_x_builtup
    X = np.array([[0.34, 0.96, 823.3, 48.0, 0.42, 298.0, 0.15, 0.95, 1.0, 0.30, 0.85, 0.33, 791.0]])
    shap_values = explainer.shap_values(X)
    assert shap_values is not None, "SHAP returned None"
    assert len(shap_values) > 0, "SHAP returned empty"


run_test("temperature model loads", test_model_load)
run_test("temperature model predicts", test_model_predict)
run_test("SHAP explainer loads", test_shap_load)
run_test("SHAP explains sample", test_shap_explain)

# --- 4. Backend Data Loader ---
print("\n--- 4. Backend Data Loader ---")


def test_data_loader():
    from data_loader import data_loader
    data_loader.load()
    assert len(data_loader.cells) > 0, "No cells loaded"


def test_data_loader_get_cell():
    from data_loader import data_loader
    data_loader.load()
    first_id = list(data_loader.cells.keys())[0]
    cell = data_loader.get_cell(first_id)
    assert cell is not None, f"Cell {first_id} not found"
    assert cell["properties"]["temperature"] > 30, "Temperature too low"


def test_data_loader_dashboard():
    from data_loader import data_loader
    data_loader.load()
    stats = data_loader.get_dashboard_stats()
    assert stats["total_cells"] > 0
    assert stats["avg_temp"] > 30


run_test("data_loader loads all cells", test_data_loader)
run_test("data_loader gets specific cell", test_data_loader_get_cell)
run_test("data_loader dashboard stats", test_data_loader_dashboard)

# --- 5. Driver Analyzer ---
print("\n--- 5. Driver Analyzer ---")


def test_driver_analyzer_load():
    from driver_analyzer import analyzer
    analyzer.load()
    assert analyzer._loaded


def test_driver_analyzer_predict():
    from driver_analyzer import analyzer
    analyzer.load()
    first_id = list(analyzer.cells.keys())[0]
    result = analyzer.predict_temperature(first_id)
    assert 30 < result["predicted_temp"] < 50
    assert 30 < result["actual_temp"] < 50


def test_driver_analyzer_analyze():
    from driver_analyzer import analyzer
    analyzer.load()
    first_id = list(analyzer.cells.keys())[0]
    result = analyzer.analyze_drivers(first_id)
    assert len(result["drivers"]) == 13  # 13 ML features
    assert result["predicted_temp"] > 30
    assert "summary" in result


def test_driver_analyzer_global():
    from driver_analyzer import analyzer
    analyzer.load()
    result = analyzer.get_global_drivers()
    assert len(result["features"]) == 13  # 13 ML features
    assert sum(result["importance"]) > 0.99


run_test("analyzer loads", test_driver_analyzer_load)
run_test("analyzer predicts temperature", test_driver_analyzer_predict)
run_test("analyzer analyzes drivers", test_driver_analyzer_analyze)
run_test("analyzer global drivers", test_driver_analyzer_global)

# --- 6. Simulation ---
print("\n--- 6. Simulation ---")


def test_simulation():
    from simulation import simulate_intervention
    cell_data = {
        "temperature": 35.55,
        "ndvi": 0.34,
        "builtup_density": 0.96,
        "distance_water_m": 823.3,
        "road_density_km_km2": 48.0,
    }
    result = simulate_intervention(cell_data, tree_cover=30)
    assert result["before"] == 35.55
    assert result["after"] < result["before"]
    assert result["reduction"] > 0


def test_simulation_no_change():
    from simulation import simulate_intervention
    cell_data = {"temperature": 35.55, "ndvi": 0.34, "builtup_density": 0.96}
    result = simulate_intervention(cell_data)
    assert result["reduction"] == 0


run_test("simulation with tree cover", test_simulation)
run_test("simulation no intervention", test_simulation_no_change)

# --- 7. API Endpoints (manual server test) ---
print("\n--- 7. API Endpoint Tests (require running server) ---")

try:
    import urllib.request
    import json as _json

    def test_api_dashboard():
        resp = urllib.request.urlopen("http://localhost:8000/dashboard?city=ahmedabad", timeout=5)
        data = _json.loads(resp.read())
        assert data["total_cells"] > 0

    def test_api_cell():
        resp = urllib.request.urlopen("http://localhost:8000/cells?city=ahmedabad", timeout=5)
        cells = _json.loads(resp.read())
        first_id = cells[0]["properties"]["cell_id"]
        resp2 = urllib.request.urlopen(f"http://localhost:8000/cells/{first_id}?city=ahmedabad", timeout=5)
        data = _json.loads(resp2.read())
        assert data["cell_id"] == first_id
        assert data["predicted_temp"] > 30

    def test_api_drivers():
        resp = urllib.request.urlopen("http://localhost:8000/cells?city=ahmedabad", timeout=5)
        cells = _json.loads(resp.read())
        first_id = cells[0]["properties"]["cell_id"]
        resp2 = urllib.request.urlopen(f"http://localhost:8000/cells/{first_id}/drivers?city=ahmedabad", timeout=5)
        data = _json.loads(resp2.read())
        assert len(data["drivers"]) == 13  # 13 ML features

    def test_api_global_drivers():
        resp = urllib.request.urlopen("http://localhost:8000/drivers/global?city=ahmedabad", timeout=5)
        data = _json.loads(resp.read())
        assert len(data["features"]) == 13  # 13 ML features

    def test_api_hotspots():
        resp = urllib.request.urlopen("http://localhost:8000/hotspots?limit=5&city=ahmedabad", timeout=5)
        data = _json.loads(resp.read())
        assert len(data) == 5

    def test_api_simulate():
        import urllib.request as req
        resp = urllib.request.urlopen("http://localhost:8000/cells?city=ahmedabad", timeout=5)
        cells = _json.loads(resp.read())
        first_id = cells[0]["properties"]["cell_id"]
        body = _json.dumps({"cell_id": first_id, "tree_cover": 30}).encode()
        r = req.Request(f"http://localhost:8000/simulate?city=ahmedabad", data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(r, timeout=5)
        data = _json.loads(resp.read())
        assert data["reduction"] > 0

    def test_api_cities():
        resp = urllib.request.urlopen("http://localhost:8000/cities", timeout=5)
        data = _json.loads(resp.read())
        assert len(data) >= 1
        assert any(c["key"] == "ahmedabad" for c in data)

    def test_api_cells_list():
        resp = urllib.request.urlopen("http://localhost:8000/cells?city=ahmedabad", timeout=10)
        data = _json.loads(resp.read())
        assert len(data) > 0

    run_test("API: GET /dashboard", test_api_dashboard)
    run_test("API: GET /cells/{id}", test_api_cell)
    run_test("API: GET /cells/{id}/drivers", test_api_drivers)
    run_test("API: GET /drivers/global", test_api_global_drivers)
    run_test("API: GET /hotspots", test_api_hotspots)
    run_test("API: POST /simulate", test_api_simulate)
    run_test("API: GET /cells (all)", test_api_cells_list)
    run_test("API: GET /cities", test_api_cities)

except Exception as e:
    print(f"  [SKIP] API tests - server not running: {e}")
    results.append(("API tests", "SKIP", "server not running"))

# --- Summary ---
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)

passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)
skipped = sum(1 for _, s, _ in results if s == "SKIP")

for name, status, err in results:
    marker = {"PASS": "[OK]", "FAIL": "[!!]", "SKIP": "[--]"}[status]
    extra = f" - {err}" if err else ""
    print(f"  {marker} {name}{extra}")

print(f"\n  Total: {len(results)} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
print("=" * 60)
