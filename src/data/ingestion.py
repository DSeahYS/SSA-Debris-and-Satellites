import os
import urllib.request
from datetime import datetime
from sgp4.api import Satrec, WGS84

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')

def load_sample_tle():
    """
    Returns a mocked TLE (Two-Line Element) string for testing purposes.
    In the real system, this will fetch from Space-Track or a proprietary database.
    This TLE is for the ISS.
    """
    return (
        "1 25544U 98067A   20282.49392593  .00000673  00000-0  19198-4 0  9990\n"
        "2 25544  51.6443 273.7432 0001305 289.0560 178.6830 15.49202525249590"
    )

def parse_tle(tle_string):
    """
    Parses a TLE string into an sgp4 Satrec object.
    
    Args:
        tle_string (str): A string containing both lines of the TLE separated by a newline.
    
    Returns:
        sgp4.api.Satrec: The parsed satellite record object.
    """
    lines = tle_string.strip().split('\n')
    if len(lines) != 2:
        raise ValueError("TLE string must contain exactly two lines.")
    
    satellite = Satrec.twoline2rv(lines[0], lines[1])
    return satellite
