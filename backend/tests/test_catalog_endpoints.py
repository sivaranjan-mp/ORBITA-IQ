import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.auth import UserProfile
from app.models.catalog import CatalogSatellite
from app.models.satellites import Satellite
from app.services.catalog_service import sync_tracker

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


def test_list_catalog_success():
    operator_user = UserProfile(
        id="user-123",
        employee_id="EMP-0042",
        email="operator@example.com",
        full_name="Orbit Operator",
        role="operator",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: operator_user

    mock_db = AsyncMock()

    # Catalog mock items
    cat1 = CatalogSatellite(
        norad_id=25544,
        name="ISS (ZARYA)",
        international_designator="1998-067A",
        object_type="payload",
        orbit_regime="LEO",
        apogee_km=420.0,
        perigee_km=415.0,
        inclination_deg=51.64,
        period_minutes=92.5,
        eccentricity=0.0005,
        line1="1 25544...",
        line2="2 25544...",
        epoch=datetime.now(timezone.utc),
    )

    # Mock count query
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 1

    # Mock items query
    mock_items_res = MagicMock()
    mock_items_res.scalars().all.return_value = [cat1]

    # Mock user tracked sats query
    mock_tracked_sat = Satellite(
        id=uuid.uuid4(),
        norad_id=25544,
        name="ISS (ZARYA)",
        owner_org="EMP-0042",
    )
    mock_user_sats_res = MagicMock()
    mock_user_sats_res.scalars().all.return_value = [mock_tracked_sat]

    mock_db.execute.side_effect = [
        mock_count_res,  # check if empty
        mock_count_res,  # count query
        mock_items_res,  # items query
        mock_user_sats_res,  # user tracked check
    ]
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/v1/catalog?page=1&limit=25")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["noradId"] == 25544
    assert data["items"][0]["name"] == "ISS (ZARYA)"
    assert data["items"][0]["isTracked"] is True


def test_track_catalog_satellite():
    operator_user = UserProfile(
        id="user-123",
        employee_id="EMP-0042",
        email="operator@example.com",
        full_name="Orbit Operator",
        role="operator",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: operator_user

    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    sat = Satellite(
        id=uuid.uuid4(),
        norad_id=25544,
        name="ISS (ZARYA)",
        owner_org="EMP-0042",
        object_type="payload",
        status="active",
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = sat
    mock_db.execute.return_value = mock_res
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post("/api/v1/catalog/track/25544")
    assert response.status_code == 200
    data = response.json()
    assert data["noradId"] == 25544
    assert data["name"] == "ISS (ZARYA)"


def test_sync_catalog_status_and_trigger():
    operator_user = UserProfile(
        id="user-123",
        employee_id="EMP-0042",
        email="operator@example.com",
        full_name="Orbit Operator",
        role="operator",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: operator_user

    # Reset tracker
    sync_tracker.status = "idle"
    sync_tracker.last_sync_completed_at = None

    # Get status
    res = client.get("/api/v1/catalog/sync/status")
    assert res.status_code == 200
    status_data = res.json()
    assert status_data["status"] == "idle"

    # Trigger sync with force=True
    with patch("app.services.catalog_service.CatalogService.run_sync_background_job", new_callable=AsyncMock):
        post_res = client.post("/api/v1/catalog/sync?force=true")
        assert post_res.status_code == 200
        data = post_res.json()
        assert data["status"] == "running"


def test_sync_catalog_forbidden_for_unauthorized():
    response = client.post("/api/v1/catalog/sync")
    assert response.status_code in (401, 403)
