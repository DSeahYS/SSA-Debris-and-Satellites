import sys
import os

# Add src to path for absolute imports within tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import pytest
from data.ingestion import load_sample_tle, parse_tle

def test_load_sample_tle():
    tle = load_sample_tle()
    assert isinstance(tle, str)
    assert len(tle.strip().split('\n')) == 2

def test_parse_tle():
    tle = load_sample_tle()
    satellite = parse_tle(tle)
    assert satellite is not None
    # Basic existence check on attributes
    assert hasattr(satellite, 'bstar')
    assert hasattr(satellite, 'inclo')
