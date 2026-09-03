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
    from app.db.schema_check import verify_and_heal_schema

    mock_engine = MagicMock()
    mock_engine.dialect.name = "sqlite"

    result = await verify_and_heal_schema(mock_engine)
    assert result["valid"] is True
    assert result["healed"] is False


@pytest.mark.asyncio
async def test_schema_check_postgres_simulation_healing():
    from unittest.mock import AsyncMock, MagicMock
    from app.db.schema_check import verify_and_heal_schema

    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"

    mock_conn = AsyncMock()
    mock_conn.commit = AsyncMock()
    
    # Return row with text type initially, then satellite_status after healing
    mock_res_initial = MagicMock()
    mock_res_initial.first.return_value = ("text", "text")
    
    mock_res_healed = MagicMock()
    mock_res_healed.first.return_value = ("USER-DEFINED", "satellite_status")
    
    mock_conn.execute.side_effect = [mock_res_initial, None, mock_res_healed]

    mock_engine.connect.return_value.__aenter__.return_value = mock_conn

    result = await verify_and_heal_schema(mock_engine)
    assert result["valid"] is True
    assert result["healed"] is True
    assert result["udt_name"] == "satellite_status"
    assert mock_conn.commit.called

