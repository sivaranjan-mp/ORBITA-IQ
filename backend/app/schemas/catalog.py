from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CatalogItemResponse(BaseModel):
    noradId: int
    name: str
    internationalDesignator: Optional[str] = None
    objectType: Optional[str] = "payload"
    orbitRegime: Optional[str] = "LEO"
    apogeeKm: Optional[float] = None
    perigeeKm: Optional[float] = None
    inclinationDeg: Optional[float] = None
    periodMinutes: Optional[float] = None
    isTracked: bool = False
    trackedSatelliteId: Optional[str] = None
    epoch: Optional[datetime] = None


class CatalogListResponse(BaseModel):
    items: List[CatalogItemResponse]
    total: int
    page: int
    limit: int
    totalPages: int


class CatalogSyncResponse(BaseModel):
    syncedCount: int
    message: str
