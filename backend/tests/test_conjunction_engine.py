from datetime import datetime, timedelta, timezone
from app.services.conjunction_engine import ConjunctionEngine


def test_stage1_coarse_filter():
    # Overlapping orbits (LEO vs LEO)
    assert ConjunctionEngine.passes_stage1_coarse_filter(
        perigee_a=400.0, apogee_a=420.0, perigee_b=410.0, apogee_b=430.0, margin_km=50.0
    ) is True

    # Non-overlapping orbits beyond 50km margin (LEO 400km vs GEO 35,786km)
    assert ConjunctionEngine.passes_stage1_coarse_filter(
        perigee_a=400.0, apogee_a=420.0, perigee_b=35780.0, apogee_b=35800.0, margin_km=50.0
    ) is False

    # Near boundary overlap within 50km margin
    assert ConjunctionEngine.passes_stage1_coarse_filter(
        perigee_a=400.0, apogee_a=500.0, perigee_b=530.0, apogee_b=600.0, margin_km=50.0
    ) is True


def test_classify_risk_by_miss_distance():
    # < 1 km -> Critical
    assert ConjunctionEngine.classify_risk_by_miss_distance(0.4) == "critical"
    assert ConjunctionEngine.classify_risk_by_miss_distance(0.99) == "critical"

    # 1 - 5 km -> High
    assert ConjunctionEngine.classify_risk_by_miss_distance(1.0) == "high"
    assert ConjunctionEngine.classify_risk_by_miss_distance(3.5) == "high"
    assert ConjunctionEngine.classify_risk_by_miss_distance(5.0) == "high"

    # 5 - 25 km -> Medium
    assert ConjunctionEngine.classify_risk_by_miss_distance(5.1) == "medium"
    assert ConjunctionEngine.classify_risk_by_miss_distance(15.0) == "medium"
    assert ConjunctionEngine.classify_risk_by_miss_distance(25.0) == "medium"

    # 25 - 50 km -> Low
    assert ConjunctionEngine.classify_risk_by_miss_distance(25.1) == "low"
    assert ConjunctionEngine.classify_risk_by_miss_distance(49.9) == "low"
    assert ConjunctionEngine.classify_risk_by_miss_distance(50.0) == "low"

    # > 50 km -> Discarded (None)
    assert ConjunctionEngine.classify_risk_by_miss_distance(50.1) is None
    assert ConjunctionEngine.classify_risk_by_miss_distance(120.0) is None


def test_classify_risk_combined():
    assert ConjunctionEngine.classify_risk(probability=1e-4, miss_distance_m=800) == "critical"
    assert ConjunctionEngine.classify_risk(probability=1e-5, miss_distance_m=3000) == "high"
    assert ConjunctionEngine.classify_risk(probability=1e-6, miss_distance_m=12000) == "medium"
    assert ConjunctionEngine.classify_risk(probability=1e-8, miss_distance_m=35000) == "low"


def test_deduplicate_alerts():
    now = datetime.now(timezone.utc)
    existing = [
        {
            "primary_norad_id": 25544,
            "secondary_norad_id": 33591,
            "tca": now
        }
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
