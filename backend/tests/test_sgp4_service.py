import pytest
from datetime import datetime, timezone
from app.services.sgp4_service import propagate_tle

def test_propagate_iss_tle():
    # Known ISS TLE
    line1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9992"
    line2 = "2 25544  51.6402 180.0000 0001000   0.0000   0.0000 15.50000000000000"
    
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    state = propagate_tle(line1, line2, dt)
    
    assert state is not None
    assert "altitude_km" in state
    assert "latitude_deg" in state
    assert "longitude_deg" in state
    assert "velocity_km_s" in state
    
    # ISS is in LEO, approx 400-430km altitude
    assert 400 <= state["altitude_km"] <= 450
    # Velocity is approx 7.6 km/s
    assert 7.0 <= state["velocity_km_s"] <= 8.0
    # Inclination is approx 51.6 deg
    assert 51.5 <= state["inclination_deg"] <= 51.7
    # Eccentricity should be very low
    assert 0 <= state["eccentricity"] < 0.1
