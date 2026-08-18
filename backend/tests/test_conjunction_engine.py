import pytest
from datetime import datetime, timedelta, timezone
from app.services.conjunction_engine import ConjunctionEngine

def test_classify_risk_critical():
    # High probability, high risk
    assert ConjunctionEngine.classify_risk(1e-4, 1000) == "critical"
    # Edge case: High prob but very close distance gets upgraded to critical
    assert ConjunctionEngine.classify_risk(5e-5, 300) == "critical"

def test_classify_risk_high():
    assert ConjunctionEngine.classify_risk(1e-5, 800) == "high"
    # Medium prob but close distance gets upgraded to high
    assert ConjunctionEngine.classify_risk(5e-6, 900) == "high"

def test_classify_risk_medium_low():
    assert ConjunctionEngine.classify_risk(2e-6, 5000) == "medium"
    assert ConjunctionEngine.classify_risk(1e-7, 10000) == "low"

def test_deduplicate_alerts():
    now = datetime.now(timezone.utc)
    existing = [
        type('obj', (object,), {
            "primary_norad_id": 25544,
            "secondary_norad_id": 33591,
            "tca": now
        })()
    ]
    
    new_alerts = [
        {
            "primary_norad_id": 25544,
            "secondary_norad_id": 33591,
            "tca": now + timedelta(minutes=30)
        },
        {
            "primary_norad_id": 48274,
            "secondary_norad_id": 29657,
            "tca": now
        }
    ]
    
    unique = ConjunctionEngine.deduplicate_alerts(new_alerts, existing)
    
    assert len(unique) == 1
    assert unique[0]["primary_norad_id"] == 48274
