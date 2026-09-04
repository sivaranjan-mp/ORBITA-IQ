import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.ai_advisory import AIManeuverAdvisory
from app.models.alerts import ConjunctionAlert
from app.models.catalog import CatalogSatellite
from app.models.satellites import Satellite
from app.schemas.ai_advisory import (
    DEFAULT_DISCLAIMER,
    AdvisoryRecommendationContent,
    AIManeuverAdvisoryResponse,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are ORBITA-IQ's Senior Spacecraft Operations & Astrodynamics AI Advisor.
Your role is to analyze orbital conjunction encounters between fleet satellites and other space objects, and provide qualitative collision avoidance guidance to human satellite operators.

CRITICAL SAFETY & ADVISORY CONSTRAINTS:
1. STRICTLY ADVISORY: Your output is an advisory aid for operator situational awareness, NOT a certified Flight Dynamics System (FDS) maneuver solution.
2. NO FALSE-PRECISION MATH: NEVER calculate or output exact delta-v (ΔV) numerical values (e.g., '1.42 m/s'), exact thruster firing durations down to seconds, or exact burn start timestamps. You do not possess calibrated thruster impulse curves, mass budgets, or high-fidelity covariance matrices.
3. REASON QUALITATIVELY: Focus on the physical astrodynamics principles:
   - Encounter crossing geometry (e.g., head-on, co-planar overtake, polar cross-track, ascending/descending node crossing).
   - Relative velocity vectors and orbital regime implications (LEO drag, debris environment).
   - Maneuver strategy selection (e.g., In-Track Phasing via Prograde/Retrograde boost to accumulate secular drift, Out-of-Plane cross-track separation for nodal divergence, or Radial boost).
   - Optimal execution timing in terms of lead time and orbital periods (e.g., 12 to 24 hours prior to TCA, allowing 8-15 orbits for secular along-track displacement with minimal propellant).
   - Operational trade-offs (re-screening against catalog post-burn, tracking pass availability, propellant consumption considerations).
   - Verification checklist for the flight operations crew before execution.

OUTPUT FORMAT:
You MUST respond with ONLY a valid JSON object adhering precisely to this structure (no markdown formatting, no code fences, no extra text):
{
  "qualitative_risk_summary": "Plain English synthesis of the encounter geometry, relative velocity, and risk drivers.",
  "maneuver_strategy": "Name of qualitative strategy (e.g. 'In-Track Phasing (Prograde Altitude Boost)' or 'Out-of-Plane Cross-Track Separation')",
  "burn_direction_rationale": "Physical explanation of why this vector effectively mitigates collision risk at the node.",
  "optimal_timing_window": "Recommended execution lead-time in orbital revolutions and hours before TCA.",
  "operational_tradeoffs": [
    "Tradeoff or operational consideration 1",
    "Tradeoff or operational consideration 2",
    "Tradeoff or operational consideration 3"
  ],
  "verification_checklist": [
    "Verification step 1 (e.g., verify latest secondary object TLE age)",
    "Verification step 2 (e.g., compute post-burn trajectory in certified FDS)",
    "Verification step 3 (e.g., execute secondary conjunction screening before thruster command upload)"
  ],
  "confidence_assessment": "High qualitative confidence based on orbital regime geometry.",
  "disclaimer": "OPERATOR ADVISORY NOTICE: AI-generated orbital risk assessment and qualitative maneuver advisory for operator review only. This is not a certified flight-dynamics maneuver solution or precision ephemeris product. All tactical maneuvers must be verified using certified Astrodynamics Flight Dynamics System (FDS) tools and official Space Command CDMs prior to execution."
}
"""

GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "qualitative_risk_summary": {
            "type": "STRING",
            "description": "Plain English synthesis of the encounter geometry, relative velocity, and risk drivers."
        },
        "maneuver_strategy": {
            "type": "STRING",
            "description": "Name of qualitative strategy (e.g. In-Track Phasing (Prograde Semi-Major Axis Boost) or Out-of-Plane Cross-Track Separation)"
        },
        "burn_direction_rationale": {
            "type": "STRING",
            "description": "Physical explanation of why this vector effectively mitigates collision risk at the node."
        },
        "optimal_timing_window": {
            "type": "STRING",
            "description": "Recommended execution lead-time in orbital revolutions and hours before TCA."
        },
        "operational_tradeoffs": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Tradeoffs or operational considerations."
        },
        "verification_checklist": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Verification steps for flight operations."
        },
        "confidence_assessment": {
            "type": "STRING",
            "description": "Qualitative confidence assessment."
        },
        "disclaimer": {
            "type": "STRING",
            "description": "Mandatory safety disclaimer."
        }
    },
    "required": [
        "qualitative_risk_summary",
        "maneuver_strategy",
        "burn_direction_rationale",
        "optimal_timing_window",
        "operational_tradeoffs",
        "verification_checklist",
        "confidence_assessment",
        "disclaimer"
    ]
}


class AIAdvisoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def get_alert_by_id(self, alert_id: str) -> Optional[ConjunctionAlert]:
        try:
            val_uuid = uuid.UUID(alert_id)
            stmt = select(ConjunctionAlert).where(ConjunctionAlert.id == val_uuid)
        except (ValueError, TypeError):
            stmt = select(ConjunctionAlert).where(ConjunctionAlert.id == alert_id)

        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_orbital_context(self, alert: ConjunctionAlert) -> Dict[str, Any]:
        """
        Assembles comprehensive telemetry for primary fleet satellite,
        secondary object, and the conjunction encounter geometry.
        """
        # 1. Primary satellite data
        primary_sat = None
        if alert.satellite_a_id:
            stmt = (
                select(Satellite)
                .where(Satellite.id == alert.satellite_a_id)
                .options(selectinload(Satellite.orbit_state), selectinload(Satellite.tle_records))
            )
            res = await self.db.execute(stmt)
            primary_sat = res.scalars().first()

        if not primary_sat:
            stmt = (
                select(Satellite)
                .where(Satellite.norad_id == alert.satellite_a_norad_id)
                .options(selectinload(Satellite.orbit_state), selectinload(Satellite.tle_records))
            )
            res = await self.db.execute(stmt)
            primary_sat = res.scalars().first()

        primary_data = {
            "name": alert.satellite_a_name,
            "norad_id": alert.satellite_a_norad_id,
            "object_type": "payload (active fleet satellite)",
            "is_maneuverable": True,
            "altitude_km": primary_sat.orbit_state.altitude_km if (primary_sat and primary_sat.orbit_state) else 550.0,
            "inclination_deg": primary_sat.orbit_state.inclination_deg if (primary_sat and primary_sat.orbit_state) else 53.0,
            "period_minutes": primary_sat.orbit_state.period_minutes if (primary_sat and primary_sat.orbit_state) else 95.5,
            "eccentricity": primary_sat.orbit_state.eccentricity if (primary_sat and primary_sat.orbit_state) else 0.001,
            "orbit_regime": "LEO",
        }

        # 2. Secondary object data
        secondary_sat = None
        cat_stmt = select(CatalogSatellite).where(CatalogSatellite.norad_id == alert.satellite_b_norad_id)
        cat_res = await self.db.execute(cat_stmt)
        secondary_cat = cat_res.scalars().first()

        secondary_type = "debris (uncontrolled)"
        secondary_regime = "LEO"
        sec_inc = 53.0
        sec_alt = primary_data["altitude_km"]

        if secondary_cat:
            secondary_type = f"{secondary_cat.object_type or 'debris'} (uncontrolled object)"
            secondary_regime = secondary_cat.orbit_regime or "LEO"
            sec_inc = secondary_cat.inclination_deg or sec_inc
            sec_alt = secondary_cat.apogee_km or sec_alt
        elif alert.screening_scope == "fleet_vs_fleet":
            secondary_type = "payload (co-fleet operational satellite)"

        secondary_data = {
            "name": alert.satellite_b_name,
            "norad_id": alert.satellite_b_norad_id,
            "object_type": secondary_type,
            "is_maneuverable": (alert.screening_scope == "fleet_vs_fleet"),
            "altitude_km": sec_alt,
            "inclination_deg": sec_inc,
            "orbit_regime": secondary_regime,
        }

        # 3. Conjunction encounter
        now = datetime.now(timezone.utc)
        tca = alert.tca if alert.tca.tzinfo else alert.tca.replace(tzinfo=timezone.utc)
        hours_to_tca = max(0.1, (tca - now).total_seconds() / 3600.0)

        conjunction_data = {
            "alert_id": str(alert.id),
            "screening_scope": alert.screening_scope,
            "tca_iso": tca.isoformat(),
            "hours_until_tca": round(hours_to_tca, 2),
            "days_until_tca": round(hours_to_tca / 24.0, 2),
            "miss_distance_km": round(alert.miss_distance_km, 3),
            "miss_distance_m": round(alert.miss_distance_m, 1),
            "relative_velocity_km_s": round(alert.relative_velocity_km_s or 10.5, 2),
            "collision_probability": alert.probability,
            "risk_level": alert.risk_level,
        }

        return {
            "conjunction": conjunction_data,
            "primary_satellite": primary_data,
            "secondary_object": secondary_data,
        }

    async def get_cached_advisory(self, alert_id: uuid.UUID) -> Optional[AIManeuverAdvisory]:
        stmt = select(AIManeuverAdvisory).where(AIManeuverAdvisory.alert_id == alert_id)
        res = await self.db.execute(stmt)
        return res.scalars().first()

    def _format_advisory_response(
        self,
        advisory: AIManeuverAdvisory,
        alert: ConjunctionAlert,
        is_cached: bool = True,
    ) -> AIManeuverAdvisoryResponse:
        data = advisory.recommendation_data
        rec_content = AdvisoryRecommendationContent(
            qualitative_risk_summary=data.get("qualitative_risk_summary", ""),
            maneuver_strategy=data.get("maneuver_strategy", "In-Track Phasing Adjustment"),
            burn_direction_rationale=data.get("burn_direction_rationale", ""),
            optimal_timing_window=data.get("optimal_timing_window", "12 to 24 hours prior to TCA"),
            operational_tradeoffs=data.get("operational_tradeoffs", []),
            verification_checklist=data.get("verification_checklist", []),
            confidence_assessment=data.get("confidence_assessment", "High qualitative confidence"),
            disclaimer=data.get("disclaimer", DEFAULT_DISCLAIMER),
        )

        return AIManeuverAdvisoryResponse(
            id=str(advisory.id),
            alertId=str(advisory.alert_id),
            satelliteNoradId=advisory.satellite_norad_id,
            satelliteName=alert.satellite_a_name,
            secondaryName=alert.satellite_b_name,
            secondaryNoradId=alert.satellite_b_norad_id,
            riskLevel=alert.risk_level,
            missDistanceKm=alert.miss_distance_km,
            tca=alert.tca,
            recommendation=rec_content,
            modelUsed=advisory.model_used,
            isCached=is_cached,
            createdAt=advisory.created_at,
            updatedAt=advisory.updated_at,
        )

    def _generate_deterministic_advisory(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Astrodynamics-grounded qualitative advisory generator used when Google Gemini / Anthropic API
        key is not provided or during offline development mode.
        """
        conj = context["conjunction"]
        prim = context["primary_satellite"]
        sec = context["secondary_object"]

        hours_tca = conj["hours_until_tca"]
        days_tca = conj["days_until_tca"]
        rel_vel = conj["relative_velocity_km_s"]
        miss_km = conj["miss_distance_km"]
        risk = conj["risk_level"].upper()
        p_name = prim["name"]
        s_name = sec["name"]
        period = prim.get("period_minutes", 96.0)

        # Astrodynamics strategy heuristic:
        if rel_vel > 11.0:
            strategy = "In-Track Phasing (Prograde Semi-Major Axis Boost)"
            direction_rationale = (
                f"Due to the high relative velocity ({rel_vel:.1f} km/s) and cross-orbit intersection angle, "
                f"an in-track prograde burn will increase the semi-major axis of {p_name}, slightly lengthening its orbital period ({period:.1f} min). "
                f"This creates secular along-track timing separation at the orbital crossing point without the excessive propellant cost of a direct plane change."
            )
            timing_revs = max(8, min(24, int(hours_tca * 60 / period / 2)))
            timing_window = f"Execute approximately {max(12, int(hours_tca * 0.4))} to {max(18, int(hours_tca * 0.7))} hours prior to TCA (~{timing_revs} orbital revolutions before encounter) to maximize along-track displacement with minimal propellant expenditure."
        elif miss_km < 1.0:
            strategy = "Radial Separation & In-Track Phasing Combination"
            direction_rationale = (
                f"With an ultra-close predicted miss distance of {conj['miss_distance_m']:.0f} m, "
                f"a combined prograde and radial vector establishes rapid geometry separation both along-track and in altitude, "
                f"ensuring immediate clearance of the {s_name} 3D error covariance ellipsoid."
            )
            timing_window = f"Execute 12 to 24 hours prior to TCA (~10 to 18 orbital periods prior) to allow deterministic dispersion away from the collision node."
        else:
            strategy = "In-Track Phasing (Retrograde Phase-Shift)"
            direction_rationale = (
                f"A retrograde in-track burn lowers orbital period slightly, advancing {p_name}'s arrival time at the intersection node. "
                f"This cleanly separates the encounter geometry with {s_name} while keeping apogee within nominal operational bounds."
            )
            timing_window = f"Execute 18 to 36 hours prior to TCA (~12 to 25 orbital periods prior) to achieve safe nodal spacing."

        summary = (
            f"[{risk} CONJUNCTION RISK] {p_name} (NORAD #{prim['norad_id']}) has a projected close approach "
            f"with {s_name} (NORAD #{sec['norad_id']}) in {days_tca:.1f} days ({hours_tca:.1f} hours). "
            f"The encounter features a miss distance of {miss_km:.2f} km ({conj['miss_distance_m']:.0f} m) "
            f"at a relative velocity of {rel_vel:.2f} km/s in {prim['orbit_regime']} orbit."
        )

        tradeoffs = [
            f"Secondary Screening Mandatory: Must screen post-burn trajectory against the Global Catalog before thruster firing.",
            f"Tracking Verification: Allow at least 2 ground station passes or TDRSS contacts post-burn to confirm orbit determination.",
            f"Propellant Penalty: In-track phasing utilizes secular along-track drift and uses substantially less delta-v than an out-of-plane inclination change.",
            f"Attitude Slew Constraints: Verify solar panel and payload thermal constraints during thruster pointing slew.",
        ]

        checklist = [
            f"Verify latest TLE / ephemeris epoch for {s_name} is less than 24 hours old.",
            f"Run candidate maneuver vector through certified Flight Dynamics System (FDS) with full gravity & atmospheric drag models.",
            f"Upload commands during line-of-sight pass with high elevation contact.",
            f"Perform post-execution orbit determination (OD) to confirm clearance.",
        ]

        return {
            "qualitative_risk_summary": summary,
            "maneuver_strategy": strategy,
            "burn_direction_rationale": direction_rationale,
            "optimal_timing_window": timing_window,
            "operational_tradeoffs": tradeoffs,
            "verification_checklist": checklist,
            "confidence_assessment": "High qualitative confidence based on SGP4 encounter geometry and orbital mechanics.",
            "disclaimer": DEFAULT_DISCLAIMER,
        }

    async def _call_gemini_api(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Calls Google Gemini API (generateContent) with strict structured JSON schema enforcement
        and rate-limit exponential backoff retry.
        """
        api_key = (
            self.settings.gemini_api_key
            or self.settings.google_api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        if not api_key:
            return None

        model_name = self.settings.ai_model_name or "gemini-2.5-flash"
        # Strip provider prefix if user specified it
        if model_name.startswith("models/"):
            model_name = model_name[7:]

        endpoint_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        )

        user_content = (
            f"Analyze this orbital conjunction event and generate the qualitative collision avoidance advisory JSON "
            f"adhering strictly to the schema:\n\n{json.dumps(context, indent=2)}"
        )

        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_content}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
                "responseSchema": GEMINI_RESPONSE_SCHEMA,
            },
        }

        max_retries = 3
        async with httpx.AsyncClient(timeout=35.0) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.post(
                        endpoint_url,
                        headers={"Content-Type": "application/json"},
                        json=payload,
                    )

                    # Handle Rate Limits (HTTP 429) or temporary service overload (HTTP 503)
                    if response.status_code in (429, 503):
                        retry_after = response.headers.get("Retry-After")
                        wait_sec = float(retry_after) if retry_after else (1.5 * (attempt + 1))
                        logger.warning(
                            f"Gemini API rate limit / 429 encountered on attempt {attempt + 1}/{max_retries}. "
                            f"Backing off for {wait_sec:.1f}s..."
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(wait_sec)
                            continue
                        else:
                            logger.error("Gemini API rate limit retries exhausted.")
                            return None

                    response.raise_for_status()
                    res_json = response.json()

                    candidates = res_json.get("candidates", [])
                    if not candidates:
                        logger.warning("Gemini API returned empty candidates.")
                        return None

                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if not parts:
                        logger.warning("Gemini API candidate has no parts.")
                        return None

                    raw_text = parts[0].get("text", "").strip()

                    # Strip markdown code blocks if returned
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:]
                    if raw_text.startswith("```"):
                        raw_text = raw_text[3:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3]

                    parsed = json.loads(raw_text.strip())
                    usage = res_json.get("usageMetadata", {})
                    parsed["_usage"] = {
                        "prompt_tokens": usage.get("promptTokenCount", 0),
                        "completion_tokens": usage.get("candidatesTokenCount", 0),
                    }
                    return parsed

                except httpx.HTTPStatusError as http_err:
                    if http_err.response.status_code in (429, 503) and attempt < max_retries - 1:
                        wait_sec = 2.0 * (attempt + 1)
                        logger.warning(f"Gemini HTTP {http_err.response.status_code}. Retrying in {wait_sec}s...")
                        await asyncio.sleep(wait_sec)
                        continue
                    logger.error(f"Gemini API HTTP Error ({http_err.response.status_code}): {http_err.response.text}")
                    return None
                except Exception as exc:
                    logger.error(f"Error communicating with Gemini API: {exc}")
                    return None

        return None

    async def _call_anthropic_api(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fallback for Anthropic Messages API if ANTHROPIC_API_KEY is explicitly configured.
        """
        api_key = self.settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None

        model_name = self.settings.ai_model_name or "claude-3-5-haiku-20241022"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        user_content = (
            f"Analyze this conjunction event and return the qualitative collision avoidance advisory JSON:\n\n"
            f"{json.dumps(context, indent=2)}"
        )

        payload = {
            "model": model_name,
            "max_tokens": 1200,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_content}],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            res_json = response.json()

            content_blocks = res_json.get("content", [])
            if not content_blocks:
                return None

            raw_text = content_blocks[0].get("text", "").strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            parsed = json.loads(raw_text.strip())
            usage = res_json.get("usage", {})
            parsed["_usage"] = {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            }
            return parsed

    async def generate_or_get_advisory(
        self,
        alert_id: str,
        force_refresh: bool = False,
    ) -> AIManeuverAdvisoryResponse:
        """
        Generates or retrieves a cached qualitative advisory for a conjunction alert.
        Primary provider: Google Gemini API (gemini-2.5-flash) with rate limit retry & heuristic simulation fallback.
        """
        alert = await self.get_alert_by_id(alert_id)
        if not alert:
            raise ValueError(f"Conjunction alert with ID '{alert_id}' not found.")

        # Check existing cache
        existing = await self.get_cached_advisory(alert.id)
        if existing and not force_refresh:
            return self._format_advisory_response(existing, alert, is_cached=True)

        # Assemble orbital context
        context = await self.get_orbital_context(alert)

        # Determine target model name
        model_name = self.settings.ai_model_name or "gemini-2.5-flash"
        prompt_tokens = 0
        completion_tokens = 0

        # Attempt 1: Call Gemini API
        llm_result = await self._call_gemini_api(context)

        # Attempt 2: Optional fallback to Anthropic if Gemini key is absent but Anthropic key is set
        if not llm_result and (self.settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")):
            try:
                llm_result = await self._call_anthropic_api(context)
                if llm_result:
                    model_name = "claude-3-5-haiku-20241022"
            except Exception as exc:
                logger.warning(f"Anthropic fallback also failed: {exc}")

        if llm_result:
            usage = llm_result.pop("_usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            recommendation_data = llm_result
        else:
            # Fallback to deterministic astrodynamics simulation
            logger.info("Live AI API key not configured or rate-limited; generating deterministic advisory.")
            model_name = f"{model_name} (simulated)"
            recommendation_data = self._generate_deterministic_advisory(context)

        # Ensure disclaimer is populated
        if "disclaimer" not in recommendation_data:
            recommendation_data["disclaimer"] = DEFAULT_DISCLAIMER

        now = datetime.now(timezone.utc)

        # Upsert into database cache
        if existing:
            existing.recommendation_data = recommendation_data
            existing.model_used = model_name
            existing.prompt_tokens = prompt_tokens
            existing.completion_tokens = completion_tokens
            existing.updated_at = now
            self.db.add(existing)
            await self.db.commit()
            await self.db.refresh(existing)
            saved_advisory = existing
        else:
            new_advisory = AIManeuverAdvisory(
                id=uuid.uuid4(),
                alert_id=alert.id,
                satellite_norad_id=alert.satellite_a_norad_id,
                recommendation_data=recommendation_data,
                model_used=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                created_at=now,
                updated_at=now,
            )
            self.db.add(new_advisory)
            await self.db.commit()
            await self.db.refresh(new_advisory)
            saved_advisory = new_advisory

        return self._format_advisory_response(saved_advisory, alert, is_cached=False)

    async def get_all_advisories(self) -> List[AIManeuverAdvisoryResponse]:
        """
        Returns all stored cached advisories mapped to their alert objects.
        """
        stmt = (
            select(AIManeuverAdvisory)
            .join(ConjunctionAlert, AIManeuverAdvisory.alert_id == ConjunctionAlert.id)
            .options(selectinload(AIManeuverAdvisory.alert))
            .order_by(AIManeuverAdvisory.updated_at.desc())
        )
        res = await self.db.execute(stmt)
        advisories = res.scalars().all()

        responses = []
        for adv in advisories:
            if adv.alert:
                responses.append(self._format_advisory_response(adv, adv.alert, is_cached=True))
        return responses
