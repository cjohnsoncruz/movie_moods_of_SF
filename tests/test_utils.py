import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from movie_moods_of_SF.src.utils import haversine

def test_haversine_zero_distance():
    assert haversine(0, 0, 0, 0) == 0

def test_haversine_sf_to_ny():
    # SF: 37.7749, -122.4194; NY: 40.7128, -74.0060
    d = haversine(37.7749, -122.4194, 40.7128, -74.0060)
    assert 4100000 < d < 4200000  # meters
