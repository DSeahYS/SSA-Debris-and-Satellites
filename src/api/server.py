"""
God's Eye SSA Platform — FastAPI Server (v3 Operational)
Conjunction assessment, satellite search, live space weather, orbital predictions.
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
from dataclasses import asdict

from data.ingestion import load_sample_tle, parse_tle
from data.celestrak_client import fetch_gp_data, parse_omm_records, get_satellite_catalog, SATELLITE_GROUPS
from data.space_weather_client import get_current_space_weather
from models.baseline_sgp4 import SGP4Baseline
from models.conjunction import screen_conjunctions, estimate_avoidance_maneuver, CloseApproach
from api.schemas import SuccessResponse, ErrorResponse, APIError, APIErrorDetail

import numpy as np
from math import pi
from sgp4.api import Satrec, WGS72
from sgp4.conveniences import jday

app = FastAPI(title="God's Eye SSA Platform", version="3.0.0")

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
            error=APIError(code="validation_error", message="Request validation failed", details=details)
        ).model_dump()
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=APIError(code="internal_server_error", message=str(exc))
        ).model_dump()
    )


# --- Static Files ---

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# --- Helpers ---

def _find_omm_by_norad(norad_id: int, groups: list = None):
    """Search for a satellite by NORAD ID across CelesTrak groups."""
    if groups is None:
        groups = ["stations", "active", "visual", "last-30-days"]
    for group in groups:
        raw = fetch_gp_data(group)
        records = parse_omm_records(raw)
        for rec in records:
            if rec.norad_cat_id == norad_id:
                return rec, group
    return None, None


def _build_satrec(omm):
    """Build Satrec from OMM for propagation."""
    sat = Satrec()
    e = omm.epoch
    yr, mo, dy = int(e[:4]), int(e[5:7]), int(e[8:10])
    hr, mi, sc = int(e[11:13]), int(e[14:16]), float(e[17:])
    jd, fr = jday(yr, mo, dy, hr, mi, sc)
    sat.sgp4init(
        WGS72, 'i', omm.norad_cat_id,
        (jd + fr) - 2433281.5,
        omm.bstar, 0.0, 0.0,
        omm.eccentricity,
        omm.arg_of_pericenter * pi / 180.0,
        omm.inclination * pi / 180.0,
        omm.mean_anomaly * pi / 180.0,
        omm.mean_motion * 2.0 * pi / 1440.0,
        omm.ra_of_asc_node * pi / 180.0,
    )
    return sat, jd, fr


# --- API Endpoints ---

@app.get("/api/v1/catalog")
def get_catalog(group: str = Query("stations")):
    """Returns satellites for a given CelesTrak group."""
    catalog = get_satellite_catalog(group)
    return SuccessResponse(
        data=catalog,
        meta={"group": group, "total": len(catalog), "available_groups": list(SATELLITE_GROUPS.keys())}
    )


@app.get("/api/v1/groups")
def get_groups():
    return SuccessResponse(data=SATELLITE_GROUPS)


@app.get("/api/v1/search")
def search_satellites(q: str = Query(..., min_length=1, description="Search by name or NORAD ID")):
    """
    Search for satellites across multiple CelesTrak groups.
    Searches by name (case-insensitive) or NORAD catalog ID.
    """
    query = q.strip().upper()
    results = []
    seen_ids = set()
    search_groups = ["stations", "active", "visual", "starlink", "weather", "geo",
                     "cosmos-2251-debris", "fengyun-1c-debris", "last-30-days"]

    for group in search_groups:
        try:
            raw = fetch_gp_data(group)
            records = parse_omm_records(raw)
            for rec in records:
                if rec.norad_cat_id in seen_ids:
                    continue
                # Match by name or NORAD ID
                if query in rec.object_name.upper() or query == str(rec.norad_cat_id):
                    seen_ids.add(rec.norad_cat_id)
                    results.append({
                        "norad_id": rec.norad_cat_id,
                        "name": rec.object_name,
                        "group": group,
                        "periapsis_km": round(rec.periapsis_km, 1),
                        "apoapsis_km": round(rec.apoapsis_km, 1),
                        "inclination": round(rec.inclination, 2),
                        "period_min": round(rec.period_min, 2),
                        "epoch": rec.epoch,
                    })
        except Exception:
            continue  # If a group fails, keep searching others

    return SuccessResponse(data=results, meta={"query": q, "total": len(results)})


@app.get("/api/v1/space-weather")
def get_space_weather():
    weather = get_current_space_weather()
    return SuccessResponse(data={
        "timestamp": weather.timestamp,
        "kp_index": weather.kp_index,
        "dst_index": weather.dst_index,
        "f107_flux": weather.f107_flux,
        "storm_level": weather.storm_level,
    })


@app.get("/api/v1/conjunctions")
def get_conjunctions(
    norad_id: int = Query(..., description="NORAD ID of your primary satellite"),
    threshold_km: float = Query(50.0, ge=1, le=500, description="Miss distance threshold (km)"),
    hours: int = Query(24, ge=1, le=168, description="Screening window (hours)"),
    screen_groups: str = Query("stations,active,visual", description="Comma-separated CelesTrak groups to screen against"),
):
    """
    Run conjunction screening for a primary satellite against catalog objects.
    Returns close approaches with RIC miss distance decomposition.
    """
    # Find primary
    primary_omm, primary_group = _find_omm_by_norad(norad_id)
    if primary_omm is None:
        return JSONResponse(status_code=404, content=ErrorResponse(
            error=APIError(code="not_found", message=f"NORAD ID {norad_id} not found.")
        ).model_dump())

    # Build secondary catalog
    secondaries = []
    for group in screen_groups.split(","):
        group = group.strip()
        try:
            raw = fetch_gp_data(group)
            records = parse_omm_records(raw)
            secondaries.extend(records)
        except Exception:
            continue

    # Screen
    approaches = screen_conjunctions(
        primary_omm, secondaries,
        hours=hours, step_seconds=60, threshold_km=threshold_km
    )

    # Build response with maneuver recs for each approach
    results = []
    for a in approaches:
        rec = asdict(a)
        if a.risk_level in ("critical", "warning"):
            rec["maneuver"] = estimate_avoidance_maneuver(a)
        results.append(rec)

    return SuccessResponse(
        data=results,
        meta={
            "primary": primary_omm.object_name,
            "norad_id": norad_id,
            "threshold_km": threshold_km,
            "hours": hours,
            "total_screened": len(secondaries),
            "close_approaches": len(results),
        }
    )


@app.get("/api/v1/predict/baseline")
def get_baseline_predictions(
    norad_id: int = Query(None),
    group: str = Query("stations"),
    days: conint(ge=1, le=30) = 1,  # type: ignore
    steps_per_day: conint(ge=1, le=1440) = 24  # type: ignore
):
    """SGP4 orbit prediction — real satellite or mock data."""
    if norad_id:
        primary_omm, found_group = _find_omm_by_norad(norad_id, [group])
        if primary_omm is None:
            # Try broader search
            primary_omm, found_group = _find_omm_by_norad(norad_id)
        if primary_omm is None:
            return JSONResponse(status_code=404, content=ErrorResponse(
                error=APIError(code="not_found", message=f"NORAD ID {norad_id} not found.")
            ).model_dump())
        satellite, jd, fr = _build_satrec(primary_omm)
        sat_name = primary_omm.object_name
    else:
        tle = load_sample_tle()
        satellite = parse_tle(tle)
        jd, fr = satellite.jdsatepoch, satellite.jdsatepochF
        sat_name = "MOCK-SAT"

    baseline = SGP4Baseline(satellite)
    predictions_eci = baseline.predict_window(jd, fr, days=days, steps_per_day=steps_per_day)

    results = []
    for t_jd, r, v in predictions_eci:
        x, y, z = r[0], r[1], r[2]
        r_mag = np.sqrt(x**2 + y**2 + z**2)
        alt = r_mag - 6371.0
        lat = np.arcsin(z / r_mag) * (180.0 / pi)
        lng = np.arctan2(y, x) * (180.0 / pi)
        results.append({"lat": float(lat), "lng": float(lng), "alt": float(alt) / 6371.0, "time_jd": t_jd})

    return SuccessResponse(data=results, meta={
        "satellite": sat_name, "norad_id": norad_id,
        "days": days, "steps_per_day": steps_per_day, "total_steps": len(results),
        "source": "celestrak" if norad_id else "mock"
    })


@app.get("/")
def read_root():
    return SuccessResponse(data={
        "message": "God's Eye SSA Platform v3 — Operational Conjunction Assessment",
        "endpoints": ["/api/v1/search", "/api/v1/conjunctions", "/api/v1/catalog",
                      "/api/v1/space-weather", "/api/v1/predict/baseline"]
    })
