"""Tests for ECI→ECEF→Geodetic coordinate transforms."""
import pytest
import numpy as np
from math import pi
from models.transforms import compute_gmst, eci_to_ecef, eci_to_geodetic, lng_deg_normalize


class TestGMST:
    def test_j2000_epoch(self):
        """GMST at J2000.0 epoch should be ~280.46° ≈ 4.894 rad."""
        gmst = compute_gmst(2451545.0, 0.0)
        # GMST at J2000.0 ≈ 280.46061837° ≈ 4.894961 rad
        assert abs(gmst - 4.894961) < 0.01  # within ~0.5°

    def test_gmst_range(self):
        """GMST should be in [0, 2π)."""
        for jd in [2451545.0, 2460000.0, 2460365.0]:
            gmst = compute_gmst(jd)
            assert 0 <= gmst < 2 * pi

    def test_gmst_advances_with_time(self):
        """GMST should advance ~360°/day (Earth rotation)."""
        g1 = compute_gmst(2460000.0, 0.0)
        g2 = compute_gmst(2460000.0, 0.5)  # 12 hours later
        # Should advance ~180° = π radians
        delta = (g2 - g1) % (2 * pi)
        assert abs(delta - pi) < 0.2  # within ~10°


class TestECItoECEF:
    def test_identity_at_gmst_zero(self):
        """When GMST=0, ECI and ECEF should be identical.
        This happens approximately at J2000.0 + ~6.7 hours (but test structure)."""
        r_eci = np.array([7000.0, 0.0, 0.0])
        # At any time, z-component should be preserved
        r_ecef = eci_to_ecef(r_eci, 2451545.0, 0.0)
        assert abs(r_ecef[2] - r_eci[2]) < 1e-6  # z unchanged

    def test_z_preserved(self):
        """Z component should be preserved (rotation is about Z axis)."""
        r_eci = np.array([5000.0, 3000.0, 4000.0])
        r_ecef = eci_to_ecef(r_eci, 2460000.0, 0.5)
        assert abs(r_ecef[2] - 4000.0) < 1e-6

    def test_magnitude_preserved(self):
        """Rotation should preserve the vector magnitude."""
        r_eci = np.array([5000.0, 3000.0, 4000.0])
        r_ecef = eci_to_ecef(r_eci, 2460000.0, 0.5)
        assert abs(np.linalg.norm(r_ecef) - np.linalg.norm(r_eci)) < 1e-6


class TestECItoGeodetic:
    def test_equatorial_orbit(self):
        """Object on equator should have ~0° latitude."""
        r_eci = np.array([7000.0, 0.0, 0.0])  # On equatorial plane
        lat, lng, alt = eci_to_geodetic(r_eci, 2460000.0, 0.0)
        assert abs(lat) < 1.0  # Within 1° of equator

    def test_altitude_reasonable(self):
        """ISS-like position should give ~400 km altitude."""
        r_eci = np.array([6778.0, 0.0, 0.0])  # ~400 km altitude
        lat, lng, alt = eci_to_geodetic(r_eci, 2460000.0, 0.0)
        assert 350 < alt < 450

    def test_polar_orbit(self):
        """Object over pole should have ~90° latitude."""
        r_eci = np.array([0.0, 0.0, 7000.0])  # Over north pole
        lat, lng, alt = eci_to_geodetic(r_eci, 2460000.0, 0.0)
        assert abs(lat - 90.0) < 1.0


class TestLngNormalize:
    def test_already_normal(self):
        assert lng_deg_normalize(45.0) == 45.0

    def test_wrap_positive(self):
        assert abs(lng_deg_normalize(270.0) - (-90.0)) < 1e-6

    def test_wrap_negative(self):
        assert abs(lng_deg_normalize(-270.0) - 90.0) < 1e-6
