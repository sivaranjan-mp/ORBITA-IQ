import pytest
import logging
from datetime import datetime, timezone
from app.services.tle_parser import parse_tle
from app.services.sgp4_service import propagate_tle
from app.models.satellites import OrbitState
import uuid

def test_parse_tle_valid():
    """
    Unit test: call parse_tle() with a valid TLE and confirm real lat/lon/vel
    values are returned (not None, not 0.0).
    """
    valid_tle = (
        "ISS (ZARYA)\n"
        "1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n"
        "2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"
    )

    parsed = parse_tle(valid_tle)

    assert parsed["name"] == "ISS (ZARYA)"
    assert parsed["norad_id"] == 25544
    assert parsed["latitudeDeg"] is not None
    assert parsed["longitudeDeg"] is not None
    assert parsed["velocityKmS"] is not None
    assert parsed["altitudeKm"] is not None

    # ISS altitude and velocity checks
    assert 200 <= parsed["altitudeKm"] <= 600
    assert 7.0 <= parsed["velocityKmS"] <= 8.5
    assert -90.0 <= parsed["latitudeDeg"] <= 90.0
    assert -180.0 <= parsed["longitudeDeg"] <= 180.0


def test_parse_tle_invalid_lines():
    """
    Unit test: call parse_tle() with fewer than 2 lines.
    """
    with pytest.raises(ValueError, match="Invalid TLE string: must contain at least 2 lines."):
        parse_tle("ONLY ONE LINE")


def test_parse_tle_corrupted_elements_raises_value_error(caplog):
    """
    Unit test: call parse_tle() with a deliberately corrupted/decayed TLE string
    where SGP4 fails propagation at both now and epoch.
    Confirm it raises ValueError instead of returning fabricated 0.0 values.
    """
    # Corrupted TLE lines that cause SGP4 error code (e != 0)
    corrupted_tle = (
        "CORRUPTED SATELLITE\n"
        "1 99999U 99999A   24001.00000000  .00000000  00000-0  00000-0 0  9999\n"
        "2 99999   0.0000   0.0000 9999999   0.0000   0.0000  0.00000000000000"
    )

    with caplog.at_level(logging.WARNING):
        with pytest.raises(ValueError) as exc_info:
            parse_tle(corrupted_tle)

        assert "TLE could not be propagated" in str(exc_info.value)
        # Verify SGP4 warning was logged
        assert any("SGP4 propagation" in record.message for record in caplog.records)


def test_sgp4_propagation_logging_on_error(caplog):
    """
    Unit test: propagate_tle logs warning with error code when propagation fails.
    """
    line1 = "1 99999U 99999A   24001.00000000  .00000000  00000-0  00000-0 0  9999"
    line2 = "2 99999   0.0000   0.0000 9999999   0.0000   0.0000  0.00000000000000"
    dt = datetime.now(timezone.utc)

    with caplog.at_level(logging.WARNING):
        result = propagate_tle(line1, line2, dt)
        assert result is None
        assert any("SGP4 propagation error code" in record.message or "SGP4 propagation exception" in record.message for record in caplog.records)


def test_orbit_state_model_nullable_fields():
    """
    Unit test: OrbitState model allows None for latitude_deg, longitude_deg, velocity_km_s.
    """
    state = OrbitState(
        satellite_id=uuid.uuid4(),
        altitude_km=400.0,
        latitude_deg=None,
        longitude_deg=None,
        velocity_km_s=None,
        inclination_deg=51.6,
        period_minutes=92.0,
        eccentricity=0.001,
        raan_deg=100.0,
        mean_anomaly_deg=200.0,
        epoch=datetime.now(timezone.utc)
    )

    assert state.latitude_deg is None
    assert state.longitude_deg is None
    assert state.velocity_km_s is None
