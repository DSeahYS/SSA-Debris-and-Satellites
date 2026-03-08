"""
Satellite Operator Advisory Engine

Translates raw space weather data into actionable satellite operations
advisories. Modeled after operational advisory systems used at the
Combined Space Operations Center (CSpOC), Slingshot Beacon, and
NOAA SWPC alerts.

Advisory Categories:
  - DRAG_ENHANCED: Increased atmospheric drag affecting orbit predictions
  - RADIATION_STORM: Single Event Upset (SEU) risk from energetic protons
  - GEOMAGNETIC_STORM: Attitude control & GPS degradation
  - SOLAR_FLARE: HF radio blackout and comm disruption
  - SURFACE_CHARGING: Electrostatic discharge risk (GEO)
  - ORBIT_PREDICTION_DEGRADED: Conjunction Pc estimates unreliable
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class Advisory:
    """A single operator advisory."""
    type: str              # Advisory category
    severity: str          # "info" / "warning" / "critical"
    title: str             # Short headline
    message: str           # Detailed advisory text
    affected_orbits: str   # "LEO" / "MEO" / "GEO" / "ALL"
    actions: List[str]     # Recommended operator actions
    timestamp: str         # When advisory was generated
    source: str            # Data source triggering the advisory


def generate_advisories(
    space_weather: dict,
    primary_omm=None,
) -> List[dict]:
    """
    Generate operational advisories based on current space weather.

    Args:
        space_weather: Dict with keys: kp_index, f107_flux, storm_level,
                      solar_wind_speed, solar_wind_bz, xray_class,
                      proton_gt10mev, proton_gt100mev
        primary_omm: Optional OMMRecord to tailor advisories to specific orbit

    Returns:
        List of advisory dicts, sorted by severity (critical first)
    """
    advisories = []
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    kp = space_weather.get("kp_index", 0) or 0
    f107 = space_weather.get("f107_flux", 0) or 0
    sw_speed = space_weather.get("solar_wind_speed") or 0
    sw_bz = space_weather.get("solar_wind_bz") or 0
    xray = space_weather.get("xray_class", "") or ""
    p10 = space_weather.get("proton_gt10mev") or 0
    p100 = space_weather.get("proton_gt100mev") or 0

    # Determine if primary is in a specific orbit regime
    pri_alt = None
    if primary_omm:
        pri_alt = (getattr(primary_omm, 'periapsis_km', 0) +
                   getattr(primary_omm, 'apoapsis_km', 0)) / 2.0

    # --- DRAG ENHANCED ---
    if kp >= 5 or f107 > 200:
        sev = "critical" if kp >= 7 or f107 > 250 else "warning"
        drag_increase = "50-200%" if kp >= 7 else "20-50%"
        advisories.append(_build_advisory(
            type="DRAG_ENHANCED",
            severity=sev,
            title="Enhanced Atmospheric Drag",
            message=(
                f"Atmospheric density elevated due to {'geomagnetic storm (Kp=' + str(kp) + ')' if kp >= 5 else ''}"
                f"{' and ' if kp >= 5 and f107 > 200 else ''}"
                f"{'high solar flux (F10.7=' + str(round(f107)) + ')' if f107 > 200 else ''}. "
                f"LEO orbit decay rates increased by approximately {drag_increase}. "
                f"Orbit prediction accuracy degraded."
            ),
            affected_orbits="LEO",
            actions=[
                "Increase conjunction screening frequency",
                "Re-propagate all LEO ephemerides with updated atmospheric model",
                "Monitor periapsis altitude for rapid decay",
                "Consider postponing non-critical maneuvers",
            ],
            timestamp=now,
            source="NOAA/SWPC Kp & F10.7",
        ))

    # --- RADIATION STORM ---
    if p10 > 10:
        sev = "critical" if p10 > 1000 or p100 > 1 else "warning"
        advisories.append(_build_advisory(
            type="RADIATION_STORM",
            severity=sev,
            title="Solar Proton Event — SEU Risk",
            message=(
                f"Energetic proton flux elevated: ≥10 MeV = {p10:.1f} pfu"
                f"{', ≥100 MeV = ' + str(round(p100, 2)) + ' pfu' if p100 else ''}. "
                f"Single Event Upset (SEU) risk for satellite electronics. "
                f"{'SEVERE: S3+ radiation storm conditions. ' if p10 > 1000 else ''}"
                f"Astronaut EVA radiation limits may be exceeded."
            ),
            affected_orbits="ALL",
            actions=[
                "Enable SEU-tolerant operating modes",
                "Increase telemetry monitoring cadence",
                "Defer firmware uploads and critical commands",
                "Monitor spacecraft health telemetry for anomalies",
                "ISS: Consider crew shelter in hardened modules",
            ],
            timestamp=now,
            source="GOES Proton Flux",
        ))

    # --- GEOMAGNETIC STORM ---
    if kp >= 7:
        advisories.append(_build_advisory(
            type="GEOMAGNETIC_STORM",
            severity="critical",
            title="Severe Geomagnetic Storm (G3+)",
            message=(
                f"Kp index = {kp:.1f} indicates G{min(int(kp) - 4, 5)} geomagnetic storm. "
                f"Expect: degraded GPS accuracy (>10m error), attitude determination anomalies, "
                f"enhanced auroral currents affecting LEO spacecraft, and potential induced "
                f"charging on spacecraft surfaces."
            ),
            affected_orbits="ALL",
            actions=[
                "Switch to star-tracker-only attitude mode (bypass magnetometer)",
                "Increase GPS solution filtering",
                "Monitor spacecraft charging levels",
                "Prepare for potential conjunction alert surge (catalog uncertainty increase)",
                "Brief flight operations team on storm procedures",
            ],
            timestamp=now,
            source="NOAA/SWPC Kp",
        ))
    elif kp >= 5:
        advisories.append(_build_advisory(
            type="GEOMAGNETIC_STORM",
            severity="warning",
            title=f"Geomagnetic Storm (G{min(int(kp) - 4, 5)})",
            message=(
                f"Kp index = {kp:.1f}. Moderate geomagnetic storm conditions. "
                f"GPS accuracy may be degraded. Attitude control anomalies possible "
                f"for LEO spacecraft using magnetometers."
            ),
            affected_orbits="LEO",
            actions=[
                "Monitor attitude control performance",
                "Verify GPS navigation accuracy",
                "Increase ephemeris update frequency",
            ],
            timestamp=now,
            source="NOAA/SWPC Kp",
        ))

    # --- SOLAR FLARE ---
    if xray.startswith("X"):
        advisories.append(_build_advisory(
            type="SOLAR_FLARE",
            severity="critical",
            title=f"X-Class Solar Flare ({xray})",
            message=(
                f"GOES X-ray flux indicates {xray} flare. "
                f"Immediate HF radio blackout on sunlit side of Earth (R2-R3 conditions). "
                f"Expect: loss of HF comm links, degraded satellite command uplink, "
                f"enhanced ionospheric scintillation affecting GPS and SATCOM."
            ),
            affected_orbits="ALL",
            actions=[
                "Switch to S-band/Ka-band command links",
                "Delay time-critical commands until HF propagation recovers",
                "Monitor for coronal mass ejection (CME) arrival in 24-72 hours",
                "Prepare for potential radiation storm",
            ],
            timestamp=now,
            source="GOES X-Ray Flux",
        ))
    elif xray.startswith("M"):
        advisories.append(_build_advisory(
            type="SOLAR_FLARE",
            severity="warning",
            title=f"M-Class Solar Flare ({xray})",
            message=(
                f"GOES X-ray flux indicates {xray} flare. "
                f"Minor HF radio degradation possible on sunlit side."
            ),
            affected_orbits="ALL",
            actions=[
                "Monitor HF comm link quality",
                "Watch for follow-on X-class flare or CME",
            ],
            timestamp=now,
            source="GOES X-Ray Flux",
        ))

    # --- SURFACE CHARGING (GEO-specific) ---
    if sw_speed > 600 and sw_bz < -10:
        sev = "critical" if sw_speed > 800 else "warning"
        advisories.append(_build_advisory(
            type="SURFACE_CHARGING",
            severity=sev,
            title="Surface Charging Risk — GEO Spacecraft",
            message=(
                f"Solar wind speed = {round(sw_speed)} km/s, Bz = {round(sw_bz, 1)} nT. "
                f"Conditions favorable for differential surface charging on GEO spacecraft. "
                f"Risk of electrostatic discharge (ESD) causing phantom commands or "
                f"component damage."
            ),
            affected_orbits="GEO",
            actions=[
                "Enable frame-level telemetry monitoring for phantom commands",
                "Verify spacecraft grounding bus integrity",
                "Consider safe-mode preparation for critical GEO assets",
                "Monitor for electron flux enhancement at GEO",
            ],
            timestamp=now,
            source="DSCOVR Solar Wind",
        ))

    # --- ORBIT PREDICTION DEGRADED ---
    if kp >= 5:
        advisories.append(_build_advisory(
            type="ORBIT_PREDICTION_DEGRADED",
            severity="warning" if kp < 7 else "critical",
            title="Orbit Prediction Accuracy Degraded",
            message=(
                f"Geomagnetic activity (Kp={kp:.1f}) causing atmospheric density uncertainty. "
                f"Conjunction assessment collision probabilities (Pc) may be "
                f"{'significantly unreliable' if kp >= 7 else 'moderately degraded'}. "
                f"Miss distance estimates for LEO objects have increased uncertainty."
            ),
            affected_orbits="LEO",
            actions=[
                "Apply additional safety margin to conjunction screening thresholds",
                "Request updated ephemerides from operators",
                "Cross-reference with alternative atmospheric models",
                "Increase screening cadence to 4-hourly",
            ],
            timestamp=now,
            source="NOAA/SWPC Kp",
        ))

    # Sort by severity (critical first, then warning, then info)
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    advisories.sort(key=lambda a: severity_order.get(a.get("severity", "info"), 2))

    return advisories


def _build_advisory(**kwargs) -> dict:
    """Build advisory dict from keyword arguments."""
    return {
        "type": kwargs["type"],
        "severity": kwargs["severity"],
        "title": kwargs["title"],
        "message": kwargs["message"],
        "affected_orbits": kwargs["affected_orbits"],
        "actions": kwargs["actions"],
        "timestamp": kwargs["timestamp"],
        "source": kwargs["source"],
    }
