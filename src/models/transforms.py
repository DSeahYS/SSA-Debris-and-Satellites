"""
Coordinate Transforms for SSA Platform
ECI (TEME) → ECEF → Geodetic conversion with GMST rotation.

The SGP4 propagator outputs position in the TEME (True Equator Mean Equinox)
frame, which is an Earth-Centered Inertial frame. To get ground-track
longitude, we must rotate by the Greenwich Mean Sidereal Time (GMST)
to convert to ECEF (Earth-Centered Earth-Fixed).

Reference: Vallado, "Fundamentals of Astrodynamics and Applications", 4th ed.
"""

import numpy as np
from math import pi, atan2, asin, sqrt, fmod


# WGS-84 constants
EARTH_RADIUS_KM = 6378.137        # equatorial radius
EARTH_FLATTENING = 1.0 / 298.257223563
EARTH_E2 = EARTH_FLATTENING * (2.0 - EARTH_FLATTENING)  # first eccentricity squared


def compute_gmst(jd: float, fr: float = 0.0) -> float:
    """
    Compute Greenwich Mean Sidereal Time (GMST) in radians.

    Uses the IAU 1982 model (consistent with SGP4/TEME frame).

    Args:
        jd: Julian Date (integer part)
        fr: Julian Date (fractional part)

    Returns:
        GMST in radians [0, 2π)
    """
    # Julian centuries from J2000.0
    t_ut1 = ((jd - 2451545.0) + fr) / 36525.0

    # GMST in seconds of time (IAU 1982)
    gmst_sec = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * t_ut1
        + 0.093104 * t_ut1 ** 2
        - 6.2e-6 * t_ut1 ** 3
    )

    # Convert to radians and normalize to [0, 2π)
    gmst_rad = fmod(gmst_sec * (2.0 * pi / 86400.0), 2.0 * pi)
    if gmst_rad < 0:
        gmst_rad += 2.0 * pi

    return gmst_rad


def eci_to_ecef(r_eci: np.ndarray, jd: float, fr: float = 0.0) -> np.ndarray:
    """
    Rotate a position vector from ECI (TEME) to ECEF using GMST.

    Args:
        r_eci: [x, y, z] in km, ECI frame
        jd, fr: Julian Date (integer + fractional parts)

    Returns:
        [x, y, z] in km, ECEF frame
    """
    gmst = compute_gmst(jd, fr)
    cos_g = np.cos(gmst)
    sin_g = np.sin(gmst)

    x_ecef = cos_g * r_eci[0] + sin_g * r_eci[1]
    y_ecef = -sin_g * r_eci[0] + cos_g * r_eci[1]
    z_ecef = r_eci[2]

    return np.array([x_ecef, y_ecef, z_ecef])


def ecef_to_geodetic(r_ecef: np.ndarray) -> tuple:
    """
    Convert ECEF position to geodetic latitude, longitude, altitude.

    Uses iterative method for geodetic latitude (WGS-84 ellipsoid).

    Args:
        r_ecef: [x, y, z] in km, ECEF frame

    Returns:
        (lat_deg, lng_deg, alt_km)
    """
    x, y, z = r_ecef[0], r_ecef[1], r_ecef[2]

    # Longitude
    lng = atan2(y, x) * (180.0 / pi)

    # Distance from Z-axis
    p = sqrt(x ** 2 + y ** 2)

    # Iterative latitude (Bowring's method, converges in 2-3 iterations)
    lat = atan2(z, p * (1.0 - EARTH_E2))  # initial guess
    for _ in range(5):
        sin_lat = np.sin(lat)
        N = EARTH_RADIUS_KM / sqrt(1.0 - EARTH_E2 * sin_lat ** 2)
        lat = atan2(z + EARTH_E2 * N * sin_lat, p)

    # Altitude
    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    N = EARTH_RADIUS_KM / sqrt(1.0 - EARTH_E2 * sin_lat ** 2)

    if abs(cos_lat) > 1e-10:
        alt = p / cos_lat - N
    else:
        alt = abs(z) - N * (1.0 - EARTH_E2)

    lat_deg = lat * (180.0 / pi)

    return lat_deg, lng_deg_normalize(lng), alt


def lng_deg_normalize(lng: float) -> float:
    """Normalize longitude to [-180, 180]."""
    while lng > 180.0:
        lng -= 360.0
    while lng < -180.0:
        lng += 360.0
    return lng


def eci_to_geodetic(r_eci: np.ndarray, jd: float, fr: float = 0.0) -> tuple:
    """
    Full pipeline: ECI (TEME) → ECEF → Geodetic.

    Args:
        r_eci: [x, y, z] in km, ECI/TEME frame
        jd, fr: Julian Date (integer + fractional parts)

    Returns:
        (lat_deg, lng_deg, alt_km)
    """
    r_ecef = eci_to_ecef(r_eci, jd, fr)
    return ecef_to_geodetic(r_ecef)
