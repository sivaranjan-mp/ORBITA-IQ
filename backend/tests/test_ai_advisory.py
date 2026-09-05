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


@pytest.mark.asyncio
async def test_call_claude_api_missing_key():
    class DummyDB:
        pass

    service = AIAdvisoryService(DummyDB())
    service.settings.anthropic_api_key = None
    
    # Ensure env var is unset for this test
    import os
    orig = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        res = await service._call_claude_api({"test": "data"})
        assert res is None
    finally:
        if orig:
            os.environ["ANTHROPIC_API_KEY"] = orig


@pytest.mark.asyncio
async def test_call_claude_api_success_mock(monkeypatch):
    class DummyDB:
        pass

    service = AIAdvisoryService(DummyDB())
    service.settings.anthropic_api_key = "test-anthropic-key"
    service.settings.claude_advisory_model = "claude-sonnet-5"

    fake_claude_json = {
        "qualitative_risk_summary": "High risk co-planar conjunction between STARLETTE and COSMOS 1408 DEB.",
        "maneuver_strategy": "In-Track Phasing (Prograde Semi-Major Axis Boost)",
        "burn_direction_rationale": "Raises semi-major axis to accumulate secular along-track timing separation.",
        "optimal_timing_window": "12 to 18 hours prior to TCA (~8 to 12 orbits before encounter)",
        "operational_tradeoffs": [
            "Requires post-burn ephemeris screening.",
            "Minimal propellant consumption compared to out-of-plane burn."
        ],
        "verification_checklist": [
            "Verify latest TLE age < 24h.",
            "Confirm FDS simulation output."
        ],
        "confidence_assessment": "High qualitative confidence based on orbital mechanics.",
        "disclaimer": DEFAULT_DISCLAIMER,
    }

    class FakeUsage:
        input_tokens = 450
        output_tokens = 280

    class FakeTextBlock:
        text = f"```json\n{json.dumps(fake_claude_json)}\n```"

    class FakeMessage:
        content = [FakeTextBlock()]
        usage = FakeUsage()

    class FakeMessagesClient:
        async def create(self, **kwargs):
            assert kwargs["model"] == "claude-sonnet-5"
            assert kwargs["temperature"] == 0.2
            assert "STARLETTE" in kwargs["messages"][0]["content"]
            return FakeMessage()

    class FakeAsyncAnthropic:
        def __init__(self, **kwargs):
            self.messages = FakeMessagesClient()

    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeAsyncAnthropic)

    context = {
        "conjunction": {"miss_distance_km": 0.42, "relative_velocity_km_s": 12.1},
        "primary_satellite": {"name": "STARLETTE", "norad_id": 7646},
        "secondary_object": {"name": "COSMOS 1408 DEB", "norad_id": 49863},
    }

    result = await service._call_claude_api(context)
    assert result is not None
    assert result["maneuver_strategy"] == "In-Track Phasing (Prograde Semi-Major Axis Boost)"
    assert result["_model_used"] == "claude-sonnet-5"
    assert result["_usage"]["prompt_tokens"] == 450
    assert result["_usage"]["completion_tokens"] == 280
    assert len(result["operational_tradeoffs"]) == 2


@pytest.mark.asyncio
async def test_call_claude_api_error_fallbacks(monkeypatch):
    class DummyDB:
        pass

    service = AIAdvisoryService(DummyDB())
    service.settings.anthropic_api_key = "test-anthropic-key"

    import anthropic

    # Test 1: Authentication Error
    class AuthErrorMessagesClient:
        async def create(self, **kwargs):
            raise anthropic.AuthenticationError(
                message="Invalid API Key",
                response=None,
                body=None,
            )

    class AuthErrorAnthropic:
        def __init__(self, **kwargs):
            self.messages = AuthErrorMessagesClient()

    monkeypatch.setattr(anthropic, "AsyncAnthropic", AuthErrorAnthropic)
    res = await service._call_claude_api({"test": "data"})
    assert res is None

    # Test 2: Rate Limit Error
    class RateLimitMessagesClient:
        async def create(self, **kwargs):
            raise anthropic.RateLimitError(
                message="Rate limit exceeded",
                response=None,
                body=None,
            )

    class RateLimitAnthropic:
        def __init__(self, **kwargs):
            self.messages = RateLimitMessagesClient()

    monkeypatch.setattr(anthropic, "AsyncAnthropic", RateLimitAnthropic)
    res = await service._call_claude_api({"test": "data"})
    assert res is None

    # Test 3: Timeout Error
    class TimeoutMessagesClient:
        async def create(self, **kwargs):
            raise anthropic.APITimeoutError(request=None)

    class TimeoutAnthropic:
        def __init__(self, **kwargs):
            self.messages = TimeoutMessagesClient()

    monkeypatch.setattr(anthropic, "AsyncAnthropic", TimeoutAnthropic)
    res = await service._call_claude_api({"test": "data"})
    assert res is None


@pytest.mark.asyncio
async def test_claude_model_env_override(monkeypatch):
    class DummyDB:
        pass

    service = AIAdvisoryService(DummyDB())
    service.settings.anthropic_api_key = "test-key"
    monkeypatch.setenv("CLAUDE_ADVISORY_MODEL", "claude-3-7-sonnet-20250219")

    captured_model = None

    class CaptureMessagesClient:
        async def create(self, **kwargs):
            nonlocal captured_model
            captured_model = kwargs["model"]
            class FakeTextBlock:
                text = json.dumps({"maneuver_strategy": "Test", "disclaimer": DEFAULT_DISCLAIMER})
            class FakeMsg:
                content = [FakeTextBlock()]
                usage = None
            return FakeMsg()

    class CaptureAnthropic:
        def __init__(self, **kwargs):
            self.messages = CaptureMessagesClient()

    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", CaptureAnthropic)

    res = await service._call_claude_api({"test": "data"})
    assert captured_model == "claude-3-7-sonnet-20250219"
    assert res["_model_used"] == "claude-3-7-sonnet-20250219"
