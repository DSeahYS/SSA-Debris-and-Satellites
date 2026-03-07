"""
CelesTrak GP Data Client
Fetches real orbital elements (OMM JSON) from CelesTrak's free public API.
No API key required. Data is cached locally to avoid excessive requests.
"""
import os
import json
import time
import requests
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

# Constants
CELESTRAK_BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
CACHE_TTL_SECONDS = 3600  # 1 hour cache validity

# Satellite groups available on CelesTrak
SATELLITE_GROUPS = {
    # Active
    "stations": "Space Stations (ISS, Tiangong)",
    "active": "Active Satellites",
    "starlink": "Starlink Constellation",
    "visual": "Brightest / Visible",
    "weather": "Weather Satellites",
    "geo": "Geostationary Satellites",
    "last-30-days": "Recently Launched (30 days)",
    # Debris catalogs (all free from CelesTrak)
    "cosmos-2251-debris": "Cosmos 2251 Debris (2009 collision, ~1800 pcs)",
    "fengyun-1c-debris": "Fengyun 1C Debris (2007 Chinese ASAT, ~3400 pcs)",
    "iridium-33-debris": "Iridium 33 Debris (2009 collision)",
    "cosmos-1408-debris": "Cosmos 1408 Debris (2021 Russian ASAT, ~1500 pcs)",
    "indian-asat-debris": "Indian ASAT Debris (2019 Mission Shakti)",
    "1982-092": "1982-092 Breakup Debris",
}


@dataclass
class OMMRecord:
    """Orbit Mean-Elements Message — parsed from CelesTrak JSON."""
    object_name: str
    object_id: str
    norad_cat_id: int
    epoch: str
    mean_motion: float
    eccentricity: float
    inclination: float
    ra_of_asc_node: float
    arg_of_pericenter: float
    mean_anomaly: float
    bstar: float
    mean_motion_dot: float
    mean_motion_ddot: float = 0.0
    rev_at_epoch: int = 0
    element_set_no: int = 0
    classification_type: str = "U"
    ephemeris_type: int = 0
    # Derived
    semimajor_axis_km: float = 0.0
    period_min: float = 0.0
    apoapsis_km: float = 0.0
    periapsis_km: float = 0.0

    def __post_init__(self):
        """Compute derived orbital parameters."""
        MU_EARTH = 398600.4418  # km^3/s^2
        EARTH_RADIUS_KM = 6378.135
        if self.mean_motion > 0:
            n_rad_s = self.mean_motion * 2.0 * 3.141592653589793 / 86400.0
            self.semimajor_axis_km = (MU_EARTH / (n_rad_s ** 2)) ** (1.0 / 3.0)
            self.period_min = 1440.0 / self.mean_motion
            self.apoapsis_km = self.semimajor_axis_km * (1 + self.eccentricity) - EARTH_RADIUS_KM
            self.periapsis_km = self.semimajor_axis_km * (1 - self.eccentricity) - EARTH_RADIUS_KM


def _ensure_cache_dir():
    """Create the cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(group: str) -> Path:
    return CACHE_DIR / f"celestrak_{group}.json"


def _is_cache_valid(group: str) -> bool:
    path = _cache_path(group)
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < CACHE_TTL_SECONDS


def fetch_gp_data(group: str = "stations", use_cache: bool = True) -> List[dict]:
    """
    Fetch General Perturbations data from CelesTrak.

    Args:
        group: Satellite group name (e.g., 'stations', 'active', 'starlink').
        use_cache: Whether to use local caching.

    Returns:
        List of raw OMM JSON dicts from CelesTrak.
    """
    _ensure_cache_dir()

    # Check cache first
    if use_cache and _is_cache_valid(group):
        with open(_cache_path(group), "r") as f:
            return json.load(f)

    # Fetch from CelesTrak
    params = {"GROUP": group, "FORMAT": "json"}
    try:
        response = requests.get(CELESTRAK_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        # Fall back to cache if available
        if _cache_path(group).exists():
            print(f"[CelesTrak] Network error, using cached data: {e}")
            with open(_cache_path(group), "r") as f:
                return json.load(f)
        raise ConnectionError(f"Failed to fetch CelesTrak data for group '{group}': {e}")

    # Save to cache
    with open(_cache_path(group), "w") as f:
        json.dump(data, f)

    return data


def parse_omm_records(raw_data: List[dict]) -> List[OMMRecord]:
    """
    Parse raw CelesTrak JSON into structured OMMRecord dataclasses.

    Args:
        raw_data: List of dicts from CelesTrak GP JSON API.

    Returns:
        List of OMMRecord objects with derived orbital parameters.
    """
    records = []
    for item in raw_data:
        try:
            record = OMMRecord(
                object_name=item.get("OBJECT_NAME", "UNKNOWN"),
                object_id=item.get("OBJECT_ID", ""),
                norad_cat_id=int(item.get("NORAD_CAT_ID", 0)),
                epoch=item.get("EPOCH", ""),
                mean_motion=float(item.get("MEAN_MOTION", 0)),
                eccentricity=float(item.get("ECCENTRICITY", 0)),
                inclination=float(item.get("INCLINATION", 0)),
                ra_of_asc_node=float(item.get("RA_OF_ASC_NODE", 0)),
                arg_of_pericenter=float(item.get("ARG_OF_PERICENTER", 0)),
                mean_anomaly=float(item.get("MEAN_ANOMALY", 0)),
                bstar=float(item.get("BSTAR", 0)),
                mean_motion_dot=float(item.get("MEAN_MOTION_DOT", 0)),
                mean_motion_ddot=float(item.get("MEAN_MOTION_DDOT", 0)),
                rev_at_epoch=int(item.get("REV_AT_EPOCH", 0)),
                element_set_no=int(item.get("ELEMENT_SET_NO", 0)),
                classification_type=item.get("CLASSIFICATION_TYPE", "U"),
                ephemeris_type=int(item.get("EPHEMERIS_TYPE", 0)),
            )
            records.append(record)
        except (ValueError, TypeError) as e:
            print(f"[CelesTrak] Skipping malformed record: {e}")
            continue
    return records


def get_satellite_catalog(group: str = "stations") -> List[dict]:
    """
    Returns a simplified catalog list for the frontend dropdown.

    Returns:
        List of dicts with 'norad_id', 'name', 'periapsis_km', 'apoapsis_km'.
    """
    raw = fetch_gp_data(group)
    records = parse_omm_records(raw)
    return [
        {
            "norad_id": r.norad_cat_id,
            "name": r.object_name,
            "periapsis_km": round(r.periapsis_km, 1),
            "apoapsis_km": round(r.apoapsis_km, 1),
            "inclination": round(r.inclination, 2),
            "period_min": round(r.period_min, 2),
            "epoch": r.epoch,
        }
        for r in records
    ]


if __name__ == "__main__":
    print("[CelesTrak Client] Fetching space station data...")
    catalog = get_satellite_catalog("stations")
    for sat in catalog[:5]:
        print(f"  {sat['name']} (NORAD {sat['norad_id']}): "
              f"{sat['periapsis_km']:.0f} x {sat['apoapsis_km']:.0f} km, "
              f"inc={sat['inclination']:.1f}°")
    print(f"  ... {len(catalog)} objects total.")
