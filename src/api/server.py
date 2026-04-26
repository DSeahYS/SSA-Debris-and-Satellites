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
from dotenv import load_dotenv

load_dotenv()

from data.ingestion import load_sample_tle, parse_tle
from data.celestrak_client import fetch_gp_data, parse_omm_records, get_satellite_catalog, SATELLITE_GROUPS
from data.space_weather_client import get_current_space_weather
from models.baseline_sgp4 import SGP4Baseline
from models.conjunction import screen_conjunctions, estimate_avoidance_maneuver, CloseApproach
from models.transforms import eci_to_geodetic
from models.decay_predictor import predict_reentry, get_decaying_objects
from models.advisories import generate_advisories
from models.cdm_generator import generate_cdm, format_cdm_kvn
from api.schemas import SuccessResponse, ErrorResponse, APIError, APIErrorDetail

import numpy as np
from math import pi
from sgp4.api import Satrec, WGS72
from sgp4.conveniences import jday
from datetime import datetime

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
        "solar_wind_speed": weather.solar_wind_speed,
        "solar_wind_density": weather.solar_wind_density,
        "solar_wind_bt": weather.solar_wind_bt,
        "solar_wind_bz": weather.solar_wind_bz,
        "xray_class": weather.xray_class,
        "xray_flux": weather.xray_flux,
        "proton_gt10mev": weather.proton_gt10mev,
        "proton_gt100mev": weather.proton_gt100mev,
    }, meta={
        "sources": ["NOAA/SWPC Kp", "NOAA/SWPC F10.7", "DSCOVR Solar Wind", "GOES X-Ray", "GOES Proton"],
    })


@app.get("/api/v1/positions")
def get_satellite_positions(group: str = Query("stations")):
    """
    Compute current lat/lng/alt for all satellites in a CelesTrak group.
    Uses proper ECI→ECEF→Geodetic transform with GMST rotation.
    """
    raw = fetch_gp_data(group)
    records = parse_omm_records(raw)
    now = datetime.utcnow()
    jd_now, fr_now = jday(now.year, now.month, now.day, now.hour, now.minute, now.second)
    results = []
    for rec in records:
        try:
            sat, jd_ep, fr_ep = _build_satrec(rec)
            e, r, v = sat.sgp4(jd_now, fr_now)
            if e != 0 or r is None:
                continue
            r_eci = np.array([r[0], r[1], r[2]])
            lat, lng, alt = eci_to_geodetic(r_eci, jd_now, fr_now)
            results.append({
                "norad_id": rec.norad_cat_id,
                "name": rec.object_name,
                "lat": round(float(lat), 4),
                "lng": round(float(lng), 4),
                "alt_km": round(float(alt), 1),
                "periapsis_km": round(rec.periapsis_km, 1),
                "apoapsis_km": round(rec.apoapsis_km, 1),
                "inclination": round(rec.inclination, 2),
                "period_min": round(rec.period_min, 2),
            })
        except Exception:
            continue
    return SuccessResponse(data=results, meta={"group": group, "total": len(results)})


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
        # Format Pc for display
        if a.collision_probability is not None:
            rec["collision_probability_display"] = f"{a.collision_probability:.2e}"
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
        r_eci = np.array([r[0], r[1], r[2]])
        lat, lng, alt = eci_to_geodetic(r_eci, t_jd, 0.0)
        results.append({"lat": float(lat), "lng": float(lng), "alt": float(alt) / 6371.0, "time_jd": t_jd})

    return SuccessResponse(data=results, meta={
        "satellite": sat_name, "norad_id": norad_id,
        "days": days, "steps_per_day": steps_per_day, "total_steps": len(results),
        "source": "celestrak" if norad_id else "mock"
    })


@app.get("/api/v1/decay")
def get_decay_predictions(
    group: str = Query("fengyun-1c-debris"),
    threshold_days: float = Query(365.0, ge=1, le=3650, description="Show objects re-entering within N days"),
):
    """
    Predict orbit decay and re-entry for objects in a CelesTrak group.
    Uses atmospheric density models driven by real-time space weather.
    """
    raw = fetch_gp_data(group)
    records = parse_omm_records(raw)

    # Get current space weather for density scaling
    try:
        weather = get_current_space_weather()
        f107 = weather.f107_flux or 150.0
        kp = weather.kp_index or 2.0
    except Exception:
        f107, kp = 150.0, 2.0

    predictions = get_decaying_objects(records, f107, kp, threshold_days)

    return SuccessResponse(
        data=[{
            "norad_id": p.norad_id,
            "name": p.name,
            "periapsis_km": p.current_periapsis_km,
            "apoapsis_km": p.current_apoapsis_km,
            "decay_rate_km_day": p.decay_rate_km_per_day,
            "days_to_reentry": p.estimated_days_to_reentry,
            "reentry_date": p.estimated_reentry_date,
            "risk_level": p.risk_level,
        } for p in predictions],
        meta={
            "group": group,
            "threshold_days": threshold_days,
            "total_scanned": len(records),
            "decaying_objects": len(predictions),
            "f107_flux": f107,
            "kp_index": kp,
        }
    )


@app.get("/api/v1/advisories")
def get_advisories():
    """
    Generate operational advisories based on current space weather.
    Translates raw space environment data into actionable satellite ops guidance.
    """
    try:
        weather = get_current_space_weather()
        weather_dict = {
            "kp_index": weather.kp_index,
            "f107_flux": weather.f107_flux,
            "storm_level": weather.storm_level,
            "solar_wind_speed": weather.solar_wind_speed,
            "solar_wind_bz": weather.solar_wind_bz,
            "xray_class": weather.xray_class,
            "proton_gt10mev": weather.proton_gt10mev,
            "proton_gt100mev": weather.proton_gt100mev,
        }
        advisories = generate_advisories(weather_dict)
    except Exception as e:
        return JSONResponse(status_code=500, content=ErrorResponse(
            error=APIError(code="advisory_error", message=str(e))
        ).model_dump())

    return SuccessResponse(
        data=advisories,
        meta={"total": len(advisories), "sources": ["NOAA/SWPC", "DSCOVR", "GOES"]}
    )


@app.get("/api/v1/cdm")
def get_cdm(
    norad_id: int = Query(..., description="Primary NORAD ID"),
    secondary_id: int = Query(..., description="Secondary NORAD ID"),
    format: str = Query("json", description="Output format: json or kvn"),
):
    """
    Generate a Conjunction Data Message (CDM) for a specific conjunction event.
    Supports CCSDS KVN text format and structured JSON.
    """
    # Find primary and secondary
    primary_omm, _ = _find_omm_by_norad(norad_id)
    secondary_omm, _ = _find_omm_by_norad(secondary_id)

    if primary_omm is None:
        return JSONResponse(status_code=404, content=ErrorResponse(
            error=APIError(code="not_found", message=f"Primary NORAD ID {norad_id} not found.")
        ).model_dump())
    if secondary_omm is None:
        return JSONResponse(status_code=404, content=ErrorResponse(
            error=APIError(code="not_found", message=f"Secondary NORAD ID {secondary_id} not found.")
        ).model_dump())

    # Run quick screening to find the approach
    approaches = screen_conjunctions(
        primary_omm, [secondary_omm],
        hours=72, step_seconds=60, threshold_km=500
    )

    if not approaches:
        # Still generate a CDM with no close approach data
        approach = CloseApproach(
            primary_name=primary_omm.object_name,
            primary_norad_id=norad_id,
            secondary_name=secondary_omm.object_name,
            secondary_norad_id=secondary_id,
            tca="N/A", tca_jd=0,
            miss_distance_km=9999, radial_km=0, in_track_km=0, cross_track_km=0,
            relative_velocity_km_s=0, risk_level="nominal",
        )
    else:
        approach = approaches[0]  # Closest approach

    cdm = generate_cdm(approach, primary_omm, secondary_omm)

    if format == "kvn":
        kvn_text = format_cdm_kvn(cdm)
        return JSONResponse(
            content={"data": kvn_text, "meta": {"format": "CCSDS_KVN"}},
            media_type="application/json"
        )

    return SuccessResponse(data=cdm, meta={"format": "JSON"})


@app.get("/api/v1/satellite/{norad_id}")
def get_satellite_detail(norad_id: int):
    """
    Get detailed information for a specific satellite by NORAD ID.
    Includes orbital elements, decay prediction, and object classification.
    """
    omm, group = _find_omm_by_norad(norad_id)
    if omm is None:
        return JSONResponse(status_code=404, content=ErrorResponse(
            error=APIError(code="not_found", message=f"NORAD ID {norad_id} not found.")
        ).model_dump())

    # Decay prediction
    try:
        weather = get_current_space_weather()
        decay = predict_reentry(
            omm.norad_cat_id, omm.object_name,
            omm.periapsis_km, omm.apoapsis_km, omm.bstar,
            weather.f107_flux, weather.kp_index
        )
        decay_info = {
            "decay_rate_km_day": decay.decay_rate_km_per_day,
            "days_to_reentry": decay.estimated_days_to_reentry,
            "reentry_date": decay.estimated_reentry_date,
            "risk_level": decay.risk_level,
        }
    except Exception:
        decay_info = None

    # Object type
    name_upper = omm.object_name.upper()
    if "DEB" in name_upper:
        obj_type = "DEBRIS"
    elif "R/B" in name_upper:
        obj_type = "ROCKET BODY"
    else:
        obj_type = "PAYLOAD"

    # Orbit regime
    if omm.periapsis_km < 2000:
        regime = "LEO"
    elif omm.periapsis_km < 35786:
        regime = "MEO"
    else:
        regime = "GEO"

    return SuccessResponse(data={
        "norad_id": omm.norad_cat_id,
        "name": omm.object_name,
        "object_id": omm.object_id,
        "object_type": obj_type,
        "orbit_regime": regime,
        "group": group,
        "epoch": omm.epoch,
        "periapsis_km": round(omm.periapsis_km, 1),
        "apoapsis_km": round(omm.apoapsis_km, 1),
        "inclination": round(omm.inclination, 2),
        "eccentricity": omm.eccentricity,
        "period_min": round(omm.period_min, 2),
        "mean_motion": round(omm.mean_motion, 8),
        "bstar": omm.bstar,
        "semimajor_axis_km": round(omm.semimajor_axis_km, 3),
        "raan": round(omm.ra_of_asc_node, 4),
        "arg_perigee": round(omm.arg_of_pericenter, 4),
        "mean_anomaly": round(omm.mean_anomaly, 4),
        "classification": omm.classification_type,
        "decay": decay_info,
    })

@app.get("/api/v1/config")
def get_config():
    return SuccessResponse(data={
        "CESIUM_ION_TOKEN": os.environ.get("CESIUM_ION_TOKEN")
    })


@app.get("/api/v1/location-info")
async def get_location_info(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
):
    """Use AI to identify a geographic location and provide basic stats."""
    import httpx

    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    model = (os.environ.get("OPENROUTER_MODEL") or "z-ai/glm-4.5-air:free").strip()

    if not api_key:
        return SuccessResponse(data={
            "name": "Unknown",
            "info": f"Coordinates: {lat:.4f}°, {lng:.4f}°\nNo AI API key configured."
        })

    prompt = (
        f"I clicked on a point on the globe at latitude {lat:.4f}° and longitude {lng:.4f}°. "
        f"In 3-4 short lines, tell me: 1) The name of this location (city, region, country, or ocean/sea name), "
        f"2) One key fact about it, 3) Its approximate population or area if relevant. "
        f"Be concise and factual. If it's in the ocean, name the ocean/sea and nearest land."
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                }
            )
            data = resp.json()
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "No response")
            # Parse first line as name
            lines = answer.strip().split("\n")
            name = lines[0] if lines else "Unknown"
            info = "\n".join(lines[1:]) if len(lines) > 1 else answer

            return SuccessResponse(data={"name": name, "info": info})
    except Exception as e:
        return SuccessResponse(data={
            "name": f"{lat:.2f}°, {lng:.2f}°",
            "info": f"AI lookup failed: {str(e)}"
        })


@app.get("/")
def read_root():
    return SuccessResponse(data={
        "message": "God's Eye SSA Platform v4 — Mission-Critical Conjunction Assessment",
        "endpoints": [
            "/api/v1/search", "/api/v1/conjunctions", "/api/v1/catalog",
            "/api/v1/space-weather", "/api/v1/predict/baseline",
            "/api/v1/positions", "/api/v1/groups",
            "/api/v1/decay", "/api/v1/advisories",
            "/api/v1/cdm", "/api/v1/satellite/{norad_id}",
        ]
    })
