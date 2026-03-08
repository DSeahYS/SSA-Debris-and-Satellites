"""Tests for satellite operator advisory engine."""
import pytest
from models.advisories import generate_advisories


def _weather(**overrides):
    """Create base weather dict with optional overrides."""
    base = {
        "kp_index": 2.0,
        "f107_flux": 120.0,
        "storm_level": "quiet",
        "solar_wind_speed": 350,
        "solar_wind_bz": 2.0,
        "xray_class": "B1.2",
        "proton_gt10mev": 0.5,
        "proton_gt100mev": 0.0,
    }
    base.update(overrides)
    return base


class TestQuietConditions:
    def test_no_advisories(self):
        """Quiet conditions should produce no advisories."""
        advisories = generate_advisories(_weather())
        assert len(advisories) == 0


class TestDragEnhanced:
    def test_kp5_triggers_drag(self):
        """Kp ≥ 5 should trigger DRAG_ENHANCED advisory."""
        advisories = generate_advisories(_weather(kp_index=5.5))
        types = [a["type"] for a in advisories]
        assert "DRAG_ENHANCED" in types

    def test_f107_high_triggers_drag(self):
        """F10.7 > 200 should trigger DRAG_ENHANCED advisory."""
        advisories = generate_advisories(_weather(f107_flux=220))
        types = [a["type"] for a in advisories]
        assert "DRAG_ENHANCED" in types

    def test_kp7_is_critical(self):
        """Kp ≥ 7 should be critical severity."""
        advisories = generate_advisories(_weather(kp_index=7.5))
        drag = [a for a in advisories if a["type"] == "DRAG_ENHANCED"]
        assert drag[0]["severity"] == "critical"


class TestRadiationStorm:
    def test_proton_triggers(self):
        """Proton ≥10 MeV > 10 should trigger RADIATION_STORM."""
        advisories = generate_advisories(_weather(proton_gt10mev=50))
        types = [a["type"] for a in advisories]
        assert "RADIATION_STORM" in types

    def test_severe_proton(self):
        """Very high proton flux should be critical."""
        advisories = generate_advisories(_weather(proton_gt10mev=5000))
        rad = [a for a in advisories if a["type"] == "RADIATION_STORM"]
        assert rad[0]["severity"] == "critical"


class TestGeomagneticStorm:
    def test_kp7_geomagnetic(self):
        """Kp ≥ 7 should trigger GEOMAGNETIC_STORM."""
        advisories = generate_advisories(_weather(kp_index=7.5))
        types = [a["type"] for a in advisories]
        assert "GEOMAGNETIC_STORM" in types

    def test_kp5_moderate(self):
        """Kp = 5 should still trigger geomagnetic advisory."""
        advisories = generate_advisories(_weather(kp_index=5.5))
        types = [a["type"] for a in advisories]
        assert "GEOMAGNETIC_STORM" in types


class TestSolarFlare:
    def test_x_class_critical(self):
        """X-class flare should be critical."""
        advisories = generate_advisories(_weather(xray_class="X2.1"))
        flare = [a for a in advisories if a["type"] == "SOLAR_FLARE"]
        assert flare[0]["severity"] == "critical"

    def test_m_class_warning(self):
        """M-class flare should be warning."""
        advisories = generate_advisories(_weather(xray_class="M5.4"))
        flare = [a for a in advisories if a["type"] == "SOLAR_FLARE"]
        assert flare[0]["severity"] == "warning"


class TestSurfaceCharging:
    def test_high_speed_southward_bz(self):
        """High solar wind + southward Bz should trigger SURFACE_CHARGING."""
        advisories = generate_advisories(_weather(
            solar_wind_speed=700, solar_wind_bz=-15
        ))
        types = [a["type"] for a in advisories]
        assert "SURFACE_CHARGING" in types


class TestPredictionDegraded:
    def test_kp5_degrades_predictions(self):
        """Kp ≥ 5 should trigger ORBIT_PREDICTION_DEGRADED."""
        advisories = generate_advisories(_weather(kp_index=5.5))
        types = [a["type"] for a in advisories]
        assert "ORBIT_PREDICTION_DEGRADED" in types


class TestSorting:
    def test_critical_first(self):
        """Critical advisories should appear before warnings."""
        advisories = generate_advisories(_weather(
            kp_index=8.0, proton_gt10mev=5000, xray_class="X5.0"
        ))
        if len(advisories) >= 2:
            assert advisories[0]["severity"] == "critical"


class TestAdvisoryStructure:
    def test_has_required_fields(self):
        """Each advisory should have all required fields."""
        advisories = generate_advisories(_weather(kp_index=8.0))
        for a in advisories:
            assert "type" in a
            assert "severity" in a
            assert "title" in a
            assert "message" in a
            assert "affected_orbits" in a
            assert "actions" in a
            assert "timestamp" in a
            assert "source" in a
