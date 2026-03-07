import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from models.baseline_sgp4 import SGP4Baseline
from data.ingestion import load_sample_tle, parse_tle

def test_sgp4_prediction():
    tle = load_sample_tle()
    sat = parse_tle(tle)
    baseline = SGP4Baseline(sat)
    
    jd, fr = sat.jdsatepoch, sat.jdsatepochF
    e, r, v = baseline.predict(jd, fr)
    
    assert e == 0
    assert r is not None
    assert v is not None
    assert len(r) == 3
    assert len(v) == 3

def test_sgp4_prediction_window():
    tle = load_sample_tle()
    sat = parse_tle(tle)
    baseline = SGP4Baseline(sat)
    
    jd, fr = sat.jdsatepoch, sat.jdsatepochF
    # mock a short 1-day window
    predictions = baseline.predict_window(jd, fr, days=1, steps_per_day=4)
    assert len(predictions) > 0
    assert len(predictions) == 4
