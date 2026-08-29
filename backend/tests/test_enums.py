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
