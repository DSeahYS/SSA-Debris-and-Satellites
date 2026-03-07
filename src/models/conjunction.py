"""
Conjunction Assessment Engine
Screens a primary satellite against a catalog of secondaries to find close approaches.
Computes miss distance decomposed into Radial, In-Track, and Cross-Track components.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from sgp4.api import Satrec, WGS72
from sgp4.conveniences import jday
from math import pi
from datetime import datetime, timedelta


@dataclass
class CloseApproach:
    """A single conjunction event between two objects."""
    primary_name: str
    primary_norad_id: int
    secondary_name: str
    secondary_norad_id: int
    tca: str                    # Time of Closest Approach (ISO 8601)
    tca_jd: float               # Julian Date of TCA
    miss_distance_km: float     # Total 3D miss distance
    radial_km: float            # Radial (along position vector)
    in_track_km: float          # In-track (along velocity vector)
    cross_track_km: float       # Cross-track (perpendicular to orbital plane)
    relative_velocity_km_s: float  # Relative speed at TCA
    risk_level: str             # "critical", "warning", "caution", "nominal"

    @staticmethod
    def classify_risk(miss_km: float) -> str:
        if miss_km < 1.0:
            return "critical"
        elif miss_km < 5.0:
            return "warning"
        elif miss_km < 25.0:
            return "caution"
        else:
            return "nominal"


def _build_satrec_from_omm(omm) -> Optional[Satrec]:
    """Build an sgp4 Satrec object from an OMMRecord."""
    try:
        sat = Satrec()
        epoch_str = omm.epoch
        yr = int(epoch_str[:4])
        mo = int(epoch_str[5:7])
        dy = int(epoch_str[8:10])
        hr = int(epoch_str[11:13])
        mi = int(epoch_str[14:16])
        sc = float(epoch_str[17:])
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
        return sat
    except Exception:
        return None


def _propagate_at(sat: Satrec, jd: float, fr: float) -> Tuple[np.ndarray, np.ndarray]:
    """Propagate a Satrec to jd+fr, return (r_km, v_km_s) as numpy arrays."""
    e, r, v = sat.sgp4(jd, fr)
    if e != 0:
        return np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0])
    return np.array(r), np.array(v)


def _decompose_miss(r_primary: np.ndarray, v_primary: np.ndarray,
                     r_secondary: np.ndarray) -> Tuple[float, float, float]:
    """
    Decompose the miss vector into Radial, In-Track, Cross-Track (RIC) frame.

    The RIC frame is defined relative to the primary:
    - R (radial): along the position vector (away from Earth)
    - C (cross-track): perpendicular to the orbital plane (r × v)
    - I (in-track): completes the right-hand system (C × R)
    """
    r_hat = r_primary / np.linalg.norm(r_primary)
    c_hat = np.cross(r_primary, v_primary)
    c_hat = c_hat / np.linalg.norm(c_hat)
    i_hat = np.cross(c_hat, r_hat)

    miss_vec = r_secondary - r_primary
    radial = float(np.dot(miss_vec, r_hat))
    in_track = float(np.dot(miss_vec, i_hat))
    cross_track = float(np.dot(miss_vec, c_hat))

    return radial, in_track, cross_track


def screen_conjunctions(
    primary_omm,
    secondary_omms: list,
    hours: int = 24,
    step_seconds: int = 60,
    threshold_km: float = 50.0,
) -> List[CloseApproach]:
    """
    Screen a primary satellite against a list of secondaries for close approaches.

    Args:
        primary_omm: OMMRecord of the primary (your satellite).
        secondary_omms: List of OMMRecord objects to screen against.
        hours: Prediction window in hours.
        step_seconds: Time step in seconds (60s = 1 per minute).
        threshold_km: Distance threshold for reporting (km).

    Returns:
        List of CloseApproach events, sorted by miss_distance_km ascending.
    """
    primary_sat = _build_satrec_from_omm(primary_omm)
    if primary_sat is None:
        return []

    # Build secondaries
    secondaries = []
    for omm in secondary_omms:
        if omm.norad_cat_id == primary_omm.norad_cat_id:
            continue  # Skip self
        sat = _build_satrec_from_omm(omm)
        if sat is not None:
            secondaries.append((omm, sat))

    if not secondaries:
        return []

    # Time grid
    now = datetime.utcnow()
    jd0, fr0 = jday(now.year, now.month, now.day, now.hour, now.minute, now.second)
    n_steps = int(hours * 3600 / step_seconds)

    # Track closest approach per secondary
    closest = {}  # norad_id -> (min_dist, tca_jd, tca_fr, r_pri, v_pri, r_sec, v_sec)

    for step in range(n_steps):
        dt_days = (step * step_seconds) / 86400.0
        jd = jd0
        fr = fr0 + dt_days

        # Normalize JD/FR
        while fr >= 1.0:
            jd += 1.0
            fr -= 1.0

        r_pri, v_pri = _propagate_at(primary_sat, jd, fr)
        if np.linalg.norm(r_pri) < 100:
            continue  # Propagation error

        for omm, sec_sat in secondaries:
            r_sec, v_sec = _propagate_at(sec_sat, jd, fr)
            if np.linalg.norm(r_sec) < 100:
                continue

            dist = float(np.linalg.norm(r_sec - r_pri))

            if dist < threshold_km:
                nid = omm.norad_cat_id
                if nid not in closest or dist < closest[nid][0]:
                    closest[nid] = (dist, jd, fr, r_pri.copy(), v_pri.copy(), r_sec.copy(), v_sec.copy(), omm)

    # Build results
    results = []
    for nid, (min_dist, tca_jd, tca_fr, r_pri, v_pri, r_sec, v_sec, omm) in closest.items():
        # Decompose into RIC
        radial, in_track, cross_track = _decompose_miss(r_pri, v_pri, r_sec)

        # Relative velocity
        rel_v = float(np.linalg.norm(v_sec - v_pri))

        # Convert TCA JD to ISO string
        from sgp4.conveniences import days2mdhms
        # Approximate TCA datetime
        tca_total = tca_jd + tca_fr
        # Convert from JD to datetime
        tca_dt = datetime(2000, 1, 1, 12, 0, 0) + timedelta(days=tca_total - 2451545.0)
        tca_iso = tca_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        results.append(CloseApproach(
            primary_name=primary_omm.object_name,
            primary_norad_id=primary_omm.norad_cat_id,
            secondary_name=omm.object_name,
            secondary_norad_id=omm.norad_cat_id,
            tca=tca_iso,
            tca_jd=tca_total,
            miss_distance_km=round(min_dist, 3),
            radial_km=round(radial, 3),
            in_track_km=round(in_track, 3),
            cross_track_km=round(cross_track, 3),
            relative_velocity_km_s=round(rel_v, 3),
            risk_level=CloseApproach.classify_risk(min_dist),
        ))

    results.sort(key=lambda x: x.miss_distance_km)
    return results


def estimate_avoidance_maneuver(approach: CloseApproach) -> dict:
    """
    Estimate a basic collision avoidance maneuver.
    Uses a simple impulsive delta-v in the cross-track direction
    to increase separation by 2x the miss distance.

    Returns:
        Dict with maneuver timing, direction, and delta-v estimate.
    """
    # Time before TCA to execute (half orbital period typical, ~45 min for LEO)
    execute_minutes_before_tca = 45

    # Target offset: move 2x the miss distance in cross-track
    target_offset_km = max(5.0, approach.miss_distance_km * 2.0)

    # Very rough delta-v estimate for cross-track maneuver in LEO
    # dv ≈ (2π * offset) / (period * 60) for one orbit ahead
    # For LEO (~90 min period): dv ≈ offset * 0.001 km/s per km offset
    delta_v_m_s = target_offset_km * 1.16  # m/s, empirical factor for LEO

    return {
        "execute_minutes_before_tca": execute_minutes_before_tca,
        "direction": "cross-track (normal to orbital plane)",
        "delta_v_m_s": round(delta_v_m_s, 2),
        "target_offset_km": round(target_offset_km, 1),
        "fuel_cost_estimate": "minimal" if delta_v_m_s < 5 else "moderate" if delta_v_m_s < 20 else "significant",
        "note": "This is a simplified estimate. Operational maneuvers require covariance analysis and Monte Carlo simulation."
    }
