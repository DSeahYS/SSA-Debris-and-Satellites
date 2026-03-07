"""
God's Eye SSA Platform — FastAPI Server (v2)
Serves real satellite catalog, space weather data, and orbital predictions.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import conint
from fastapi.exceptions import RequestValidationError

from data.ingestion import load_sample_tle, parse_tle
from data.celestrak_client import fetch_gp_data, parse_omm_records, get_satellite_catalog, SATELLITE_GROUPS
from data.space_weather_client import get_current_space_weather
from models.baseline_sgp4 import SGP4Baseline
from api.schemas import SuccessResponse, ErrorResponse, APIError, APIErrorDetail

import numpy as np
from math import pi
from sgp4.api import Satrec, WGS72

app = FastAPI(title="God's Eye SSA Platform", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Error Handlers ---

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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=APIError(
                code="internal_server_error",
                message=str(exc)
            )
        ).model_dump()
    )


# --- Static Files ---

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# --- API Endpoints ---

@app.get("/api/v1/catalog")
def get_catalog(group: str = Query("stations", description="Satellite group from CelesTrak")):
    """Returns a list of tracked satellites for a given group."""
    catalog = get_satellite_catalog(group)
    return SuccessResponse(
        data=catalog,
        meta={"group": group, "total": len(catalog), "available_groups": list(SATELLITE_GROUPS.keys())}
    )


@app.get("/api/v1/groups")
def get_groups():
    """Returns the available satellite group names and descriptions."""
    return SuccessResponse(data=SATELLITE_GROUPS)


@app.get("/api/v1/space-weather")
def get_space_weather():
    """Returns the current space weather conditions (Kp, F10.7, storm level)."""
    weather = get_current_space_weather()
    return SuccessResponse(data={
        "timestamp": weather.timestamp,
        "kp_index": weather.kp_index,
        "dst_index": weather.dst_index,
        "f107_flux": weather.f107_flux,
        "storm_level": weather.storm_level,
    })


@app.get("/api/v1/predict/baseline")
def get_baseline_predictions(
    norad_id: int = Query(None, description="NORAD Catalog ID (omit for mock data)"),
    group: str = Query("stations", description="CelesTrak group to search"),
    days: conint(ge=1, le=30) = 1,  # type: ignore
    steps_per_day: conint(ge=1, le=1440) = 24  # type: ignore
):
    """
    Returns SGP4 coordinate predictions (lat, lng, alt) for a satellite.
    If norad_id is provided, fetches real data from CelesTrak.
    Otherwise uses mock TLE data.
    """
    if norad_id:
        # Fetch real satellite data from CelesTrak
        raw = fetch_gp_data(group)
        omm_records = parse_omm_records(raw)
        target = None
        for rec in omm_records:
            if rec.norad_cat_id == norad_id:
                target = rec
                break
        if not target:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error=APIError(
                        code="not_found",
                        message=f"Satellite with NORAD ID {norad_id} not found in group '{group}'."
                    )
                ).model_dump()
            )

        # Build Satrec from OMM data
        satellite = Satrec()
        # Use sgp4init with WGS72 gravity model
        from sgp4.api import WGS72
        from sgp4 import exporter
        # Reconstruct a TLE from the OMM record and parse it
        # CelesTrak JSON includes raw TLE lines for compatibility
        # We'll use the OMM fields directly via sgp4init
        epoch_year = int(target.epoch[:4])
        epoch_month = int(target.epoch[5:7])
        epoch_day = int(target.epoch[8:10])
        epoch_hour = int(target.epoch[11:13])
        epoch_minute = int(target.epoch[14:16])
        epoch_second = float(target.epoch[17:])

        from sgp4.conveniences import jday
        jd, fr = jday(epoch_year, epoch_month, epoch_day, epoch_hour, epoch_minute, epoch_second)

        satellite.sgp4init(
            WGS72,
            'i',  # improved mode
            target.norad_cat_id,
            (jd + fr) - 2433281.5,  # epoch in days since 1949 Dec 31 00:00 UT
            target.bstar,
            0.0,  # ndot (not used in sgp4init)
            0.0,  # nddot (not used in sgp4init)
            target.eccentricity,
            target.arg_of_pericenter * pi / 180.0,
            target.inclination * pi / 180.0,
            target.mean_anomaly * pi / 180.0,
            target.mean_motion * 2.0 * pi / 1440.0,  # rev/day to rad/min
            target.ra_of_asc_node * pi / 180.0,
        )
        sat_name = target.object_name
    else:
        # Use mock data
        tle = load_sample_tle()
        satellite = parse_tle(tle)
        jd, fr = satellite.jdsatepoch, satellite.jdsatepochF
        sat_name = "MOCK-SAT"

    # Propagate using SGP4
    baseline = SGP4Baseline(satellite)
    predictions_eci = baseline.predict_window(jd, fr, days=days, steps_per_day=steps_per_day)

    results = []
    for t_jd, r, v in predictions_eci:
        x, y, z = r[0], r[1], r[2]
        r_mag = np.sqrt(x**2 + y**2 + z**2)
        alt = r_mag - 6371.0
        lat = np.arcsin(z / r_mag) * (180.0 / pi)
        lng = np.arctan2(y, x) * (180.0 / pi)

        results.append({
            "lat": float(lat),
            "lng": float(lng),
            "alt": float(alt) / 6371.0,
            "time_jd": t_jd
        })

    return SuccessResponse(
        data=results,
        meta={
            "satellite": sat_name,
            "norad_id": norad_id,
            "days": days,
            "steps_per_day": steps_per_day,
            "total_steps": len(results),
            "source": "celestrak" if norad_id else "mock"
        }
    )


@app.get("/")
def read_root():
    return SuccessResponse(data={
        "message": "God's Eye SSA Platform API v2. Visit /static/index.html for the dashboard.",
        "endpoints": ["/api/v1/catalog", "/api/v1/groups", "/api/v1/space-weather", "/api/v1/predict/baseline"]
    })
