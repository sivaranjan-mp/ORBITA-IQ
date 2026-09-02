import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.auth import UserProfile
from app.models.satellites import Satellite, OrbitState, TLERecord
from app.services.satellite_service import SatelliteService
from app.api.v1.endpoints.satellites import _format_satellite_response

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()

def test_add_satellite_by_norad_mock():
    admin_user = UserProfile(
        id="user-123",
        employee_id="EMP-0001",
        email="admin@example.com",
        full_name="Admin User",
        role="admin",
        is_active=True
    )
    
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_res.scalar_one.return_value = Satellite(
        id=uuid.uuid4(),
        norad_id=25544,
        name="ISS (ZARYA)",
        object_type="payload",
        status="active"
    )
    mock_db.execute.return_value = mock_res
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    sample_tle = "ISS (ZARYA)\n1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"
    
    with patch("app.services.celestrak_service.fetch_tle_by_norad_id", return_value=sample_tle):
        response = client.post("/api/v1/satellites/norad", json={"norad_id": 25544})
        assert response.status_code == 200


def test_add_satellite_manual_success():
    operator_user = UserProfile(
        id="user-456",
        employee_id="EMP-0002",
        email="operator@example.com",
        full_name="Operator User",
        role="operator",
        is_active=True
    )
    app.dependency_overrides[get_current_user] = lambda: operator_user

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_res.scalar_one.return_value = Satellite(
        id=uuid.uuid4(),
        norad_id=25544,
        name="ISS (ZARYA)",
        object_type="payload",
        status="active"
    )
    mock_db.execute.return_value = mock_res
    app.dependency_overrides[get_db] = lambda: mock_db

    sample_tle = "ISS (ZARYA)\n1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"

    response = client.post("/api/v1/satellites/manual", json={"raw_tle": sample_tle})
    assert response.status_code == 200
    data = response.json()
    assert data["noradId"] == 25544
    assert data["name"] == "ISS (ZARYA)"


def test_add_satellite_manual_2line_fallback_to_celestrak():
    operator_user = UserProfile(
        id="user-456",
        employee_id="EMP-0002",
        email="operator@example.com",
        full_name="Operator User",
        role="operator",
        is_active=True
    )
    app.dependency_overrides[get_current_user] = lambda: operator_user

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_res.scalar_one.return_value = Satellite(
        id=uuid.uuid4(),
        norad_id=25544,
        name="ISS (ZARYA)",
        object_type="payload",
        status="active"
    )
    mock_db.execute.return_value = mock_res
    app.dependency_overrides[get_db] = lambda: mock_db

    # 2-line TLE without line 0
    tle_2line = (
        "1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n"
        "2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"
    )
    celestrak_3line = "ISS (ZARYA)\n1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"

    with patch("app.services.satellite_service.fetch_tle_by_norad_id", return_value=celestrak_3line) as mock_fetch:
        response = client.post("/api/v1/satellites/manual", json={"raw_tle": tle_2line})
        assert response.status_code == 200
        data = response.json()
        assert data["noradId"] == 25544
        assert data["name"] == "ISS (ZARYA)"
        assert mock_fetch.called


def test_add_satellite_manual_3le_with_0_prefix():
    operator_user = UserProfile(
        id="user-456",
        employee_id="EMP-0002",
        email="operator@example.com",
        full_name="Operator User",
        role="operator",
        is_active=True
    )
    app.dependency_overrides[get_current_user] = lambda: operator_user

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_res.scalar_one.return_value = Satellite(
        id=uuid.uuid4(),
        norad_id=25544,
        name="ISS (ZARYA)",
        object_type="payload",
        status="active"
    )
    mock_db.execute.return_value = mock_res
    app.dependency_overrides[get_db] = lambda: mock_db

    # 3LE with '0 ' prefix
    tle_3le = (
        "0 ISS (ZARYA)\n"
        "1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n"
        "2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"
    )

    response = client.post("/api/v1/satellites/manual", json={"raw_tle": tle_3le})
    assert response.status_code == 200
    data = response.json()
    assert data["noradId"] == 25544
    assert data["name"] == "ISS (ZARYA)"



def test_add_satellite_manual_invalid_tle():
    admin_user = UserProfile(
        id="user-123",
        employee_id="EMP-0001",
        email="admin@example.com",
        full_name="Admin User",
        role="admin",
        is_active=True
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post("/api/v1/satellites/manual", json={"raw_tle": "INVALID TLE LINE"})
    assert response.status_code == 422


def test_add_satellite_manual_unauthenticated():
    sample_tle = "ISS (ZARYA)\n1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"
    response = client.post("/api/v1/satellites/manual", json={"raw_tle": sample_tle})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_add_satellite_from_tle_regression_orbit_state_access():
    """
    Regression test: ensures add_satellite_from_tle re-fetches and returns a
    Satellite object with .orbit_state accessible (preventing 'greenlet_spawn has
    not been called' during _format_satellite_response or subsequent relationship reads).
    """
    sample_tle = (
        "ISS (ZARYA)\n"
        "1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n"
        "2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    expected_sat = Satellite(
        id=uuid.uuid4(),
        norad_id=25544,
        name="ISS (ZARYA)",
        international_designator="98067A",
        object_type="payload",
        status="active",
        owner_org="EMP-0001"
    )
    expected_sat.orbit_state = OrbitState(
        altitude_km=420.0,
        latitude_deg=10.5,
        longitude_deg=-20.5,
        velocity_km_s=7.65,
        inclination_deg=51.64,
        period_minutes=92.5,
        eccentricity=0.0005,
        raan_deg=261.24,
        mean_anomaly_deg=334.85,
        epoch=datetime.now(timezone.utc)
    )

    res1 = MagicMock()
    res1.scalar_one_or_none.return_value = None
    res2 = MagicMock()
    res2.scalar_one.return_value = expected_sat

    mock_db.execute.side_effect = [res1, res2]

    service = SatelliteService(mock_db)
    sat = await service.add_satellite_from_tle(sample_tle, owner_org="EMP-0001")

    # Assert orbit_state is loaded and accessible directly
    assert sat.orbit_state is not None
    assert sat.orbit_state.altitude_km == 420.0
    assert sat.orbit_state.latitude_deg == 10.5
    assert sat.orbit_state.longitude_deg == -20.5
    assert sat.orbit_state.velocity_km_s == 7.65

    # Assert _format_satellite_response operates smoothly without async lazy load errors
    formatted = _format_satellite_response(sat, owner_name="Admin User")
    assert formatted["noradId"] == 25544
    assert formatted["altitudeKm"] == 420.0
    assert formatted["latitudeDeg"] == 10.5
    assert formatted["longitudeDeg"] == -20.5
    assert formatted["velocityKmS"] == 7.65
    assert formatted["name"] == "ISS (ZARYA)"
    assert formatted["ownerName"] == "Admin User"
    assert formatted["ownerEmployeeId"] == "EMP-0001"


def test_list_satellites_returns_owner_details():
    admin_user = UserProfile(
        id="user-123",
        employee_id="EMP-0001",
        email="admin@example.com",
        full_name="Admin User",
        role="admin",
        is_active=True
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user

    mock_db = AsyncMock()
    sat = Satellite(
        id=uuid.uuid4(),
        norad_id=25544,
        name="ISS (ZARYA)",
        owner_org="EMP-0001",
        object_type="payload",
        status="active"
    )
    mock_res = MagicMock()
    mock_res.scalars().all.return_value = [sat]
    mock_db.execute.return_value = mock_res
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_admin = MagicMock()
    mock_admin.table.return_value.select.return_value.execute.return_value.data = [
        {"employee_id": "EMP-0001", "full_name": "Admin User"}
    ]

    with patch("app.api.v1.endpoints.satellites.get_admin_client", return_value=mock_admin):
        response = client.get("/api/v1/satellites?scope=all")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["ownerName"] == "Admin User"
        assert data[0]["ownerEmployeeId"] == "EMP-0001"

