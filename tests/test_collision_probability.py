"""Tests for collision probability engine."""
import pytest
import numpy as np
from models.collision_probability import (
    estimate_position_covariance,
    compute_collision_probability,
    classify_risk_with_pc,
    determine_hard_body_radius,
)


class TestCovarianceEstimation:
    def test_grows_with_epoch_age(self):
        """Covariance should grow with epoch age."""
        cov_fresh = estimate_position_covariance(1.0, 400.0, 0.0001)
        cov_old = estimate_position_covariance(72.0, 400.0, 0.0001)
        assert cov_old[0, 0] > cov_fresh[0, 0]  # radial
        assert cov_old[1, 1] > cov_fresh[1, 1]  # in-track

    def test_in_track_dominates(self):
        """In-track uncertainty should exceed radial and cross-track."""
        cov = estimate_position_covariance(48.0, 400.0, 0.0001)
        assert cov[1, 1] > cov[0, 0]  # in-track > radial
        assert cov[1, 1] > cov[2, 2]  # in-track > cross-track

    def test_high_altitude_lower_uncertainty(self):
        """Higher altitude = less drag = lower uncertainty growth."""
        cov_leo = estimate_position_covariance(48.0, 300.0, 0.0001)
        cov_meo = estimate_position_covariance(48.0, 5000.0, 0.0001)
        assert cov_leo[1, 1] > cov_meo[1, 1]

    def test_debris_higher_uncertainty(self):
        """Debris should have higher uncertainty than payloads."""
        cov_payload = estimate_position_covariance(24.0, 400.0, 0.0001, "PAYLOAD")
        cov_debris = estimate_position_covariance(24.0, 400.0, 0.0001, "DEBRIS")
        assert cov_debris[0, 0] > cov_payload[0, 0]

    def test_diagonal_covariance(self):
        """Covariance should be diagonal (no cross-correlations in this model)."""
        cov = estimate_position_covariance(24.0, 400.0, 0.0001)
        assert cov[0, 1] == 0
        assert cov[0, 2] == 0
        assert cov[1, 2] == 0


class TestCollisionProbability:
    def test_far_apart_zero_pc(self):
        """Objects far apart should have ~0 Pc."""
        r1 = np.array([7000.0, 0.0, 0.0])
        v1 = np.array([0.0, 7.5, 0.0])
        r2 = np.array([7100.0, 0.0, 0.0])  # 100 km apart
        v2 = np.array([0.0, -7.5, 0.0])
        cov = np.diag([1.0, 1.0, 1.0])
        pc = compute_collision_probability(r1, v1, r2, v2, cov, cov)
        assert pc < 1e-10

    def test_near_zero_miss_high_pc(self):
        """Nearly zero miss with small covariance → high Pc."""
        r1 = np.array([7000.0, 0.0, 0.0])
        v1 = np.array([0.0, 7.5, 0.0])
        r2 = np.array([7000.001, 0.0, 0.0])  # 1m apart
        v2 = np.array([0.0, -7.5, 0.0])
        cov = np.diag([0.1, 0.1, 0.1])  # 100m uncertainty
        pc = compute_collision_probability(r1, v1, r2, v2, cov, cov, 0.01)
        assert pc > 0  # Should be non-zero

    def test_pc_between_zero_and_one(self):
        """Pc must always be in [0, 1]."""
        r1 = np.array([7000.0, 0.0, 0.0])
        v1 = np.array([0.0, 7.5, 0.0])
        r2 = np.array([7005.0, 0.0, 0.0])
        v2 = np.array([0.0, -7.5, 0.0])
        cov = np.diag([1.0, 10.0, 1.0])
        pc = compute_collision_probability(r1, v1, r2, v2, cov, cov)
        assert 0 <= pc <= 1

    def test_zero_relative_velocity(self):
        """Zero relative velocity → Pc = 0 (co-orbiting)."""
        r1 = np.array([7000.0, 0.0, 0.0])
        v1 = np.array([0.0, 7.5, 0.0])
        r2 = np.array([7005.0, 0.0, 0.0])
        v2 = np.array([0.0, 7.5, 0.0])  # Same velocity
        cov = np.diag([1.0, 1.0, 1.0])
        pc = compute_collision_probability(r1, v1, r2, v2, cov, cov)
        assert pc == 0.0


class TestRiskWithPc:
    def test_critical_by_pc(self):
        assert classify_risk_with_pc(10.0, 1e-3) == "critical"

    def test_warning_by_pc(self):
        assert classify_risk_with_pc(10.0, 5e-5) == "warning"

    def test_caution_by_pc(self):
        assert classify_risk_with_pc(30.0, 1e-6) == "caution"

    def test_nominal_low_pc(self):
        assert classify_risk_with_pc(50.0, 1e-10) == "nominal"

    def test_critical_by_miss(self):
        assert classify_risk_with_pc(0.5, 1e-10) == "critical"


class TestHardBodyRadius:
    def test_debris(self):
        assert determine_hard_body_radius("COSMOS 2251 DEB") == 0.001

    def test_rocket_body(self):
        assert determine_hard_body_radius("CZ-2C R/B") == 0.005

    def test_payload(self):
        assert determine_hard_body_radius("ISS (ZARYA)") == 0.010
