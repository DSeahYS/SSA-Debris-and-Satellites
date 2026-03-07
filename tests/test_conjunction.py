"""Tests for the conjunction assessment engine."""
import pytest
import numpy as np
from models.conjunction import (
    CloseApproach, _decompose_miss, estimate_avoidance_maneuver
)


def test_risk_classification():
    assert CloseApproach.classify_risk(0.5) == "critical"
    assert CloseApproach.classify_risk(1.0) == "warning"
    assert CloseApproach.classify_risk(3.0) == "warning"
    assert CloseApproach.classify_risk(5.0) == "caution"
    assert CloseApproach.classify_risk(10.0) == "caution"
    assert CloseApproach.classify_risk(25.0) == "nominal"
    assert CloseApproach.classify_risk(100.0) == "nominal"


def test_decompose_miss_radial():
    """Test RIC decomposition: a miss purely in the radial direction."""
    r_pri = np.array([7000.0, 0.0, 0.0])   # Primary at 7000 km on x-axis
    v_pri = np.array([0.0, 7.5, 0.0])       # Velocity in y-direction
    r_sec = np.array([7010.0, 0.0, 0.0])    # Secondary 10 km further radially

    radial, in_track, cross_track = _decompose_miss(r_pri, v_pri, r_sec)
    assert abs(radial - 10.0) < 0.1         # Should be ~10 km radial
    assert abs(in_track) < 0.1               # Should be ~0 in-track
    assert abs(cross_track) < 0.1            # Should be ~0 cross-track


def test_decompose_miss_in_track():
    """Test RIC decomposition: a miss purely in the in-track direction."""
    r_pri = np.array([7000.0, 0.0, 0.0])
    v_pri = np.array([0.0, 7.5, 0.0])
    # Cross-track is r×v = (0,0,52500), so in-track is C×R
    # C = (0,0,1), R = (1,0,0), I = C×R = (0,-1,0)... wait let me recalculate
    # Actually: r_hat = (1,0,0), c_hat = normalize((0,0,52500)) = (0,0,1), i_hat = (0,0,1)×(1,0,0) = (0,1,0)
    # So in-track is the y-direction
    r_sec = np.array([7000.0, 10.0, 0.0])   # 10 km in y (in-track)

    radial, in_track, cross_track = _decompose_miss(r_pri, v_pri, r_sec)
    assert abs(radial) < 0.1
    assert abs(in_track - 10.0) < 0.1
    assert abs(cross_track) < 0.1


def test_decompose_miss_cross_track():
    """Test RIC decomposition: a miss purely in cross-track direction."""
    r_pri = np.array([7000.0, 0.0, 0.0])
    v_pri = np.array([0.0, 7.5, 0.0])
    # cross-track is the z-direction per the frame above
    r_sec = np.array([7000.0, 0.0, 10.0])

    radial, in_track, cross_track = _decompose_miss(r_pri, v_pri, r_sec)
    assert abs(radial) < 0.1
    assert abs(in_track) < 0.1
    assert abs(cross_track - 10.0) < 0.1


def test_avoidance_maneuver_estimate():
    """Test avoidance maneuver generation."""
    approach = CloseApproach(
        primary_name="ISS", primary_norad_id=25544,
        secondary_name="DEBRIS-X", secondary_norad_id=99999,
        tca="2025-03-08T12:00:00Z", tca_jd=2460012.0,
        miss_distance_km=2.0, radial_km=1.5, in_track_km=1.0, cross_track_km=0.8,
        relative_velocity_km_s=10.5, risk_level="warning"
    )
    m = estimate_avoidance_maneuver(approach)
    assert m["execute_minutes_before_tca"] == 45
    assert m["delta_v_m_s"] > 0
    assert m["target_offset_km"] >= 5.0
    assert "direction" in m
    assert m["fuel_cost_estimate"] in ["minimal", "moderate", "significant"]
