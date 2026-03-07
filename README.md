# God's Eye — Space Situational Awareness Platform (v2)

A production-grade AI data refinery for the orbital commons. Fuses real orbital data from **CelesTrak** with live space weather from **NOAA SWPC** to predict satellite trajectories using SGP4 and (soon) Physics-Informed Neural Networks.

## Live Data Sources

| Source | API | Data | Cross-Checks |
|--------|-----|------|---------------|
| **CelesTrak** | `celestrak.org/NORAD/elements/gp.php` | GP orbital elements (JSON) for all tracked RSOs | Ground truth state vectors |
| **NOAA SWPC** | `services.swpc.noaa.gov/json/` | Kp index, F10.7 solar flux | Atmospheric drag driver |

## Features

- **Real Satellite Catalog**: Browse and select from CelesTrak's live database (Space Stations, Starlink, Debris, etc.)
- **Live Space Weather**: Real-time Kp index and F10.7 solar flux with storm-level classification
- **SGP4 Orbit Propagation**: Predict any tracked satellite's trajectory over 1–30 days
- **3D Globe Visualization**: Render orbital paths on an interactive Globe.gl Earth
- **PINN Architecture**: Scaffolded Physics-Informed Neural Network for drag-aware predictions
- **81%+ Test Coverage**: TDD-compliant with 26 passing tests

## Project Structure

```
SSA Startup/
├── src/
│   ├── api/
│   │   ├── static/              # Web Dashboard (HTML/CSS/JS)
│   │   ├── schemas.py           # Pydantic response models
│   │   └── server.py            # FastAPI server (v2)
│   ├── data/
│   │   ├── celestrak_client.py  # CelesTrak GP/OMM JSON client
│   │   ├── space_weather_client.py  # NOAA SWPC Kp/F10.7 client
│   │   ├── ingestion.py         # Mock TLE loader
│   │   └── preprocessing.py     # Feature extraction
│   ├── models/
│   │   ├── baseline_sgp4.py     # SGP4 orbit propagation
│   │   └── pinn_predictor.py    # PINN model scaffold
│   └── evaluate_mvp.py          # Evaluation harness
├── tests/                       # 26 tests, 81% coverage
├── requirements.txt
├── .gitignore
└── README.md
```

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the dashboard
$env:PYTHONPATH="src"; uvicorn src.api.server:app --reload --port 8000

# 4. Open browser
# http://localhost:8000/static/index.html
```

## Running Tests

```bash
$env:PYTHONPATH="src"; pytest tests/ -v --cov=src --cov-report=term-missing
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/catalog?group=stations` | GET | List satellites from CelesTrak |
| `/api/v1/groups` | GET | Available satellite groups |
| `/api/v1/space-weather` | GET | Current Kp, F10.7, storm level |
| `/api/v1/predict/baseline?norad_id=25544&days=1` | GET | SGP4 trajectory prediction |

## Roadmap

- [ ] PINN training loop with real drag-based physics loss
- [ ] Cross-validation module (SGP4 error vs. geomagnetic activity)
- [ ] Multi-satellite simultaneous rendering
- [ ] Conjunction assessment module
