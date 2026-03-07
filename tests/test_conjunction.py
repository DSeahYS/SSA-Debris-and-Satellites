"""
Tests for Conjunction Assessment Engine v2 (Smart Sieve)
Covers: risk classification, RIC decomposition, Smart Sieve filtering,
        maneuver estimation (all branches), and screening loop with mock data.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock
from models.conjunction import (
    CloseApproach,
    _decompose_miss,
    estimate_avoidance_maneuver,
    orbital_sieve,
    screen_conjunctions,
)


# ═══════════════════════════════════════
# Helper: mock OMMRecord
# ═══════════════════════════════════════
def make_omm(norad_id=25544, name="ISS", inclination=51.6,
             periapsis_km=415.0, apoapsis_km=420.0,
             eccentricity=0.0004, mean_motion=15.5,
             epoch="2026-03-07T06:00:00.000000"):
    """Create a mock OMMRecord for testing."""
    omm = MagicMock()
    omm.norad_cat_id = norad_id
    omm.object_name = name
    omm.inclination = inclination
    omm.periapsis_km = periapsis_km
    omm.apoapsis_km = apoapsis_km
    omm.eccentricity = eccentricity
    omm.mean_motion = mean_motion
    omm.epoch = epoch
    omm.bstar = 0.0001
    omm.arg_of_pericenter = 0.0
    omm.mean_anomaly = 0.0
    omm.ra_of_asc_node = 0.0
    omm.mean_motion_dot = 0.0
    return omm


# ═══════════════════════════════════════
# Risk Classification
# ═══════════════════════════════════════
class TestRiskClassification:
    def test_critical(self):
        assert CloseApproach.classify_risk(0.5) == "critical"

    def test_warning(self):
        assert CloseApproach.classify_risk(3.0) == "warning"

    def test_caution(self):
        assert CloseApproach.classify_risk(15.0) == "caution"

    def test_nominal(self):
        assert CloseApproach.classify_risk(50.0) == "nominal"

    def test_boundary_1km(self):
        assert CloseApproach.classify_risk(1.0) == "warning"

    def test_boundary_5km(self):
        assert CloseApproach.classify_risk(5.0) == "caution"

    def test_boundary_25km(self):
        assert CloseApproach.classify_risk(25.0) == "nominal"


# ═══════════════════════════════════════
# RIC Decomposition
# ═══════════════════════════════════════
class TestRICDecomposition:
    def test_radial_miss(self):
        r_pri = np.array([7000.0, 0.0, 0.0])
        v_pri = np.array([0.0, 7.5, 0.0])
        r_sec = np.array([7010.0, 0.0, 0.0])
        r, i, c = _decompose_miss(r_pri, v_pri, r_sec)
        assert abs(r - 10.0) < 0.1
        assert abs(i) < 0.1
        assert abs(c) < 0.1

    def test_in_track_miss(self):
        r_pri = np.array([7000.0, 0.0, 0.0])
        v_pri = np.array([0.0, 7.5, 0.0])
        r_sec = np.array([7000.0, 10.0, 0.0])
        r, i, c = _decompose_miss(r_pri, v_pri, r_sec)
        assert abs(r) < 0.1
        assert abs(i - 10.0) < 0.1

    def test_cross_track_miss(self):
        r_pri = np.array([7000.0, 0.0, 0.0])
        v_pri = np.array([0.0, 7.5, 0.0])
        r_sec = np.array([7000.0, 0.0, 10.0])
        r, i, c = _decompose_miss(r_pri, v_pri, r_sec)
        assert abs(c - 10.0) < 0.1

    def test_combined_miss(self):
        r_pri = np.array([7000.0, 0.0, 0.0])
        v_pri = np.array([0.0, 7.5, 0.0])
        r_sec = np.array([7005.0, 3.0, 2.0])
        r, i, c = _decompose_miss(r_pri, v_pri, r_sec)
        total = np.sqrt(r**2 + i**2 + c**2)
        expected = np.linalg.norm(r_sec - r_pri)
        assert abs(total - expected) < 0.01


# ═══════════════════════════════════════
# Smart Sieve (orbital_sieve)
# ═══════════════════════════════════════
class TestOrbitalSieve:
    def test_passes_same_altitude_band(self):
        """Object in same altitude band should pass the sieve."""
        pri = make_omm(norad_id=1, periapsis_km=400, apoapsis_km=420)
        sec = make_omm(norad_id=2, periapsis_km=410, apoapsis_km=430)
        result = orbital_sieve(pri, [sec], threshold_km=50)
        assert len(result) == 1

    def test_rejects_high_orbit(self):
        """GEO satellite should be rejected when screening LEO primary."""
        pri = make_omm(norad_id=1, periapsis_km=400, apoapsis_km=420)
        geo = make_omm(norad_id=2, periapsis_km=35780, apoapsis_km=35790)
        result = orbital_sieve(pri, [geo], threshold_km=50)
        assert len(result) == 0

    def test_rejects_low_orbit(self):
        """Very low orbit rejected against higher primary."""
        pri = make_omm(norad_id=1, periapsis_km=800, apoapsis_km=820)
        low = make_omm(norad_id=2, periapsis_km=200, apoapsis_km=220)
        result = orbital_sieve(pri, [low], threshold_km=50)
        assert len(result) == 0

    def test_skips_self(self):
        """Primary should not be included in results."""
        pri = make_omm(norad_id=1, periapsis_km=400, apoapsis_km=420)
        result = orbital_sieve(pri, [pri], threshold_km=50)
        assert len(result) == 0

    def test_skips_bad_data(self):
        """Objects with zero/negative periapsis should be skipped."""
        pri = make_omm(norad_id=1, periapsis_km=400, apoapsis_km=420)
        bad = make_omm(norad_id=2, periapsis_km=0, apoapsis_km=0)
        result = orbital_sieve(pri, [bad], threshold_km=50)
        assert len(result) == 0

    def test_margin_allows_edge_cases(self):
        """Altitude just outside threshold should still pass due to margin."""
        pri = make_omm(norad_id=1, periapsis_km=400, apoapsis_km=420)
        # Secondary perigee is 90km above primary apogee, but margin is 100km
        edge = make_omm(norad_id=2, periapsis_km=510, apoapsis_km=530)
        result = orbital_sieve(pri, [edge], threshold_km=50)
        assert len(result) == 1

    def test_inclination_filter_extreme(self):
        """Extreme inclination diff in circular LEO should be filtered."""
        pri = make_omm(norad_id=1, periapsis_km=400, apoapsis_km=420, inclination=5.0)
        polar = make_omm(norad_id=2, periapsis_km=410, apoapsis_km=420, inclination=98.0)
        result = orbital_sieve(pri, [polar], threshold_km=50)
        # Should be filtered — 93° diff in near-circular LEO
        assert len(result) == 0

    def test_inclination_allows_moderate_diff(self):
        """Moderate inclination difference should pass."""
        pri = make_omm(norad_id=1, periapsis_km=400, apoapsis_km=420, inclination=51.6)
        sec = make_omm(norad_id=2, periapsis_km=410, apoapsis_km=420, inclination=28.5)
        result = orbital_sieve(pri, [sec], threshold_km=50)
        assert len(result) == 1

    def test_mixed_catalog(self):
        """Mixed catalog: some should pass, some should be filtered."""
        pri = make_omm(norad_id=1, periapsis_km=400, apoapsis_km=420, inclination=51.6)
        catalog = [
            make_omm(norad_id=2, periapsis_km=410, apoapsis_km=430),  # PASS
            make_omm(norad_id=3, periapsis_km=35780, apoapsis_km=35790),  # REJECT (GEO)
            make_omm(norad_id=4, periapsis_km=415, apoapsis_km=425),  # PASS
            make_omm(norad_id=5, periapsis_km=100, apoapsis_km=120),  # REJECT (too low)
        ]
        result = orbital_sieve(pri, catalog, threshold_km=50)
        assert len(result) == 2


# ═══════════════════════════════════════
# Maneuver Estimation
# ═══════════════════════════════════════
class TestManeuverEstimation:
    def _make_approach(self, miss_km, risk="warning"):
        return CloseApproach(
            primary_name="ISS", primary_norad_id=25544,
            secondary_name="DEBRIS", secondary_norad_id=99999,
            tca="2026-03-07T12:00:00Z", tca_jd=2460000.0,
            miss_distance_km=miss_km, radial_km=miss_km*0.5,
            in_track_km=miss_km*0.3, cross_track_km=miss_km*0.2,
            relative_velocity_km_s=7.0, risk_level=risk,
        )

    def test_minimal_fuel_cost(self):
        m = estimate_avoidance_maneuver(self._make_approach(2.0))
        assert m["fuel_cost_estimate"] == "minimal"
        assert m["delta_v_m_s"] > 0

    def test_moderate_fuel_cost(self):
        m = estimate_avoidance_maneuver(self._make_approach(8.0))
        assert m["fuel_cost_estimate"] == "moderate"

    def test_significant_fuel_cost(self):
        m = estimate_avoidance_maneuver(self._make_approach(20.0))
        assert m["fuel_cost_estimate"] == "significant"

    def test_minimum_offset(self):
        """Even tiny miss should produce at least 5km offset."""
        m = estimate_avoidance_maneuver(self._make_approach(0.1))
        assert m["target_offset_km"] >= 5.0

    def test_direction_is_cross_track(self):
        m = estimate_avoidance_maneuver(self._make_approach(1.0))
        assert "cross-track" in m["direction"]

    def test_execute_timing(self):
        m = estimate_avoidance_maneuver(self._make_approach(1.0))
        assert m["execute_minutes_before_tca"] == 45

    def test_has_note(self):
        m = estimate_avoidance_maneuver(self._make_approach(1.0))
        assert "note" in m
        assert len(m["note"]) > 10


# ═══════════════════════════════════════
# Screening Loop (with mock OMMRecords)
# ═══════════════════════════════════════
class TestScreenConjunctions:
    def test_empty_secondaries(self):
        pri = make_omm(norad_id=1)
        result = screen_conjunctions(pri, [], hours=1, step_seconds=60)
        assert result == []

    def test_self_excluded(self):
        """Primary should not appear in conjunction results with itself."""
        pri = make_omm(norad_id=25544)
        result = screen_conjunctions(pri, [pri], hours=1, step_seconds=60)
        assert all(r.secondary_norad_id != 25544 for r in result)

    def test_geo_filtered_out(self):
        """GEO objects should be filtered by sieve when primary is LEO."""
        pri = make_omm(norad_id=1, periapsis_km=400, apoapsis_km=420)
        geo = make_omm(norad_id=2, periapsis_km=35780, apoapsis_km=35790, name="GEO-SAT")
        result = screen_conjunctions(pri, [geo], hours=1, step_seconds=60)
        assert len(result) == 0
