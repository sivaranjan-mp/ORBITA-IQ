import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.models.satellites import Satellite
from app.models.ai_advisory import AIManeuverAdvisory
from app.models.alerts import AlertStatusHistory, ConjunctionAlert
from app.schemas.alerts import AlertStatusHistoryResponse, AlertStatusHistoryListResponse
from app.schemas.auth import UserProfile
from app.services.alert_service import AlertService


def test_alert_status_history_schema():
    now = datetime.now(timezone.utc)
    item = AlertStatusHistoryResponse(
        id=str(uuid.uuid4()),
        alertId=str(uuid.uuid4()),
        primarySatellite="STARLINK-1007",
        primaryNoradId=44713,
        secondaryObject="COSMOS 2251 DEB",
        secondaryNoradId=33591,
        riskLevel="critical",
        previousStatus="open",
        newStatus="monitoring",
        actionTaken="Monitoring",
        changedBy="00000000-0000-0000-0000-000000000001",
        operatorName="Flight Commander Jane",
        changedAt=now,
        notes="Monitoring closely due to low miss distance",
    )
    assert item.primarySatellite == "STARLINK-1007"
    assert item.actionTaken == "Monitoring"
    assert item.operatorName == "Flight Commander Jane"

    resp = AlertStatusHistoryListResponse(
        items=[item],
        total=1,
        page=1,
        limit=20,
        totalPages=1,
    )
    assert len(resp.items) == 1
    assert resp.total == 1


@pytest.mark.asyncio
async def test_update_alert_status_creates_history():
    alert_id = uuid.uuid4()
    operator_id = str(uuid.uuid4())
    alert = ConjunctionAlert(
        id=alert_id,
        satellite_a_norad_id=25544,
        satellite_a_name="ISS (ZARYA)",
        satellite_b_norad_id=33591,
        satellite_b_name="COSMOS 2251 DEB",
        screening_scope="fleet_vs_catalog",
        tca=datetime.now(timezone.utc),
        miss_distance_km=0.34,
        miss_distance_m=340.0,
        relative_velocity_km_s=14.2,
        probability=0.00042,
        risk_level="critical",
        status="open",
        detected_by="satguard",
    )

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()

    service = AlertService(mock_session)
    service.get_alert = AsyncMock(return_value=alert)

    updated = await service.update_alert_status(
        alert_id=str(alert_id),
        new_status="monitoring",
        changed_by=operator_id,
        notes="Tracking for potential maneuver",
    )

    assert updated is not None
    assert updated.status == "monitoring"
    assert mock_session.add.call_count >= 2

    # Verify history entry was added
    history_calls = [
        call.args[0] for call in mock_session.add.call_args_list
        if isinstance(call.args[0], AlertStatusHistory)
    ]
    assert len(history_calls) == 1
    hist = history_calls[0]
    assert hist.alert_id == alert_id
    assert hist.previous_status == "open"
    assert hist.new_status == "monitoring"
    assert str(hist.changed_by) == operator_id
    assert hist.notes == "Tracking for potential maneuver"


@pytest.mark.asyncio
async def test_get_alert_history_service():
    mock_session = AsyncMock()
    service = AlertService(mock_session)

    mock_history_item = AlertStatusHistory(
        id=uuid.uuid4(),
        alert_id=uuid.uuid4(),
        previous_status="open",
        new_status="resolved",
        changed_by=uuid.uuid4(),
        changed_at=datetime.now(timezone.utc),
        notes="Resolved after screening update",
    )
    service.repository.get_alert_status_history = AsyncMock(return_value=([mock_history_item], 1))

    items, total = await service.get_alert_history(page=1, limit=10)
    assert total == 1
    assert len(items) == 1
    assert items[0].new_status == "resolved"


def test_alerts_history_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import get_current_user
    from app.db.session import get_db

    mock_user = UserProfile(
        id=str(uuid.uuid4()),
        employee_id="EMP-0001",
        full_name="Chief Orbital Officer",
        role="operator",
        is_active=True,
    )

    mock_db = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("app.api.v1.endpoints.alerts.AlertService") as MockService:
            service_instance = MockService.return_value
            mock_hist = AlertStatusHistory(
                id=uuid.uuid4(),
                alert_id=uuid.uuid4(),
                previous_status="open",
                new_status="monitoring",
                changed_by=uuid.UUID(mock_user.id),
                changed_at=datetime.now(timezone.utc),
                notes="Under active observation",
            )
            mock_alert = ConjunctionAlert(
                id=mock_hist.alert_id,
                satellite_a_norad_id=25544,
                satellite_a_name="ISS (ZARYA)",
                satellite_b_norad_id=33591,
                satellite_b_name="COSMOS 2251 DEB",
                risk_level="critical",
                status="monitoring",
                miss_distance_km=0.5,
                miss_distance_m=500.0,
                tca=datetime.now(timezone.utc),
            )
            mock_hist.alert = mock_alert

            service_instance.get_alert_history = AsyncMock(return_value=([mock_hist], 1))

            client = TestClient(app)
            response = client.get("/api/v1/alerts/history?page=1&limit=20")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["primarySatellite"] == "ISS (ZARYA)"
            assert data["items"][0]["actionTaken"] == "Monitoring"
            assert data["items"][0]["notes"] == "Under active observation"
    finally:
        app.dependency_overrides.clear()

