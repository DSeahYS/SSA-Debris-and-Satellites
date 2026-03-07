"""Integration tests for the v3 API endpoints."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)

# --- Mock data ---
MOCK_CELESTRAK = [
    {
        "OBJECT_NAME": "ISS (ZARYA)", "OBJECT_ID": "1998-067A",
        "NORAD_CAT_ID": 25544, "EPOCH": "2025-03-07T12:00:00.000000",
        "MEAN_MOTION": 15.50103472, "ECCENTRICITY": 0.0007417,
        "INCLINATION": 51.6416, "RA_OF_ASC_NODE": 295.1294,
        "ARG_OF_PERICENTER": 132.2257, "MEAN_ANOMALY": 49.4412,
        "BSTAR": 0.00036508, "MEAN_MOTION_DOT": 0.00016177,
        "MEAN_MOTION_DDOT": 0, "REV_AT_EPOCH": 99999,
        "ELEMENT_SET_NO": 999, "CLASSIFICATION_TYPE": "U", "EPHEMERIS_TYPE": 0,
    }
]


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "endpoints" in r.json()["data"]


def test_groups():
    r = client.get("/api/v1/groups")
    assert r.status_code == 200
    assert "stations" in r.json()["data"]


@patch("api.server.get_satellite_catalog")
def test_catalog(mock_catalog):
    mock_catalog.return_value = [{"norad_id": 25544, "name": "ISS"}]
    r = client.get("/api/v1/catalog?group=stations")
    assert r.status_code == 200
    assert r.json()["data"][0]["norad_id"] == 25544


@patch("api.server.get_current_space_weather")
def test_space_weather(mock_w):
    from data.space_weather_client import SpaceWeatherSnapshot
    mock_w.return_value = SpaceWeatherSnapshot("2025-03-07T12:00:00Z", 2.5, None, 160.0, "quiet")
    r = client.get("/api/v1/space-weather")
    assert r.status_code == 200
    assert r.json()["data"]["kp_index"] == 2.5


@patch("api.server.fetch_gp_data")
def test_search(mock_fetch):
    mock_fetch.return_value = MOCK_CELESTRAK
    r = client.get("/api/v1/search?q=ISS")
    assert r.status_code == 200
    data = r.json()["data"]
    assert any(s["name"] == "ISS (ZARYA)" for s in data)


@patch("api.server.fetch_gp_data")
def test_search_by_norad_id(mock_fetch):
    mock_fetch.return_value = MOCK_CELESTRAK
    r = client.get("/api/v1/search?q=25544")
    assert r.status_code == 200
    data = r.json()["data"]
    assert any(s["norad_id"] == 25544 for s in data)


def test_search_empty():
    r = client.get("/api/v1/search?q=")
    assert r.status_code == 422  # min_length=1 validation


def test_baseline_no_norad():
    r = client.get("/api/v1/predict/baseline?days=1&steps_per_day=24")
    assert r.status_code == 200
    assert r.json()["meta"]["source"] == "mock"


@patch("api.server._find_omm_by_norad")
def test_conjunctions_not_found(mock_find):
    mock_find.return_value = (None, None)
    r = client.get("/api/v1/conjunctions?norad_id=99999")
    assert r.status_code == 404


def test_baseline_validation():
    r = client.get("/api/v1/predict/baseline?days=0")
    assert r.status_code == 422
