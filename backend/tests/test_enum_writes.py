import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import insert, update
from sqlalchemy.dialects import postgresql

from app.models.enums import (
    AlertState,
    RiskLevel,
    SatelliteStatus,
    ObjectType,
    ConjunctionStatus,
)
from app.models.alerts import Alert, AlertHistory
from app.models.satellites import Satellite, OrbitState, TLERecord
from app.models.conjunctions import ConjunctionEvent
from app.services.satellite_service import SatelliteService
from app.services.alert_service import AlertService
from app.services.conjunction_service import ConjunctionService
from app.schemas.satellites import SatelliteUpdateRequest


def test_postgres_enum_sql_compilation_for_inserts_and_updates():
    """Verify that SQLAlchemy PostgreSQL dialect compiles INSERT and UPDATE statements with proper ENUM types."""
    pg_dialect = postgresql.dialect()
    
    # 1. Satellite insert & update
    sat_insert = insert(Satellite).values(
        norad_id=99999,
        name="TEST-SAT",
        object_type=ObjectType.PAYLOAD,
        status=SatelliteStatus.ACTIVE
    )
    compiled_sat = str(sat_insert.compile(dialect=pg_dialect))
    assert "INSERT INTO satellites" in compiled_sat
    assert "object_type" in compiled_sat
    assert "status" in compiled_sat
    
    sat_update = update(Satellite).where(Satellite.norad_id == 99999).values(
        status=SatelliteStatus.DEGRADED
    )
    compiled_sat_up = str(sat_update.compile(dialect=pg_dialect))
    assert "UPDATE satellites" in compiled_sat_up

    # 2. Alert insert & update
    alert_insert = insert(Alert).values(
        conjunction_event_id=uuid.uuid4(),
        satellite_a_id=uuid.uuid4(),
        miss_distance=500.0,
        time_of_closest_approach=datetime.now(timezone.utc),
        risk_level=RiskLevel.HIGH,
        status=AlertState.ACTIVE
    )
    compiled_alert = str(alert_insert.compile(dialect=pg_dialect))
    assert "INSERT INTO alerts" in compiled_alert

    alert_update = update(Alert).where(Alert.id == uuid.uuid4()).values(
        status=AlertState.ACKNOWLEDGED
    )
    compiled_alert_up = str(alert_update.compile(dialect=pg_dialect))
    assert "UPDATE alerts" in compiled_alert_up

    # 3. ConjunctionEvent insert & update
    conj_insert = insert(ConjunctionEvent).values(
        primary_satellite="SAT-A",
        primary_norad_id=10001,
        secondary_object="DEB-B",
        secondary_norad_id=10002,
        tca=datetime.now(timezone.utc),
        miss_distance_m=250.0,
        probability=0.001,
        risk_level=RiskLevel.CRITICAL,
        status=ConjunctionStatus.OPEN,
        detected_by="satguard"
    )
    compiled_conj = str(conj_insert.compile(dialect=pg_dialect))
    assert "INSERT INTO conjunction_events" in compiled_conj

    conj_update = update(ConjunctionEvent).where(ConjunctionEvent.id == uuid.uuid4()).values(
        status=ConjunctionStatus.RESOLVED
    )
    compiled_conj_up = str(conj_update.compile(dialect=pg_dialect))
    assert "UPDATE conjunction_events" in compiled_conj_up


@pytest.mark.asyncio
async def test_satellite_service_create_and_update():
    """Test creating and updating a satellite through SatelliteService."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    
    # Mock get_satellite_by_norad returning None then Satellite
    sat_id = uuid.uuid4()
    mock_sat = Satellite(
        id=sat_id,
        norad_id=25544,
        name="ISS (ZARYA)",
        object_type=ObjectType.PAYLOAD,
        status=SatelliteStatus.ACTIVE,
        owner_org="NASA"
    )
    
    mock_res_none = MagicMock()
    mock_res_none.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res_none
    
    service = SatelliteService(mock_session)
    
    sample_tle = "ISS (ZARYA)\n1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993\n2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"
    with patch("app.services.celestrak_service.fetch_tle_by_norad_id", return_value=sample_tle):
        created = await service.add_satellite_by_norad(25544, owner_org="EMP-0001")
        assert created.norad_id == 25544
        assert created.status == "active"
        assert created.object_type == "payload"
        assert mock_session.add.called
        assert mock_session.commit.called

    # Test update
    mock_res_sat = MagicMock()
    mock_res_sat.scalar_one_or_none.return_value = mock_sat
    mock_session.execute.return_value = mock_res_sat
    
    updated = await service.update_satellite(str(sat_id), SatelliteUpdateRequest(status="degraded"))
    assert updated.status == "degraded"
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_alert_service_create_and_update():
    """Test creating and updating an alert through AlertService."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    
    # Mock no existing alert
    mock_res_existing = MagicMock()
    mock_res_existing.scalars().first.return_value = None
    
    # Mock finding sat_a and sat_b
    sat_a = Satellite(id=uuid.uuid4(), norad_id=25544, name="ISS")
    sat_b = Satellite(id=uuid.uuid4(), norad_id=33591, name="DEB")
    
    mock_res_sat_a = MagicMock()
    mock_res_sat_a.scalars().first.return_value = sat_a
    mock_res_sat_b = MagicMock()
    mock_res_sat_b.scalars().first.return_value = sat_b
    
    mock_session.execute.side_effect = [mock_res_existing, mock_res_sat_a, mock_res_sat_b]
    
    service = AlertService(mock_session)
    
    event = ConjunctionEvent(
        id=uuid.uuid4(),
        primary_satellite="ISS",
        primary_norad_id=25544,
        secondary_object="DEB",
        secondary_norad_id=33591,
        tca=datetime.now(timezone.utc),
        miss_distance_m=120.0,
        relative_velocity_km_s=14.5,
        probability=0.005,
        risk_level=RiskLevel.CRITICAL,
        status=ConjunctionStatus.OPEN,
        detected_by="satguard"
    )
    
    created_alert = await service.create_alert_from_conjunction(event)
    assert created_alert.risk_level == RiskLevel.CRITICAL
    assert created_alert.status == AlertState.ACTIVE
    assert mock_session.add.called
    assert mock_session.commit.called

    # Test update status
    alert_obj = Alert(
        id=uuid.uuid4(),
        conjunction_event_id=event.id,
        satellite_a_id=sat_a.id,
        miss_distance=120.0,
        time_of_closest_approach=datetime.now(timezone.utc),
        risk_level=RiskLevel.CRITICAL,
        status=AlertState.ACTIVE
    )
    
    with patch.object(service.repository, "get_alert_by_id", return_value=alert_obj):
        updated_alert = await service.update_alert_status(str(alert_obj.id), "acknowledged")
        assert updated_alert.status == "acknowledged"
        assert mock_session.commit.called


@pytest.mark.asyncio
async def test_conjunction_service_seed_and_update():
    """Test creating and updating conjunction events through ConjunctionService."""
    mock_session = AsyncMock()
    mock_session.add_all = MagicMock()
    
    service = ConjunctionService(mock_session)
    
    mock_events = [
        {
            "primary_satellite": "ISS",
            "primary_norad_id": 25544,
            "secondary_object": "DEB",
            "secondary_norad_id": 33591,
            "tca": datetime.now(timezone.utc),
            "miss_distance_m": 340.0,
            "probability": 0.00042,
            "risk_level": "critical",
            "status": "open",
            "detected_by": "satguard"
        }
    ]
    
    # Mock returning inserted
    created_event = ConjunctionEvent(
        id=uuid.uuid4(),
        primary_satellite="ISS",
        primary_norad_id=25544,
        secondary_object="DEB",
        secondary_norad_id=33591,
        tca=datetime.now(timezone.utc),
        miss_distance_m=340.0,
        probability=0.00042,
        risk_level=RiskLevel.CRITICAL,
        status=ConjunctionStatus.OPEN,
        detected_by="satguard"
    )
    mock_res = MagicMock()
    mock_res.scalars().all.return_value = [created_event]
    mock_res.scalars().first.return_value = created_event
    mock_session.execute.return_value = mock_res
    
    seeded = await service.seed_mock_alerts(mock_events)
    assert len(seeded) == 1
    assert seeded[0].risk_level == "critical"
    assert seeded[0].status == "open"
    assert mock_session.add_all.called
    assert mock_session.commit.called

    updated = await service.update_alert_status(str(created_event.id), "resolved")
    assert updated is not None
    assert mock_session.commit.called
