"""
Collision Probability (Pc) Engine for SSA Platform

Implements the 2D Alfano/Chan method — the industry standard used by
NASA CARA (Conjunction Assessment Risk Analysis), the 18th SDS, and
commercial providers like LeoLabs and COMSPOC.

Since CelesTrak GP data does not include covariance matrices, we estimate
position uncertainty from epoch age, altitude, and B* drag term using
empirical models derived from published literature.

References:
  - Chan, F.K. "Spacecraft Collision Probability" (2008)
  - Alfano, S. "A Numerical Implementation of Spherical Object
    Collision Probability" (2005)
  - NASA CARA Pc Methodology (conjunctions.org)
"""

import numpy as np
from math import pi, exp, sqrt
from typing import Tuple, Optional


# Hard-body radius for collision (sum of radii)
DEFAULT_HARD_BODY_RADIUS_M = 10.0   # 10m combined radius (conservative for active sats)
DEBRIS_HARD_BODY_RADIUS_M = 1.0     # 1m for small debris


def estimate_position_covariance(
    epoch_age_hours: float,
    altitude_km: float,
    bstar: float,
    object_type: str = "PAYLOAD"
) -> np.ndarray:
    """
    Estimate a diagonal 3×3 position covariance matrix (in km²) based on
    TLE epoch age, altitude, and drag characteristics.

    The uncertainty grows with epoch age due to:
    - Atmospheric drag uncertainty (dominant below 600 km)
    - Solar radiation pressure uncertainty
    - Gravitational perturbation accumulation

    Empirical model based on published covariance realism studies:
    - LEO (< 600 km): σ grows ~0.5-2.0 km/day (drag-dominated)
    - LEO (600-1000 km): σ grows ~0.1-0.5 km/day
    - MEO/GEO: σ grows ~0.01-0.1 km/day

    Args:
        epoch_age_hours: Hours since TLE epoch
        altitude_km: Mean altitude in km
        bstar: B* drag term from TLE
        object_type: "PAYLOAD", "DEBRIS", or "ROCKET_BODY"

    Returns:
        3×3 diagonal covariance matrix in km²
    """
    epoch_age_days = epoch_age_hours / 24.0

    # Base growth rate (km/day) depends on altitude
    if altitude_km < 400:
        growth_rate = 2.0   # High drag uncertainty
    elif altitude_km < 600:
        growth_rate = 1.0
    elif altitude_km < 1000:
        growth_rate = 0.3
    elif altitude_km < 2000:
        growth_rate = 0.1
    else:
        growth_rate = 0.05  # GEO/MEO: very stable

    # B* amplification: higher drag = more uncertainty
    bstar_factor = 1.0 + min(abs(bstar) * 1e4, 5.0)

    # Object type factor
    type_factor = {
        "PAYLOAD": 1.0,
        "DEBRIS": 2.0,      # Debris has less predictable attitude/drag
        "ROCKET_BODY": 1.5,
    }.get(object_type, 1.5)

    # Position uncertainty (1-sigma) in km
    # In-track uncertainty dominates (3-10x larger than radial/cross-track)
    sigma_r = max(0.01, growth_rate * bstar_factor * type_factor * epoch_age_days * 0.3)  # radial
    sigma_i = max(0.05, growth_rate * bstar_factor * type_factor * epoch_age_days * 1.0)  # in-track
    sigma_c = max(0.01, growth_rate * bstar_factor * type_factor * epoch_age_days * 0.2)  # cross-track

    # Cap at reasonable maxima
    sigma_r = min(sigma_r, 50.0)
    sigma_i = min(sigma_i, 200.0)
    sigma_c = min(sigma_c, 50.0)

    return np.diag([sigma_r ** 2, sigma_i ** 2, sigma_c ** 2])


def _project_to_encounter_plane(
    r_miss: np.ndarray,
    v_rel: np.ndarray,
    cov_combined: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Project the miss vector and combined covariance onto the 2D encounter plane
    (perpendicular to relative velocity vector).

    Args:
        r_miss: 3D miss vector (secondary - primary) in km
        v_rel: 3D relative velocity vector in km/s
        cov_combined: 3×3 combined position covariance in km²

    Returns:
        (miss_2d, cov_2d): 2D miss vector and 2×2 covariance in encounter plane
    """
    # Encounter plane basis vectors
    v_hat = v_rel / np.linalg.norm(v_rel)

    # Find two vectors perpendicular to v_hat
    if abs(v_hat[0]) < 0.9:
        perp1 = np.cross(v_hat, np.array([1.0, 0.0, 0.0]))
    else:
        perp1 = np.cross(v_hat, np.array([0.0, 1.0, 0.0]))
    perp1 = perp1 / np.linalg.norm(perp1)
    perp2 = np.cross(v_hat, perp1)
    perp2 = perp2 / np.linalg.norm(perp2)

    # Projection matrix (2×3)
    P = np.vstack([perp1, perp2])

    # Project miss vector to 2D
    miss_2d = P @ r_miss

    # Project covariance to 2D
    cov_2d = P @ cov_combined @ P.T

    return miss_2d, cov_2d


def compute_collision_probability(
    r_primary: np.ndarray,
    v_primary: np.ndarray,
    r_secondary: np.ndarray,
    v_secondary: np.ndarray,
    cov_primary: np.ndarray,
    cov_secondary: np.ndarray,
    hard_body_radius_km: float = DEFAULT_HARD_BODY_RADIUS_M / 1000.0,
) -> float:
    """
    Compute collision probability using the 2D Chan method.

    Projects the conjunction geometry onto the encounter plane (perpendicular
    to relative velocity) and integrates a 2D Gaussian over a circular
    hard-body cross-section.

    Args:
        r_primary: [x,y,z] position of primary in km (ECI)
        v_primary: [vx,vy,vz] velocity of primary in km/s (ECI)
        r_secondary: [x,y,z] position of secondary in km (ECI)
        v_secondary: [vx,vy,vz] velocity of secondary in km/s (ECI)
        cov_primary: 3×3 position covariance of primary in km²
        cov_secondary: 3×3 position covariance of secondary in km²
        hard_body_radius_km: combined hard-body radius in km

    Returns:
        Collision probability (0 to 1)
    """
    # Miss vector and relative velocity
    r_miss = r_secondary - r_primary
    v_rel = v_secondary - v_primary
    v_rel_mag = np.linalg.norm(v_rel)

    if v_rel_mag < 1e-6:
        return 0.0  # No relative motion

    # Combined covariance (assuming independence)
    cov_combined = cov_primary + cov_secondary

    # Project to encounter plane
    miss_2d, cov_2d = _project_to_encounter_plane(r_miss, v_rel, cov_combined)

    # Ensure covariance is positive definite
    det = np.linalg.det(cov_2d)
    if det <= 0:
        return 0.0

    # 2D Gaussian Pc (Chan method):
    # Pc = (R² / (2 * sqrt(det(C)))) * exp(-0.5 * miss^T * C^-1 * miss)
    # This is the "maximum probability" approximation, which assumes
    # the probability density is constant over the hard-body disk.
    cov_inv = np.linalg.inv(cov_2d)
    mahal_sq = float(miss_2d @ cov_inv @ miss_2d)

    # Hard-body cross section area
    R_sq = hard_body_radius_km ** 2

    # Chan's 2D Pc formula
    pc = (R_sq / (2.0 * sqrt(det))) * exp(-0.5 * mahal_sq)

    # Clamp to [0, 1]
    return max(0.0, min(1.0, pc))


def classify_risk_with_pc(miss_km: float, pc: float) -> str:
    """
    Enhanced risk classification using both miss distance AND collision probability.

    Thresholds aligned with NASA CARA and 18th SDS operational standards:
    - CRITICAL: Pc ≥ 1e-4 (NASA red threshold) OR miss < 1 km
    - WARNING:  Pc ≥ 1e-5 (NASA amber threshold) OR miss < 5 km
    - CAUTION:  Pc ≥ 1e-7 OR miss < 25 km
    - NOMINAL:  Below all thresholds

    Args:
        miss_km: Total 3D miss distance in km
        pc: Collision probability (0 to 1)

    Returns:
        Risk level string
    """
    if pc >= 1e-4 or miss_km < 1.0:
        return "critical"
    elif pc >= 1e-5 or miss_km < 5.0:
        return "warning"
    elif pc >= 1e-7 or miss_km < 25.0:
        return "caution"
    else:
        return "nominal"


def determine_hard_body_radius(name: str) -> float:
    """
    Determine hard-body collision radius based on object class.

    Args:
        name: Object name (used to infer type)

    Returns:
        Combined hard-body radius in km
    """
    name_upper = name.upper()
    if "DEB" in name_upper:
        return 0.001   # 1m for debris
    elif "R/B" in name_upper:
        return 0.005   # 5m for rocket bodies
    else:
        return 0.010   # 10m for payloads (conservative)
