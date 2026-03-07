"""Tests for CelesTrak client."""
import pytest
from unittest.mock import patch, MagicMock
from data.celestrak_client import parse_omm_records, OMMRecord, get_satellite_catalog

# Mock CelesTrak JSON data (one ISS-like record)
MOCK_CELESTRAK_JSON = [
    {
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "NORAD_CAT_ID": 25544,
        "EPOCH": "2025-03-07T12:00:00.000000",
        "MEAN_MOTION": 15.50103472,
        "ECCENTRICITY": 0.0007417,
        "INCLINATION": 51.6416,
        "RA_OF_ASC_NODE": 295.1294,
        "ARG_OF_PERICENTER": 132.2257,
        "MEAN_ANOMALY": 49.4412,
        "BSTAR": 0.00036508,
        "MEAN_MOTION_DOT": 0.00016177,
        "MEAN_MOTION_DDOT": 0,
        "REV_AT_EPOCH": 99999,
        "ELEMENT_SET_NO": 999,
        "CLASSIFICATION_TYPE": "U",
        "EPHEMERIS_TYPE": 0,
    }
]


def test_parse_omm_records():
    """Test parsing CelesTrak JSON into OMMRecord dataclasses."""
    records = parse_omm_records(MOCK_CELESTRAK_JSON)
    assert len(records) == 1
    iss = records[0]
    assert isinstance(iss, OMMRecord)
    assert iss.object_name == "ISS (ZARYA)"
    assert iss.norad_cat_id == 25544
    assert iss.inclination == 51.6416
    # Derived parameters should be computed
    assert iss.semimajor_axis_km > 6370  # Should be Earth radius + altitude
    assert iss.period_min > 90  # ISS period ~92 min
    assert iss.periapsis_km > 300  # ISS perigee > 300 km
    assert iss.apoapsis_km > 300  # ISS apogee > 300 km


def test_parse_omm_records_handles_malformed():
    """Test that malformed records are skipped gracefully."""
    bad_data = [{"OBJECT_NAME": "BAD", "MEAN_MOTION": "not_a_number"}]
    records = parse_omm_records(bad_data)
    assert len(records) == 0


def test_parse_omm_records_empty():
    """Test parsing empty data returns empty list."""
    records = parse_omm_records([])
    assert records == []


@patch("data.celestrak_client.fetch_gp_data")
def test_get_satellite_catalog(mock_fetch):
    """Test catalog generation from OMM records."""
    mock_fetch.return_value = MOCK_CELESTRAK_JSON
    catalog = get_satellite_catalog("stations")
    assert len(catalog) == 1
    assert catalog[0]["name"] == "ISS (ZARYA)"
    assert catalog[0]["norad_id"] == 25544
    assert "periapsis_km" in catalog[0]
    assert "apoapsis_km" in catalog[0]
