from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class SatelliteAddRequest(BaseModel):
    norad_id: int = Field(..., description="The NORAD ID (CATNR) of the satellite to add")

class SatelliteUpdateRequest(BaseModel):
    name: Optional[str] = None
    ownerOrg: Optional[str] = None
    status: Optional[str] = None

class TLEUploadRequest(BaseModel):
    norad_id: int
    raw_tle: str

class OMMUploadRequest(BaseModel):
    payload: dict

class SatelliteResponse(BaseModel):
    id: str
    noradId: int
    name: str
    internationalDesignator: str
    objectType: str
    status: str
    ownerOrg: str
    altitudeKm: float
    inclinationDeg: float
    periodMinutes: float
    eccentricity: float
    lastTleEpoch: datetime
    raanDeg: float
    meanAnomalyDeg: float
