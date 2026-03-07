# God's Eye SSA Platform (MVP)

An AI-native data refinery for the orbital commons, shifting the paradigm from legacy TLE/SGP4 models to high-precision Physics-Informed Neural Networks (PINNs) for orbit prediction.

## Overview

This repository contains the MVP (Minimum Viable Product) for the God's Eye Space Situational Awareness (SSA) platform. The primary goal of this MVP is to establish the baseline legacy model (SGP4) and set up the testing harness and pseudo-architecture for the PINN predictor.

## Features

- **SGP4 Baseline Evaluation**: Evaluates mock historical TLE data using the legacy SGP4 propagator.
- **PINN Architecture**: Scaffolds a Physics-Informed Neural Network designed to learn orbital dynamics via a custom physics loss function.
- **FastAPI Backend**: Serves orbital coordinates via a modern, structured API.
- **3D Web Dashboard**: Visualizes orbital trajectories on a 3D Earth using Globe.gl.

## Project Structure

```text
SSA Startup/
│
├── src/
│   ├── api/
│   │   ├── static/         # Frontend Web Application (HTML, JS, CSS)
│   │   ├── schemas.py      # Standardized API Response Models
│   │   └── server.py       # FastAPI Server
│   ├── data/
│   │   ├── ingestion.py    # TLE Parsing and Loading
│   │   └── preprocessing.py# Feature extraction
│   ├── models/
│   │   ├── baseline_sgp4.py# SGP4 Orbit Propagation
│   │   └── pinn_predictor.py# PINN Model Scaffold
│   └── evaluate_mvp.py     # Evaluation Harness Script
│
├── tests/                  # Pytest Unit & Integration Tests (>90% coverage)
├── requirements.txt        # Python Dependencies
└── README.md               # This file
```

## Getting Started

1. **Install Dependencies**
   It is recommended to use a virtual environment.

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the API and Web Dashboard**
   From the `SSA Startup` directory, start the FastAPI server:

   ```bash
   $env:PYTHONPATH="src"; uvicorn src.api.server:app --reload --port 8000
   ```

   Alternatively, run the server using python directly:

   ```bash
   python -m uvicorn src.api.server:app --reload --port 8000
   ```

   Then open your web browser and navigate to `http://localhost:8000/static/index.html`.

3. **Run the Evaluation Script**
   To execute the evaluation harness for the SGP4 and PINN models in the terminal:

   ```bash
   $env:PYTHONPATH="src"; python src/evaluate_mvp.py
   ```

4. **Run Tests**
   This project follows TDD best practices. To run the test suite and verify coverage:

   ```bash
   $env:PYTHONPATH="src"; pytest tests/ -v --cov=src --cov-report=term-missing
   ```

## Next Focus Areas

1. **Connect Historical Data**: Replace the mock TLE data with an actual historical dataset spanning multiple years to begin training the PINN model.
2. **Implement Physics Loss**: Define the true physics-informed gradients within `pinn_predictor.py` to bound the neural network's predictions.
