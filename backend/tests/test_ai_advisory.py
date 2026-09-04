import json
import pytest
from app.schemas.ai_advisory import (
    DEFAULT_DISCLAIMER,
    AdvisoryRecommendationContent,
    AdvisoryRecommendationRequest,
    AIManeuverAdvisoryResponse,
)
from app.services.ai_advisory_service import AIAdvisoryService, GEMINI_RESPONSE_SCHEMA, SYSTEM_PROMPT


def test_ai_advisory_schemas():
    content = AdvisoryRecommendationContent(
        qualitative_risk_summary="High-speed encounter in LEO.",
        maneuver_strategy="In-Track Phasing (Prograde Boost)",
        burn_direction_rationale="Extends semi-major axis to accumulate along-track separation.",
        optimal_timing_window="18 to 24 hours prior to TCA",
        operational_tradeoffs=["Secondary screening required."],
        verification_checklist=["Verify latest TLE."],
        disclaimer=DEFAULT_DISCLAIMER,
    )
    assert content.maneuver_strategy == "In-Track Phasing (Prograde Boost)"
    assert "OPERATOR ADVISORY NOTICE" in content.disclaimer
    assert "certified" in content.disclaimer.lower()


def test_gemini_response_schema_definition():
    assert GEMINI_RESPONSE_SCHEMA["type"] == "OBJECT"
    props = GEMINI_RESPONSE_SCHEMA["properties"]
    assert "qualitative_risk_summary" in props
    assert "maneuver_strategy" in props
    assert "burn_direction_rationale" in props
    assert "optimal_timing_window" in props
    assert "operational_tradeoffs" in props
    assert "verification_checklist" in props
    assert "disclaimer" in props

    required = GEMINI_RESPONSE_SCHEMA["required"]
    assert "qualitative_risk_summary" in required
    assert "maneuver_strategy" in required
    assert "burn_direction_rationale" in required


def test_negative_constraints_in_system_prompt():
    assert "NO FALSE-PRECISION MATH" in SYSTEM_PROMPT
    assert "NEVER calculate or output exact delta-v" in SYSTEM_PROMPT
    assert "REASON QUALITATIVELY" in SYSTEM_PROMPT
    assert "STRICTLY ADVISORY" in SYSTEM_PROMPT


def test_deterministic_advisory_heuristic():
    class DummyDB:
        pass

    service = AIAdvisoryService(DummyDB())
    context = {
        "conjunction": {
            "alert_id": "test-alert-id",
            "screening_scope": "fleet_vs_catalog",
            "tca_iso": "2026-09-12T14:32:00Z",
            "hours_until_tca": 182.4,
            "days_until_tca": 7.6,
            "miss_distance_km": 8.45,
            "miss_distance_m": 8450.0,
            "relative_velocity_km_s": 13.8,
            "collision_probability": 3.4e-5,
            "risk_level": "medium",
        },
        "primary_satellite": {
            "name": "STARLETTE",
            "norad_id": 7646,
            "period_minutes": 100.9,
            "orbit_regime": "LEO",
        },
        "secondary_object": {
            "name": "COSMOS 1408 DEB",
            "norad_id": 49863,
            "object_type": "debris",
        },
    }

    result = service._generate_deterministic_advisory(context)
    assert "maneuver_strategy" in result
    assert "In-Track Phasing" in result["maneuver_strategy"]
    assert "STARLETTE" in result["qualitative_risk_summary"]
    assert "COSMOS 1408 DEB" in result["qualitative_risk_summary"]
    assert len(result["operational_tradeoffs"]) > 0
    assert len(result["verification_checklist"]) > 0
    assert "OPERATOR ADVISORY NOTICE" in result["disclaimer"]
    # Ensure no exact numerical delta-v values like " m/s" or " thruster seconds" are prescribed
    assert "m/s" not in result["maneuver_strategy"]
