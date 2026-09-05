from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AlertStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


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


class AlertStatusHistoryResponse(BaseModel):
    id: str
    alertId: str
    primarySatellite: str
    primaryNoradId: int
    secondaryObject: str
    secondaryNoradId: int
    riskLevel: str
    previousStatus: str
    newStatus: str
    actionTaken: str
    changedBy: Optional[str] = None
    operatorName: Optional[str] = None
    changedAt: datetime
    notes: Optional[str] = None


class AlertStatusHistoryListResponse(BaseModel):
    items: List[AlertStatusHistoryResponse]
    total: int
    page: int
    limit: int
    totalPages: int

