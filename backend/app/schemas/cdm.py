import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from app.schemas.astrodynamics import CovarianceMatrixResponse, StateVectorResponse


class CDMRecordBase(BaseModel):
    primary_norad_id: int = Field(..., description="NORAD ID of primary object")
    secondary_norad_id: int = Field(..., description="NORAD ID of secondary object")
    tca: datetime = Field(..., description="Time of closest approach")
    payload: Dict[str, Any] = Field(..., description="Raw CCSDS CDM payload")
    message_id: Optional[str] = None
    originator: Optional[str] = None
    emergency_reportable: bool = False
    miss_distance_m: Optional[float] = None
    relative_speed_km_s: Optional[float] = None
    collision_probability: Optional[float] = None
    source_id: Optional[uuid.UUID] = None
    algorithm_version_id: Optional[uuid.UUID] = None
    primary_state_vector_id: Optional[uuid.UUID] = None
    secondary_state_vector_id: Optional[uuid.UUID] = None
    primary_covariance_matrix_id: Optional[uuid.UUID] = None
    secondary_covariance_matrix_id: Optional[uuid.UUID] = None


class CDMRecordCreate(CDMRecordBase):
    pass


class CDMRecordResponse(CDMRecordBase):
    id: uuid.UUID
    created_at: datetime
    primary_state_vector: Optional[StateVectorResponse] = None
    secondary_state_vector: Optional[StateVectorResponse] = None
    primary_covariance_matrix: Optional[CovarianceMatrixResponse] = None
    secondary_covariance_matrix: Optional[CovarianceMatrixResponse] = None

    class Config:
        from_attributes = True
