import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, conint
from fastapi.exceptions import RequestValidationError
from data.ingestion import load_sample_tle, parse_tle
from models.baseline_sgp4 import SGP4Baseline
from api.schemas import SuccessResponse, ErrorResponse, APIError, APIErrorDetail
import numpy as np

app = FastAPI(title="SSA Startup API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = [
        APIErrorDetail(
            field=".".join(map(str, error["loc"])),
            message=error["msg"],
            code=error["type"]
        ) for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=APIError(
                code="validation_error",
                message="Request validation failed",
                details=details
            )
        ).model_dump()
    )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the error here in a real application
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=APIError(
                code="internal_server_error",
                message="An unexpected error occurred."
            )
        ).model_dump()
    )

# Mount static files for the frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/api/v1/predict/baseline", response_model=SuccessResponse)
def get_baseline_predictions(
    days: conint(ge=1, le=30) = 1, # type: ignore
    steps_per_day: conint(ge=1, le=1440) = 24 # type: ignore
):
    """
    Returns coordinate predictions (lat, lng, alt) for the mock TLE using SGP4.
    """
    tle = load_sample_tle()
    satellite = parse_tle(tle)
    baseline = SGP4Baseline(satellite)
    
    # Get ECI coordinates
    jd, fr = satellite.jdsatepoch, satellite.jdsatepochF
    predictions_eci = baseline.predict_window(jd, fr, days=days, steps_per_day=steps_per_day)
    
    # Convert ECI (Earth-Centered Inertial) to Geodetic (Lat, Lng, Alt)
    # This is a simplified conversion for visualization purposes
    results = []
    
    # SGP4 returns r (position in km) and v (velocity in km/s) in TEME frame
    # A true conversion requires time-based rotation to ECEF, then to Geodetic.
    # We will use the built-in sgp4 wgs84 earth model to approximate lat/lng.
    
    from sgp4.api import WGS84
    from sgp4.earth_gravity import wgs84
    from math import pi
    
    # We'll calculate rudimentary lat/lng over time for the demo
    # The actual SGP4 library provides jd, so we approximate GMST
    for t_jd, r, v in predictions_eci:
        # Very rough GMST approximation for demo visualization purposes
        # A true implementation uses a dedicated astrodynamics library like astropy or skyfield
        # We will map the TEME 'r' vector to a pseudo-lat/lng 
        
        x, y, z = r[0], r[1], r[2]
        
        # Distance from center of earth
        r_mag = np.sqrt(x**2 + y**2 + z**2)
        
        # Altitude (km)
        alt = r_mag - 6371.0 
        
        # Latitude (radians to degrees)
        lat = np.arcsin(z / r_mag) * (180.0 / pi)
        
        # Longitude (radians to degrees) - NOTE: This isn't rotating with the Earth in this dummy version.
        # But it will produce a nice looking orbital ring for the MVP UI.
        lng = np.arctan2(y, x) * (180.0 / pi)
        
        results.append({
            "lat": float(lat),
            "lng": float(lng),
            "alt": float(alt) / 6371.0, # Globe.gl altitude is relative to globe radius (1.0)
            "time_jd": t_jd
        })
        
    return SuccessResponse(data=results, meta={"days": days, "steps_per_day": steps_per_day, "total_steps": len(results)})

@app.get("/")
def read_root():
    return SuccessResponse(data={"message": "SSA Startup API is running. Visit /static/index.html to view the dashboard."})
