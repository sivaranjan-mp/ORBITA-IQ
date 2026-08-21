from pydantic import BaseModel
from datetime import datetime


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
    probability: float
    riskLevel: str
    status: str
    detectedBy: str
    createdAt: datetime
