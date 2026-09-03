from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AlertStatusUpdate(BaseModel):
    status: str


class ConjunctionAlertResponse(BaseModel):
    id: str
    primarySatellite: str
    primaryNoradId: int
    secondaryObject: str
    secondaryNoradId: int
    tca: datetime
    missDistanceM: float
    missDistanceKm: Optional[float] = None
    relativeVelocityKmS: Optional[float] = None
    probability: float = 0.0
    riskLevel: str
    status: str
    screeningScope: Optional[str] = "fleet_vs_catalog"
    detectedBy: str = "satguard"
    createdAt: datetime
    computedAt: Optional[datetime] = None


class ScreeningRunResponse(BaseModel):
    message: str
    eventsCreated: int
    totalDetected: int
    stage1Survivors: int
    durationSeconds: float
