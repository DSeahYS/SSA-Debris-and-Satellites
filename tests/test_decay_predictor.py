"""Tests for orbit decay predictor."""
import pytest
from models.decay_predictor import (
    estimate_decay_rate,
    predict_reentry,
    get_decaying_objects,
    _get_atmosphere_density,
    _apply_solar_activity_scaling,
)
from unittest.mock import MagicMock


class TestAtmosphereDensity:
    def test_decreases_with_altitude(self):
        """Density should decrease with altitude."""
        rho_200 = _get_atmosphere_density(200)
        rho_400 = _get_atmosphere_density(400)
        rho_800 = _get_atmosphere_density(800)
        assert rho_200 > rho_400 > rho_800

    def test_positive(self):
        """Density should always be positive."""
        for alt in [100, 200, 300, 400, 500, 600, 800, 1000]:
            assert _get_atmosphere_density(alt) > 0


class TestSolarActivityScaling:
    def test_high_f107_increases_density(self):
        """High solar flux should increase density."""
        rho_base = 1e-12
        rho_low = _apply_solar_activity_scaling(rho_base, 70, 0)
        rho_high = _apply_solar_activity_scaling(rho_base, 250, 0)
        assert rho_high > rho_low

    def test_high_kp_increases_density(self):
        """High Kp should increase density."""
        rho_base = 1e-12
        rho_quiet = _apply_solar_activity_scaling(rho_base, 150, 0)
        rho_stormy = _apply_solar_activity_scaling(rho_base, 150, 7)
        assert rho_stormy > rho_quiet


class TestDecayRate:
    def test_iss_decays(self):
        """ISS at ~420 km should have measurable decay."""
        rate = estimate_decay_rate(415, 420, 0.00036508)
        assert rate > 0

    def test_geo_no_decay(self):
        """GEO orbit should have zero decay."""
        rate = estimate_decay_rate(35780, 35790, 0.0001)
        assert rate == 0.0

    def test_higher_f107_faster_decay(self):
        """Higher solar flux → faster decay."""
        rate_low = estimate_decay_rate(400, 420, 0.0001, f107_flux=70)
        rate_high = estimate_decay_rate(400, 420, 0.0001, f107_flux=250)
        assert rate_high > rate_low

    def test_lower_altitude_faster_decay(self):
        """Lower altitude → faster decay."""
        rate_low = estimate_decay_rate(200, 220, 0.0001)
        rate_high = estimate_decay_rate(600, 620, 0.0001)
        assert rate_low > rate_high


class TestPredictReentry:
    def test_iss_not_imminent(self):
        """ISS at ~420 km should not be imminent re-entry."""
        pred = predict_reentry(25544, "ISS", 415, 420, 0.00036508)
        assert pred.risk_level != "imminent"
        assert pred.estimated_days_to_reentry > 7

    def test_very_low_orbit_imminent(self):
        """Object at 150 km should have very short re-entry."""
        pred = predict_reentry(99999, "LOW-SAT", 150, 160, 0.001)
        assert pred.estimated_days_to_reentry < 365

    def test_geo_stable(self):
        """GEO satellite should be stable."""
        pred = predict_reentry(99998, "GEO-SAT", 35780, 35790, 0.0001)
        assert pred.risk_level == "stable"

    def test_leo_band(self):
        pred = predict_reentry(25544, "ISS", 415, 420, 0.0001)
        assert pred.altitude_band == "LEO"


class TestGetDecayingObjects:
    def test_filters_by_threshold(self):
        """Should only return objects within threshold."""
        geo = MagicMock()
        geo.periapsis_km = 35780
        geo.apoapsis_km = 35790
        geo.bstar = 0.0001
        geo.norad_cat_id = 1
        geo.object_name = "GEO-SAT"

        result = get_decaying_objects([geo], threshold_days=365)
        assert len(result) == 0  # GEO won't re-enter in 365 days

    def test_skips_invalid(self):
        """Should skip objects with invalid data."""
        bad = MagicMock()
        bad.periapsis_km = 0
        bad.apoapsis_km = 0
        bad.bstar = 0
        bad.norad_cat_id = 1
        bad.object_name = "BAD"

        result = get_decaying_objects([bad])
        assert len(result) == 0
