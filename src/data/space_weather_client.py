"""
NOAA SWPC Space Weather Client
Fetches real-time geomagnetic indices (Kp, Dst) and solar flux (F10.7)
from the NOAA Space Weather Prediction Center's free JSON API.
No API key required.
"""
import requests
from dataclasses import dataclass
from typing import List, Optional

SWPC_BASE = "https://services.swpc.noaa.gov"

# Endpoints
KP_1MIN_URL = f"{SWPC_BASE}/json/planetary_k_index_1m.json"
DST_1HR_URL = f"{SWPC_BASE}/products/kyoto-dst.json"
F107_URL = f"{SWPC_BASE}/json/f107_cm_flux.json"
KP_DST_URL = f"{SWPC_BASE}/json/geospace/geospace_pred_est_kp_1_hour.json"
GEOSPACE_DST_URL = f"{SWPC_BASE}/products/geospace/propagated-solar-wind-1-hour.json"


@dataclass
class SpaceWeatherSnapshot:
    """A point-in-time snapshot of space weather conditions."""
    timestamp: str
    kp_index: float              # 0-9 scale, planetary geomagnetic index
    dst_index: Optional[float]   # nT, disturbance storm time index
    f107_flux: Optional[float]   # SFU, 10.7cm solar radio flux
    storm_level: str             # "quiet", "unsettled", "storm", "severe_storm"

    @staticmethod
    def classify_storm(kp: float) -> str:
        if kp < 4:
            return "quiet"
        elif kp < 5:
            return "unsettled"
        elif kp < 7:
            return "storm"
        else:
            return "severe_storm"


def fetch_kp_index() -> List[dict]:
    """
    Fetch the estimated planetary Kp index (1-minute cadence).
    Returns the most recent entries.
    """
    try:
        response = requests.get(KP_1MIN_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.RequestException as e:
        print(f"[SWPC] Failed to fetch Kp index: {e}")
        return []


def fetch_dst_index() -> List[dict]:
    """
    Fetch the Dst index from NOAA Geospace products.
    """
    try:
        # Try the geospace propagated solar wind which includes Dst estimates
        response = requests.get(GEOSPACE_DST_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.RequestException as e:
        print(f"[SWPC] Failed to fetch Dst index: {e}")
        return []


def fetch_f107_flux() -> List[dict]:
    """
    Fetch the F10.7cm solar radio flux measurements.
    """
    try:
        response = requests.get(F107_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.RequestException as e:
        print(f"[SWPC] Failed to fetch F10.7 flux: {e}")
        return []


def get_current_space_weather() -> SpaceWeatherSnapshot:
    """
    Get the most recent space weather conditions by combining
    Kp, Dst, and F10.7 data from NOAA SWPC.

    Returns:
        SpaceWeatherSnapshot with the latest available readings.
    """
    # Fetch Kp
    kp_data = fetch_kp_index()
    latest_kp = 0.0
    kp_timestamp = "N/A"
    if kp_data:
        latest = kp_data[-1]
        latest_kp = float(latest.get("estimated_kp", latest.get("kp_index", 0)))
        kp_timestamp = latest.get("time_tag", latest.get("model_prediction_time", "N/A"))

    # Fetch F10.7
    f107_data = fetch_f107_flux()
    latest_f107 = None
    if f107_data:
        latest = f107_data[-1]
        latest_f107 = float(latest.get("flux", latest.get("f107", 0)))

    # Classify storm level
    storm_level = SpaceWeatherSnapshot.classify_storm(latest_kp)

    return SpaceWeatherSnapshot(
        timestamp=kp_timestamp,
        kp_index=latest_kp,
        dst_index=None,  # Dst requires separate parsing; we'll add it as we refine
        f107_flux=latest_f107,
        storm_level=storm_level,
    )


if __name__ == "__main__":
    print("[SWPC Client] Fetching current space weather...")
    weather = get_current_space_weather()
    print(f"  Timestamp:   {weather.timestamp}")
    print(f"  Kp Index:    {weather.kp_index}")
    print(f"  F10.7 Flux:  {weather.f107_flux} SFU")
    print(f"  Storm Level: {weather.storm_level}")
