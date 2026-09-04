from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

DEFAULT_DISCLAIMER = (
    "OPERATOR ADVISORY NOTICE: AI-generated orbital risk assessment and qualitative "
    "maneuver advisory for operator review only. This is not a certified flight-dynamics "
    "maneuver solution or precision ephemeris product. All tactical maneuvers must be "
    "verified using certified Astrodynamics Flight Dynamics System (FDS) tools and official "
    "Space Command CDMs prior to execution."
)


class AdvisoryRecommendationRequest(BaseModel):
    alert_id: str
    force_refresh: bool = False


class AdvisoryRecommendationContent(BaseModel):
    qualitative_risk_summary: str = Field(
        ..., description="Human-readable plain English explanation of the encounter geometry and collision dynamics."
    )
    maneuver_strategy: str = Field(
        ..., description="Qualitative maneuver approach (e.g., In-Track Phasing Prograde Boost, Out-of-Plane Cross-Track Separation, Radial Separation, Hold & Monitor)."
    )
    burn_direction_rationale: str = Field(
        ..., description="Physical rationale for the suggested burn direction based on orbital mechanics."
    )
    optimal_timing_window: str = Field(
        ..., description="Guidance on when to execute relative to TCA in orbital periods or lead hours."
    )
    operational_tradeoffs: List[str] = Field(
        default_factory=list, description="Key operational considerations including secondary screening and propellant impact."
    )
    verification_checklist: List[str] = Field(
        default_factory=list, description="Checklist steps for the flight operations team before any burn execution."
    )
    confidence_assessment: Optional[str] = Field(
        default="High qualitative confidence based on orbital regime geometry.",
        description="Qualitative confidence rating of the advisory."
    )
    disclaimer: str = Field(
        default=DEFAULT_DISCLAIMER,
        description="Mandatory operator safety disclaimer."
    )


class AIManeuverAdvisoryResponse(BaseModel):
    id: str
    alertId: str
    satelliteNoradId: int
    satelliteName: str
    secondaryName: str
    secondaryNoradId: int
    riskLevel: str
    missDistanceKm: float
    tca: datetime
    recommendation: AdvisoryRecommendationContent
    modelUsed: str
    isCached: bool = False
    createdAt: datetime
    updatedAt: datetime
