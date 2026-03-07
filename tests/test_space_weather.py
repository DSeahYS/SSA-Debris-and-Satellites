"""Tests for NOAA SWPC Space Weather client."""
import pytest
from unittest.mock import patch, MagicMock
from data.space_weather_client import SpaceWeatherSnapshot, get_current_space_weather


def test_storm_classification_quiet():
    assert SpaceWeatherSnapshot.classify_storm(0.0) == "quiet"
    assert SpaceWeatherSnapshot.classify_storm(3.9) == "quiet"


def test_storm_classification_unsettled():
    assert SpaceWeatherSnapshot.classify_storm(4.0) == "unsettled"
    assert SpaceWeatherSnapshot.classify_storm(4.9) == "unsettled"


def test_storm_classification_storm():
    assert SpaceWeatherSnapshot.classify_storm(5.0) == "storm"
    assert SpaceWeatherSnapshot.classify_storm(6.9) == "storm"


def test_storm_classification_severe():
    assert SpaceWeatherSnapshot.classify_storm(7.0) == "severe_storm"
    assert SpaceWeatherSnapshot.classify_storm(9.0) == "severe_storm"


@patch("data.space_weather_client.fetch_kp_index")
@patch("data.space_weather_client.fetch_f107_flux")
def test_get_current_space_weather(mock_f107, mock_kp):
    """Test that get_current_space_weather assembles data correctly."""
    mock_kp.return_value = [
        {"time_tag": "2025-03-07T12:00:00Z", "estimated_kp": "3.33"}
    ]
    mock_f107.return_value = [
        {"flux": "155.0"}
    ]
    weather = get_current_space_weather()
    assert weather.kp_index == 3.33
    assert weather.f107_flux == 155.0
    assert weather.storm_level == "quiet"
    assert weather.timestamp == "2025-03-07T12:00:00Z"


@patch("data.space_weather_client.fetch_kp_index")
@patch("data.space_weather_client.fetch_f107_flux")
def test_get_weather_handles_empty(mock_f107, mock_kp):
    """Test graceful behavior when APIs return empty data."""
    mock_kp.return_value = []
    mock_f107.return_value = []
    weather = get_current_space_weather()
    assert weather.kp_index == 0.0
    assert weather.f107_flux is None
    assert weather.storm_level == "quiet"
