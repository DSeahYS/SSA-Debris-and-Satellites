"""Integration tests for the v2 API endpoints."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)

# --- Root ---

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "endpoints" in data["data"]

# --- Catalog ---

MOCK_CELESTRAK = [
    {
        "OBJECT_NAME": "ISS (ZARYA)", "OBJECT_ID": "1998-067A",
        "NORAD_CAT_ID": 25544, "EPOCH": "2025-03-07T12:00:00.000000",
        "MEAN_MOTION": 15.50103472, "ECCENTRICITY": 0.0007417,
        "INCLINATION": 51.6416, "RA_OF_ASC_NODE": 295.1294,
        "ARG_OF_PERICENTER": 132.2257, "MEAN_ANOMALY": 49.4412,
        "BSTAR": 0.00036508, "MEAN_MOTION_DOT": 0.00016177,
        "MEAN_MOTION_DDOT": 0, "REV_AT_EPOCH": 99999,
        "ELEMENT_SET_NO": 999, "CLASSIFICATION_TYPE": "U",
        "EPHEMERIS_TYPE": 0,
    }
]

@patch("api.server.get_satellite_catalog")
def test_get_catalog(mock_catalog):
    mock_catalog.return_value = [
        {"norad_id": 25544, "name": "ISS (ZARYA)", "periapsis_km": 418.0, "apoapsis_km": 422.0, "inclination": 51.64, "period_min": 92.83, "epoch": "2025-03-07T12:00:00"}
    ]
    response = client.get("/api/v1/catalog?group=stations")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == "ISS (ZARYA)"
    assert data["meta"]["group"] == "stations"

def test_get_groups():
    response = client.get("/api/v1/groups")
    assert response.status_code == 200
    data = response.json()
    assert "stations" in data["data"]
    assert "starlink" in data["data"]

# --- Space Weather ---

@patch("api.server.get_current_space_weather")
def test_get_space_weather(mock_weather):
    from data.space_weather_client import SpaceWeatherSnapshot
    mock_weather.return_value = SpaceWeatherSnapshot(
        timestamp="2025-03-07T12:00:00Z", kp_index=2.5,
        dst_index=None, f107_flux=165.0, storm_level="quiet"
    )
    response = client.get("/api/v1/space-weather")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["kp_index"] == 2.5
    assert data["data"]["f107_flux"] == 165.0
    assert data["data"]["storm_level"] == "quiet"

# --- Predictions ---

def test_baseline_predictions_mock():
    """Test baseline predictions with mock data (no norad_id)."""
    response = client.get("/api/v1/predict/baseline?days=1&steps_per_day=24")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 24
    assert data["meta"]["source"] == "mock"

@patch("api.server.fetch_gp_data")
def test_baseline_predictions_real_satellite(mock_fetch):
    """Test baseline prediction with a real NORAD ID from CelesTrak data."""
    mock_fetch.return_value = MOCK_CELESTRAK
    response = client.get("/api/v1/predict/baseline?norad_id=25544&group=stations&days=1&steps_per_day=24")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["source"] == "celestrak"
    assert data["meta"]["satellite"] == "ISS (ZARYA)"
    assert len(data["data"]) == 24

@patch("api.server.fetch_gp_data")
def test_baseline_predictions_not_found(mock_fetch):
    """Test 404 when NORAD ID is not in the catalog."""
    mock_fetch.return_value = MOCK_CELESTRAK
    response = client.get("/api/v1/predict/baseline?norad_id=99999&group=stations")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "not_found"

def test_baseline_predictions_validation():
    response = client.get("/api/v1/predict/baseline?days=0")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
