import pytest
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import ENUM
from app.models.enums import AlertState, RiskLevel, SatelliteStatus, ObjectType, ConjunctionStatus
from app.models.alerts import Alert, AlertHistory
from app.models.satellites import Satellite
from app.models.conjunctions import ConjunctionEvent

def test_enum_declarations_and_comparisons():
    # Test that queries can be constructed with string literals and Enum members
    q1 = select(func.count(Alert.id)).where(Alert.status == 'active')
    q2 = select(func.count(Alert.id)).where(Alert.status == AlertState.ACTIVE)
    q3 = select(func.count(Alert.id)).where(Alert.risk_level.in_(['high', 'critical']))
    q4 = select(func.count(Alert.id)).where(Alert.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]))
    
    q5 = select(Satellite).where(Satellite.status == 'active')
    q6 = select(Satellite).where(Satellite.object_type == 'payload')
    
    q7 = select(ConjunctionEvent).where(ConjunctionEvent.status == 'open')
    q8 = select(ConjunctionEvent).where(ConjunctionEvent.risk_level == 'low')
    
    assert str(q1) is not None
    assert str(q2) is not None
    assert str(q3) is not None
    assert str(q4) is not None
    assert str(q5) is not None
    assert str(q6) is not None
    assert str(q7) is not None
    assert str(q8) is not None


@pytest.mark.asyncio
async def test_schema_check_non_postgres():
    from unittest.mock import AsyncMock, MagicMock
    from app.db.schema_check import verify_schema

    mock_engine = MagicMock()
    mock_engine.dialect.name = "sqlite"

    result = await verify_schema(mock_engine)
    assert result["valid"] is True
    assert len(result["mismatches"]) == 0


@pytest.mark.asyncio
async def test_schema_check_postgres_readonly_verification():
    from unittest.mock import AsyncMock, MagicMock
    from app.db.schema_check import verify_schema

    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"

    mock_conn = AsyncMock()
    mock_conn.commit = AsyncMock()
    
    # Return matched enum types
    mock_res = MagicMock()
    mock_res.fetchall.return_value = [
        ("satellites", "status", "USER-DEFINED", "satellite_status"),
        ("satellites", "object_type", "USER-DEFINED", "object_type"),
        ("conjunction_events", "risk_level", "USER-DEFINED", "risk_level"),
        ("conjunction_events", "status", "USER-DEFINED", "alert_status"),
    ]
    mock_conn.execute.return_value = mock_res
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn

    result = await verify_schema(mock_engine)
    assert result["valid"] is True
    assert len(result["mismatches"]) == 0
    assert len(result["columns_checked"]) == 4
    # Ensure NO commits or DDL executions occurred
    assert not mock_conn.commit.called


@pytest.mark.asyncio
async def test_schema_check_postgres_detects_mismatch_without_ddl():
    from unittest.mock import AsyncMock, MagicMock
    from app.db.schema_check import verify_schema

    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"

    mock_conn = AsyncMock()
    mock_conn.commit = AsyncMock()
    
    # Return mismatch: satellites.status is text instead of satellite_status
    mock_res = MagicMock()
    mock_res.fetchall.return_value = [
        ("satellites", "status", "text", "text"),
        ("satellites", "object_type", "USER-DEFINED", "object_type"),
        ("conjunction_events", "risk_level", "USER-DEFINED", "risk_level"),
        ("conjunction_events", "status", "USER-DEFINED", "alert_status"),
    ]
    mock_conn.execute.return_value = mock_res
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn

    result = await verify_schema(mock_engine)
    assert result["valid"] is False
    assert len(result["mismatches"]) == 1
    assert result["mismatches"][0]["column"] == "status"
    assert result["mismatches"][0]["expected_udt"] == "satellite_status"
    assert result["mismatches"][0]["actual_udt"] == "text"
    
    # Ensure NO DDL and NO commit were executed — strictly read-only
    assert not mock_conn.commit.called
    assert mock_conn.execute.call_count == 1  # Only the single read SELECT was run


