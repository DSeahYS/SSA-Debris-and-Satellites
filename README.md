# God's Eye — Space Situational Awareness Platform

A production-grade AI data refinery for the orbital commons. Fuses real orbital data from **CelesTrak** with live space weather from **NOAA SWPC** to deliver mission-critical conjunction assessment, orbit prediction, and a fully interactive 3D digital twin of Earth.

## 3D Digital Twin

The platform features a **CesiumJS-powered 3D globe** with:
- **Seamless zoom** from orbital altitude down to individual city streets
- **Bing Maps Aerial with Labels** — high-resolution, up-to-date satellite imagery
- **3D OSM Buildings** — efficient streaming of worldwide building geometry at street level
- **World terrain** — realistic topography with elevation data
- **Click-to-identify** — click any location on the globe to see lat/lng coordinates and AI-powered location identification

## Live Data Sources

| Source | API | Data |
|--------|-----|------|
| **CelesTrak** | `celestrak.org/NORAD/elements/gp.php` | GP orbital elements (JSON) for all tracked RSOs |
| **NOAA SWPC** | `services.swpc.noaa.gov/json/` | Kp, F10.7, solar wind, X-ray, proton flux |
| **Cesium Ion** | `cesium.com` | 3D terrain, imagery, OSM Buildings |
| **OpenRouter AI** | `openrouter.ai` | Location identification via LLM |

## Features

### Orbital Tracking
- **Real Satellite Catalog**: Browse CelesTrak's live database (Space Stations, Starlink, Debris, etc.)
- **Multi-Satellite Tracking**: Track multiple satellites simultaneously with 8 distinct color-coded orbital paths
- **Scan Swath Visualization**: Togglable sensor footprint corridors showing ground coverage based on altitude and FOV
- **SGP4 Orbit Propagation**: Predict any tracked satellite's trajectory over 1–30 days

### Conjunction Assessment
- **Automated Screening**: Screen primary satellite against catalog objects with configurable thresholds
- **RIC Miss Distance**: Radial, In-track, Cross-track decomposition for each close approach
- **Collision Probability**: Estimated Pc with risk-level classification (Critical/Warning/Caution/Nominal)
- **Maneuver Recommendations**: Δv, fuel cost, execution timing for avoidance maneuvers
- **CDM Export**: Generate CCSDS-compliant Conjunction Data Messages in KVN format

### Space Environment
- **6 NOAA Feeds**: Kp index, F10.7 flux, solar wind (speed/density/Bt/Bz), X-ray class, proton flux
- **Storm Classification**: Real-time geomagnetic storm level assessment
- **Operator Advisories**: AI-generated operational guidance based on space weather conditions
- **Decay Predictions**: Atmospheric drag-based re-entry forecasting driven by live weather data

### 3D Globe Interaction
- **Click Satellites**: Inspect orbital parameters, set as primary, or add to multi-track
- **Click Ground**: Shows coordinates with AI-powered identification (city, region, country, or ocean)
- **Geocoder Search**: Fly to any address or city name worldwide
- **Street-Level Zoom**: 3D buildings render efficiently via Cesium 3D Tiles

## Project Structure

```
SSA Startup/
├── src/
│   ├── api/
│   │   ├── static/              # Web Dashboard (HTML/CSS/JS + CesiumJS)
│   │   │   ├── index.html       # Dashboard layout
│   │   │   ├── app.js           # Application controller (Cesium, tracking, AI)
│   │   │   └── style.css        # Military C2 interface styling
│   │   ├── schemas.py           # Pydantic response models
│   │   └── server.py            # FastAPI server (v5)
│   ├── data/
│   │   ├── celestrak_client.py  # CelesTrak GP/OMM JSON client
│   │   ├── space_weather_client.py  # NOAA SWPC multi-feed client
│   │   ├── ingestion.py         # Mock TLE loader
│   │   └── preprocessing.py     # Feature extraction
│   ├── models/
│   │   ├── baseline_sgp4.py     # SGP4 orbit propagation
│   │   ├── conjunction.py       # Conjunction screening & Pc estimation
│   │   ├── decay_predictor.py   # Atmospheric decay prediction
│   │   ├── advisories.py        # Operator advisory generation
│   │   ├── cdm_generator.py     # CCSDS CDM generation
│   │   ├── transforms.py        # ECI→ECEF→Geodetic transforms
│   │   └── pinn_predictor.py    # PINN model scaffold
│   └── evaluate_mvp.py          # Evaluation harness
├── tests/                       # Test suite
├── .env                         # API keys (not committed)
├── .gitignore
├── requirements.txt
└── README.md
```

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
# Create .env file with:
#   OPENROUTER_API_KEY=your_key_here
#   OPENROUTER_MODEL=z-ai/glm-4.5-air:free
#   CESIUM_ION_TOKEN=your_cesium_token_here

# 4. Start the dashboard
$env:PYTHONPATH="src"; uvicorn src.api.server:app --reload --port 8000

# 5. Open browser
# http://localhost:8000/static/index.html
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/catalog?group=stations` | GET | List satellites from CelesTrak |
| `/api/v1/groups` | GET | Available satellite groups |
| `/api/v1/search?q=ISS` | GET | Search satellites by name or NORAD ID |
| `/api/v1/space-weather` | GET | Current Kp, F10.7, solar wind, X-ray, proton |
| `/api/v1/positions?group=stations` | GET | Real-time lat/lng/alt for all satellites in group |
| `/api/v1/predict/baseline?norad_id=25544&days=1` | GET | SGP4 trajectory prediction |
| `/api/v1/conjunctions?norad_id=25544&threshold_km=50` | GET | Conjunction screening |
| `/api/v1/cdm?norad_id=25544&secondary_id=36508` | GET | Generate CDM (JSON or KVN) |
| `/api/v1/decay?group=fengyun-1c-debris` | GET | Decay/re-entry predictions |
| `/api/v1/advisories` | GET | Operator advisories from space weather |
| `/api/v1/satellite/{norad_id}` | GET | Detailed satellite info |
| `/api/v1/location-info?lat=1.35&lng=103.82` | GET | AI-powered location identification |
| `/api/v1/config` | GET | Client configuration (Cesium token) |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CESIUM_ION_TOKEN` | Yes | Cesium Ion access token for 3D globe imagery and terrain |
| `OPENROUTER_API_KEY` | Optional | OpenRouter API key for AI location identification |
| `OPENROUTER_MODEL` | Optional | AI model to use (default: `z-ai/glm-4.5-air:free`) |

## Running Tests

```bash
$env:PYTHONPATH="src"; pytest tests/ -v --cov=src --cov-report=term-missing
```
