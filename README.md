# UrbanCool AI — ISRO Hackathon Project

UrbanCool AI is a geospatial machine learning platform designed for **Urban Heat Island (UHI) mitigation and cooling strategy simulation**. It allows urban planners, researchers, and developers to analyze land surface temperatures, identify high-heat risk zones, explain the spatial drivers of heat using SHAP explainability, and simulate mitigation interventions (such as tree cover expansion, cool roofs, and green roofs) in real-time.

---

## 🏗️ System Architecture & Workflow

The platform follows a decoupled architecture, dividing responsibilities between a geospatial data pipeline, a FastAPI machine learning backend, and a React-based interactive web frontend.

```mermaid
flowchart TD
    subgraph Data Pipeline [Data Processing & Model Training]
        D1[Raw NetCDF/GeoJSON Data] -->|Aggregate| D2[master_grid.geojson]
        D2 -->|Pipeline Merge & Feature Engineering| D3[heat_grid.geojson]
        D3 -->|Train Ridge Regressor| D4[temperature_model.joblib]
        D3 -->|Train SHAP Explainer| D5[temperature_shap.joblib]
    end

    subgraph Backend [FastAPI Backend Server]
        B1[data_loader.py] <---|Loads JSON/GeoJSON| D3
        B2[driver_analyzer.py] <---|Loads ML Weights| D4 & D5
        B3[simulation.py] -->|Intervention Math| B4[FastAPI Route Handlers]
        B1 & B2 --> B4
    end

    subgraph Frontend [React Vite + Tailwind Client]
        F1[HeatMap Page] <-->|Fetch geojson & drivers| B4
        F2[Simulator Page] <-->|Post parameters| B4
        F3[Dashboard Page] <-->|Fetch global stats & importance| B4
    end

    classDef pipe fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;
    classDef back fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;
    classDef front fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    class Data Pipeline pipe;
    class Backend back;
    class Frontend front;
```

### End-to-End Workflow
1. **Grid Generation & Ingestion**: The data pipeline generates a uniform grid (500m cells) over target cities (defaulting to Ahmedabad) and populates spatial indices (NDVI, built-up density, distance to water, road density) alongside weather observations.
2. **Model Training & Explanations**: A Ridge Regression model is trained on spatial features to predict local temperatures. Post-training, a SHAP (SHapley Additive exPlanations) explainer calculates the feature importances (e.g., how much built-up density increases heat vs. how much vegetation cools it).
3. **API Serving**: The FastAPI server loads the processed geospatial grid and pre-trained models into memory. It provides endpoints for map rendering, cell lookups, feature drivers, and real-time intervention simulations.
4. **Interactive Dashboard & Client**: The frontend displays the grid on a React Leaflet map. Users can click any cell to inspect its attributes, view its SHAP local drivers, simulate cooling scenarios, and see global charts (risk categories, feature importances, and hotspots).

---

## 📂 File Structure

Below is an overview of the key directories and files in the repository:

```text
ISRO Hackathon/
├── README.md                          # Main project documentation (this file)
├── Design.md                          # Brand style guidelines (Claude.com reference style)
├── urban-cool/                        # Backend Application & Geospatial Pipeline
│   ├── run_server.py                  # Entrypoint to run the FastAPI backend server
│   ├── backend/                       # Python FastAPI Backend
│   │   ├── main.py                    # API routers, endpoints, and CORS config
│   │   ├── data_loader.py             # Geospatial in-memory loader & aggregator
│   │   ├── driver_analyzer.py         # SHAP explanation and Ridge prediction loader
│   │   ├── simulation.py              # Math modules for green/cool roof & tree cover simulations
│   │   ├── models.py                  # Pydantic schemas for request/response validation
│   │   ├── requirements.txt           # Python backend dependencies
│   │   └── config/
│   │       └── interventions.json     # Mitigation cooling coefficients (C° reduction per %)
│   ├── data/                          # Data Directory
│   │   ├── raw/                       # Original inputs (ERA5 netCDF, OSM geojsons)
│   │   ├── intermediate/              # Mid-pipeline aggregated records
│   │   ├── processed/                 # Output geojsons (heat_grid.geojson - the map source)
│   │   └── scripts/                   # Extraction, merging, and ML training scripts
│   │       ├── master_grid.py         # Generates base geospatial grid for target cities
│   │       ├── feature_extraction.py  # Calculates spatial indices (NDVI, water proximity)
│   │       ├── unified_pipeline.py    # Merges all datasets into a single GeoJSON grid
│   │       └── train_temperature_model.py # Trains temperature Ridge model & SHAP explainer
│   ├── models/                        # Serialized ML files
│   │   ├── temperature_model.joblib   # Trained Ridge regression weights
│   │   └── temperature_shap.joblib    # Serialized SHAP explainer
│   └── tests/
│       └── test_all.py                # Pipeline, data, backend, and API mock tests
│
└── urban-cool-frontend/               # React + Vite Frontend Application
    ├── package.json                   # Node.js dependencies
    ├── vite.config.js                 # Vite bundler configs + API proxy to backend
    ├── index.html                     # Frontend entrypoint HTML
    └── src/
        ├── main.jsx                   # React bootstrapper
        ├── App.jsx                    # Root view switcher (tab navigation router)
        ├── index.css                  # Tailwind theme tokens and font imports
        ├── api.js                     # Fetch client wrapper for Backend communication
        ├── components/
        │   ├── Navbar.jsx             # Fixed top layout navigator
        │   ├── CellPanel.jsx          # Sidebar displaying cell details & SHAP drivers
        │   └── CitySelector.jsx       # City dropdown selector
        └── pages/
            ├── HeatMap.jsx            # Interactive grid map rendering with Leaflet
            ├── Simulator.jsx          # Slide controls for real-time cooling simulations
            ├── Optimizer.jsx          # Budget-constrained optimization with best/worst comparison
            ├── Priority.jsx           # Risk-ranked cell table with sorting and filtering
            └── Dashboard.jsx          # Recharts visualizations (pie charts, bar charts, line trends)
```

---

## 🛠️ Setup & Installation

Follow these steps to run both the backend API and the frontend locally.

### Prerequisites
* Python 3.8 or higher
* Node.js 18.x or higher + npm

### 1. Backend Server Setup
Navigate into the backend project folder, set up a virtual environment, install python libraries, and run the server.

```bash
# Navigate to the backend directory
cd urban-cool

# Create and activate a virtual environment
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On macOS/Linux:
source venv/bin/activate

# Install required python packages
pip install -r backend/requirements.txt
# Note: For model inference and SHAP computations, make sure to install:
pip install numpy pandas scikit-learn shap joblib

# Start the FastAPI server (running on http://localhost:8000)
python run_server.py
```

### 2. Frontend Client Setup
Open a new terminal window/tab, navigate to the frontend directory, install Node packages, and run the hot-reloading development server.

```bash
# Navigate to the frontend directory
cd urban-cool-frontend

# Install node dependencies
npm install

# Start the Vite development server (running on http://localhost:5173)
# It automatically proxies any request to /api to the Python backend on http://localhost:8000
npm run dev
```

### 3. Running Verification Tests
To run the automated test suite verifying data availability, ML model loads, SHAP output calculations, and backend routes, execute:

```bash
# With python environment activated inside the urban-cool directory:
python tests/test_all.py
```

---

## 📊 Backend API Reference

The backend runs on port `8000`. Key endpoints are:

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/cells` | `GET` | Returns basic details and polygon geometry of all grid cells for Mapbox/Leaflet rendering. |
| `/cells/{cell_id}` | `GET` | Fetches full attributes (NDVI, Built-up density, water proximity, wind speed, solar radiation) of a single cell. |
| `/cells/{cell_id}/drivers` | `GET` | Calculates SHAP values and outputs a text summary of why that cell is hot/cool. |
| `/hotspots` | `GET` | Returns list of hottest cells (sorted by temperature), filterable by `min_temp` query parameter. |
| `/simulate` | `POST` | Runs cooling math on a cell given `tree_cover`, `cool_roof`, and `green_roof` percentages. |
| `/dashboard` | `GET` | Returns aggregated metrics (high risk cell count, avg/max temperature) for display cards. |
| `/drivers/global` | `GET` | Computes global feature importance across all cells for Recharts bar charts. |

---

## ⚙️ How to Make Changes

Here is how you can customize or extend the platform depending on your needs:

### 1. Adding or Modifying a Target City
To run simulations or train models for a new city:
1. Open [master_grid.py](file:///h:/Projects/Projects/ISRO%20Hackathon/urban-cool/data/scripts/master_grid.py).
2. Under the `CITIES` dictionary (line 18), add your city with its coordinate bounding box (`lat_min`, `lat_max`, `lon_min`, `lon_max`) and a 3-letter uppercase `prefix`.
3. Open [feature_extraction.py](file:///h:/Projects/Projects/ISRO%20Hackathon/urban-cool/data/scripts/feature_extraction.py).
4. Add your city details in `CITY_CONFIGS` (line 191) specifying simulated coordinates of parks and river/lakes to activate cooling heuristics.
5. Re-run the data generation script:
   ```bash
   python data/scripts/run_pipeline.py --city your_city_name
   ```

### 2. Modifying Simulation Cooling Coefficients
The cooling reductions are configured via a JSON config file.
1. Open [interventions.json](file:///h:/Projects/Projects/ISRO%20Hackathon/urban-cool/backend/config/interventions.json).
2. Adjust `temp_reduction_per_percent` for tree cover, cool roofs, or green roofs.
   * *Example:* Changing `tree_cover.temp_reduction_per_percent` to `0.1` means each 1% increase in canopy reduces the temperature by `0.1°C`.
3. The backend dynamically loads these coefficients during `/simulate` POST requests—no restart is necessary if uvicorn is in reload mode.

### 3. Re-training the Machine Learning Models
If you enrich the processed GeoJSON file with new satellite columns:
1. Ensure your feature is present in the `FEATURES` list of [train_temperature_model.py](file:///h:/Projects/Projects/ISRO%20Hackathon/urban-cool/data/scripts/train_temperature_model.py) (line 32) and [driver_analyzer.py](file:///h:/Projects/Projects/ISRO%20Hackathon/urban-cool/backend/driver_analyzer.py) (line 20).
2. Run the training script:
   ```bash
   python data/scripts/train_temperature_model.py
   ```
3. This saves updated model weights (`temperature_model.joblib`) and SHAP calculations (`temperature_shap.joblib`) directly into the `models/` directory, which the FastAPI app consumes immediately.

### 4. Updating Styling & Theme
The frontend uses a warm cream-and-coral design system inspired by Anthropic/Claude's editorial aesthetic.
* All theme tokens are defined in [index.css](urban-cool-frontend/src/index.css) under the `@theme` block using CSS custom properties.
* Typography uses **Cormorant Garamond** (serif headlines), **Inter** (body text), and **JetBrains Mono** (data/code values).
* Core palette:
  ```css
  --color-canvas: #faf9f5;       /* Warm cream background */
  --color-surface-card: #ffffff;  /* Card surfaces */
  --color-primary: #cc785c;       /* Coral primary */
  --color-primary-active: #a9583e; /* Coral hover/active */
  --color-ink: #1b1917;          /* Dark headlines */
  --color-body: #373530;         /* Body text */
  ```
* Cards use `bg-surface-card border border-hairline rounded-xl` (12px radius, hairline borders, no shadows).
* To change the accent color, update `--color-primary` and `--color-primary-active` in the theme block.
