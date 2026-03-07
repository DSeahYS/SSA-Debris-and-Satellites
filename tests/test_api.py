import pytest
from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "message" in data["data"]

def test_get_baseline_predictions_success():
    response = client.get("/api/v1/predict/baseline?days=1&steps_per_day=24")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 24
    
    # Check first coordinate structure
    first_coord = data["data"][0]
    assert "lat" in first_coord
    assert "lng" in first_coord
    assert "alt" in first_coord
    assert "time_jd" in first_coord

def test_get_baseline_predictions_validation_error_days():
    # Test invalid days (0 is below minimum 1)
    response = client.get("/api/v1/predict/baseline?days=0&steps_per_day=24")
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "validation_error"
    assert len(data["error"]["details"]) > 0
    assert data["error"]["details"][0]["field"] == "query.days"
    
def test_get_baseline_predictions_validation_error_steps():
    # Test invalid steps (over max 1440)
    response = client.get("/api/v1/predict/baseline?days=1&steps_per_day=5000")
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "validation_error"
    assert len(data["error"]["details"]) > 0
    assert data["error"]["details"][0]["field"] == "query.steps_per_day"

def test_get_baseline_predictions_validation_error_type():
    # Test invalid type (string instead of int)
    response = client.get("/api/v1/predict/baseline?days=abc")
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "validation_error"
