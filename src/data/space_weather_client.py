"""
NOAA SWPC Space Weather Client (v2)
Fetches real-time geomagnetic indices, solar flux, solar wind,
X-ray flux, and proton flux from NOAA's free JSON APIs.
No API key required.

Data Sources:
  - Kp index: services.swpc.noaa.gov/json/planetary_k_index_1m.json
  - F10.7 flux: services.swpc.noaa.gov/json/f107_cm_flux.json
  - Solar wind (DSCOVR): services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json
  - Solar wind mag: services.swpc.noaa.gov/products/solar-wind/mag-7-day.json
  - X-ray flux (GOES): services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json
  - Proton flux (GOES): services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json
"""
import requests
from dataclasses import dataclass, field
from typing import List, Optional, Dict

SWPC_BASE = "https://services.swpc.noaa.gov"

# Endpoints
KP_1MIN_URL = f"{SWPC_BASE}/json/planetary_k_index_1m.json"
F107_URL = f"{SWPC_BASE}/json/f107_cm_flux.json"
SOLAR_WIND_PLASMA_URL = f"{SWPC_BASE}/products/solar-wind/plasma-7-day.json"
SOLAR_WIND_MAG_URL = f"{SWPC_BASE}/products/solar-wind/mag-7-day.json"
XRAY_FLUX_URL = f"{SWPC_BASE}/json/goes/primary/xray-flares-latest.json"
PROTON_FLUX_URL = f"{SWPC_BASE}/json/goes/primary/integral-protons-1-day.json"
GEOMAG_FORECAST_URL = f"{SWPC_BASE}/products/noaa-planetary-k-index-forecast.json"


@dataclass
class SpaceWeatherSnapshot:
    """Comprehensive space weather conditions."""
    timestamp: str
    kp_index: float              # 0-9, planetary geomagnetic index
    dst_index: Optional[float]   # nT, disturbance storm time
    f107_flux: Optional[float]   # SFU, 10.7cm solar radio flux
    storm_level: str             # quiet / unsettled / storm / severe_storm
    # Solar wind (DSCOVR)
    solar_wind_speed: Optional[float] = None   # km/s
    solar_wind_density: Optional[float] = None # p/cm³
    solar_wind_temp: Optional[float] = None    # K
    solar_wind_bt: Optional[float] = None      # nT, total B-field
    solar_wind_bz: Optional[float] = None      # nT, Z-component
    # GOES X-ray
    xray_class: Optional[str] = None           # e.g. "C1.2", "M5.4", "X1.0"
    xray_flux: Optional[float] = None          # W/m²
    # GOES Proton
    proton_gt10mev: Optional[float] = None     # pfu, ≥10 MeV
    proton_gt100mev: Optional[float] = None    # pfu, ≥100 MeV

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


def _safe_get(url: str, timeout: int = 15):
    """Fetch JSON from URL with error handling."""
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[SWPC] Failed: {url} — {e}")
        return None


def fetch_kp_index() -> List[dict]:
    data = _safe_get(KP_1MIN_URL)
    return data if isinstance(data, list) else []


def fetch_f107_flux() -> List[dict]:
    data = _safe_get(F107_URL)
    return data if isinstance(data, list) else []


def fetch_solar_wind_plasma() -> Optional[Dict]:
    """Fetch DSCOVR solar wind plasma: speed, density, temperature."""
    data = _safe_get(SOLAR_WIND_PLASMA_URL)
    if not data or len(data) < 2:
        return None
    # Data is array-of-arrays: [headers, ...rows]
    # Headers: time_tag, density, speed, temperature
    try:
        # Get latest non-null entry (scan from end)
        for row in reversed(data[1:]):
            if row[2] is not None and row[2] != '':  # speed
                return {
                    "time_tag": row[0],
                    "density": float(row[1]) if row[1] else None,
                    "speed": float(row[2]) if row[2] else None,
                    "temperature": float(row[3]) if row[3] else None,
                }
    except (IndexError, ValueError, TypeError):
        pass
    return None


def fetch_solar_wind_mag() -> Optional[Dict]:
    """Fetch DSCOVR solar wind magnetometer: Bt, Bz."""
    data = _safe_get(SOLAR_WIND_MAG_URL)
    if not data or len(data) < 2:
        return None
    try:
        for row in reversed(data[1:]):
            if row[6] is not None and row[6] != '':  # bt
                return {
                    "time_tag": row[0],
                    "bt": float(row[6]) if row[6] else None,
                    "bz": float(row[3]) if row[3] else None,
                }
    except (IndexError, ValueError, TypeError):
        pass
    return None


def fetch_xray_flares() -> Optional[Dict]:
    """Fetch latest X-ray flare event from GOES."""
    data = _safe_get(XRAY_FLUX_URL)
    if not data or not isinstance(data, list):
        return None
    try:
        latest = data[-1] if data else None
        if latest:
            return {
                "class": latest.get("max_class", ""),
                "flux": latest.get("max_xrlong", None),
                "time": latest.get("max_time", ""),
            }
    except (IndexError, TypeError):
        pass
    return None


def fetch_proton_flux() -> Optional[Dict]:
    """Fetch latest integral proton flux from GOES."""
    data = _safe_get(PROTON_FLUX_URL)
    if not data or not isinstance(data, list):
        return None
    try:
        # Look for ≥10 MeV and ≥100 MeV channels
        gt10 = None
        gt100 = None
        for entry in reversed(data):
            energy = entry.get("energy", "")
            flux = entry.get("flux", None)
            if "10" in str(energy) and gt10 is None and flux is not None:
                gt10 = float(flux)
            if "100" in str(energy) and gt100 is None and flux is not None:
                gt100 = float(flux)
            if gt10 is not None and gt100 is not None:
                break
        return {"gt10mev": gt10, "gt100mev": gt100}
    except (TypeError, ValueError):
        pass
    return None


def get_current_space_weather() -> SpaceWeatherSnapshot:
    """
    Assemble comprehensive space weather from all NOAA sources.
    Combines: Kp, F10.7, DSCOVR solar wind, GOES X-ray, GOES proton.
    """
    # Kp index
    kp_data = fetch_kp_index()
    latest_kp = 0.0
    kp_timestamp = "N/A"
    if kp_data:
        latest = kp_data[-1]
        latest_kp = float(latest.get("estimated_kp", latest.get("kp_index", 0)))
        kp_timestamp = latest.get("time_tag", latest.get("model_prediction_time", "N/A"))

    # F10.7
    f107_data = fetch_f107_flux()
    latest_f107 = None
    if f107_data:
        latest = f107_data[-1]
        latest_f107 = float(latest.get("flux", latest.get("f107", 0)))

    storm_level = SpaceWeatherSnapshot.classify_storm(latest_kp)

    # Solar wind plasma
    sw_plasma = fetch_solar_wind_plasma()
    sw_speed = sw_plasma["speed"] if sw_plasma else None
    sw_density = sw_plasma["density"] if sw_plasma else None
    sw_temp = sw_plasma["temperature"] if sw_plasma else None

    # Solar wind mag
    sw_mag = fetch_solar_wind_mag()
    sw_bt = sw_mag["bt"] if sw_mag else None
    sw_bz = sw_mag["bz"] if sw_mag else None

    # X-ray
    xray = fetch_xray_flares()
    xray_class = xray["class"] if xray else None
    xray_flux_val = xray["flux"] if xray else None

    # Proton
    proton = fetch_proton_flux()
    p10 = proton["gt10mev"] if proton else None
    p100 = proton["gt100mev"] if proton else None

    return SpaceWeatherSnapshot(
        timestamp=kp_timestamp,
        kp_index=latest_kp,
        dst_index=None,
        f107_flux=latest_f107,
        storm_level=storm_level,
        solar_wind_speed=sw_speed,
        solar_wind_density=sw_density,
        solar_wind_temp=sw_temp,
        solar_wind_bt=sw_bt,
        solar_wind_bz=sw_bz,
        xray_class=xray_class,
        xray_flux=xray_flux_val,
        proton_gt10mev=p10,
        proton_gt100mev=p100,
    )
