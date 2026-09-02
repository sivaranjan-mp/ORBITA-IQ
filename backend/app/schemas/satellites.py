from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class SatelliteAddRequest(BaseModel):
    norad_id: int = Field(...,
                          description="The NORAD ID (CATNR) of the satellite to add")


class SatelliteAddFromTLERequest(BaseModel):
    raw_tle: str = Field(...,
                         description="Raw 2-line or 3-line TLE string for the satellite")


class SatelliteUpdateRequest(BaseModel):
    name: Optional[str] = None
    ownerOrg: Optional[str] = None
    status: Optional[str] = None


class TLEUploadRequest(BaseModel):
    norad_id: int
    raw_tle: str


class CCSDSOMM(BaseModel):
    CCSDS_OMM_VERS: str = Field(..., description="OMM Version")
    CREATION_DATE: str
    ORIGINATOR: str
    OBJECT_NAME: str
    OBJECT_ID: str
    CENTER_NAME: str
    REF_FRAME: str
    TIME_SYSTEM: str
    MEAN_ELEMENT_THEORY: str
    EPOCH: str
    MEAN_MOTION: float
    ECCENTRICITY: float
    INCLINATION: float
    RA_OF_ASC_NODE: float
    ARG_OF_PERICENTER: float
    MEAN_ANOMALY: float
    EPHEMERIS_TYPE: int
    CLASSIFICATION_TYPE: str
    NORAD_CAT_ID: int
    ELEMENT_SET_NO: int
    REV_AT_EPOCH: int
    BSTAR: float
    MEAN_MOTION_DOT: float
    MEAN_MOTION_DDOT: float

class OMMUploadRequest(BaseModel):
    payload: CCSDSOMM

class SatelliteResponse(BaseModel):
    id: str
    noradId: int
    name: str
    internationalDesignator: str
    objectType: str
    status: str
    ownerOrg: str
    ownerName: Optional[str] = None
    ownerEmployeeId: Optional[str] = None
    altitudeKm: Optional[float] = None
    latitudeDeg: Optional[float] = None
    longitudeDeg: Optional[float] = None
    velocityKmS: Optional[float] = None
    inclinationDeg: Optional[float] = None
    periodMinutes: Optional[float] = None
    eccentricity: Optional[float] = None
    lastTleEpoch: Optional[datetime] = None
    raanDeg: Optional[float] = None
    meanAnomalyDeg: Optional[float] = None


class SatelliteBulkAddRequest(BaseModel):
    norad_ids: list[int] = Field(..., description="List of NORAD IDs to add")


class SatelliteBulkAddResult(BaseModel):
    norad_id: int
    success: bool
    reason: Optional[str] = None


class SatelliteBulkAddResponse(BaseModel):
    successful: int
    failed: int
    results: list[SatelliteBulkAddResult]
