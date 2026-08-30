import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.auth import UserProfile
from app.models.satellites import Satellite, OrbitState, TLERecord
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
    mock_db.execute.return_value = mock_res
    app.dependency_overrides[get_db] = lambda: mock_db

    sample_tle = "ISS (ZARYA)\n1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"

    response = client.post("/api/v1/satellites/manual", json={"raw_tle": sample_tle})
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
    assert response.status_code == 400


def test_add_satellite_manual_unauthenticated():
    sample_tle = "ISS (ZARYA)\n1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"
    response = client.post("/api/v1/satellites/manual", json={"raw_tle": sample_tle})
    assert response.status_code in (401, 403)
