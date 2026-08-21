from app.services.risk_explanation_engine import RiskExplanationEngine


def test_risk_explanation_generation():
    text = RiskExplanationEngine.generate_explanation(
        primary_name="ISS",
        secondary_name="DEBRIS X",
        risk_level="high",
        miss_distance_km=0.85,
        relative_velocity_kms=12.4,
        probability=0.00005,
        trend="increasing"
    )

    expected = "[HIGH RISK] ISS is projected to have an extremely close approach with DEBRIS X at a miss distance of 0.85 km. The encounter will occur at a very high relative velocity of 12.40 km/s. The estimated collision probability is 5.00e-05 (1 in 20,000). The risk trend is currently increasing."

    assert text == expected


def test_risk_explanation_negligible():
    text = RiskExplanationEngine.generate_explanation(
        primary_name="SAT A",
        secondary_name="SAT B",
        risk_level="low",
        miss_distance_km=15.0,
        relative_velocity_kms=4.5,
        probability=0.0,
        trend="stable"
    )

    expected = "[LOW RISK] SAT A is projected to have a moderate approach with SAT B at a miss distance of 15.00 km. The encounter will occur at a moderate relative velocity of 4.50 km/s. The estimated collision probability is 0.0 (negligible). The risk trend is currently stable."

    assert text == expected
