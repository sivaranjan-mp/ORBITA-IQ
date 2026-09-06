import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------
class DataSourceBase(BaseModel):
    code: str = Field(..., description="Unique source code, e.g. CELESTRAK, SPACE_TRACK")
    name: str = Field(..., description="Display name for the source")
    category: str = Field(..., description="EXTERNAL_CATALOG, INTERNAL_PROPAGATION, etc.")
    is_authoritative: bool = False
    description: Optional[str] = None
    api_endpoint: Optional[str] = None


class DataSourceCreate(DataSourceBase):
    pass


class DataSourceResponse(DataSourceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Algorithm Versions
# -----------------------------------------------------------------------------
class AlgorithmVersionBase(BaseModel):
    name: str
    version: str
    author: Optional[str] = None
    description: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class AlgorithmVersionCreate(AlgorithmVersionBase):
    pass


class AlgorithmVersionResponse(AlgorithmVersionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# State Vectors
# -----------------------------------------------------------------------------
class StateVectorBase(BaseModel):
    epoch: datetime
    reference_frame: str = "TEME"
    x_km: float
    y_km: float
    z_km: float
    vx_kms: float
    vy_kms: float
    vz_kms: float
    satellite_id: Optional[uuid.UUID] = None
    norad_id: Optional[int] = None
    source_id: Optional[uuid.UUID] = None
    entity_tag: Optional[str] = None


class StateVectorCreate(StateVectorBase):
    pass


class StateVectorResponse(StateVectorBase):
    id: uuid.UUID
    oem_record_id: Optional[uuid.UUID] = None
    sequence_idx: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Covariance Matrices
# -----------------------------------------------------------------------------
class CovarianceMatrixBase(BaseModel):
    state_vector_id: Optional[uuid.UUID] = None
    reference_frame: str = "RTN"
    cx_x: float
    cx_y: float = 0.0
    cx_z: float = 0.0
    cy_y: float
    cy_z: float = 0.0
    cz_z: float
    cx_vx: Optional[float] = 0.0
    cx_vy: Optional[float] = 0.0
    cx_vz: Optional[float] = 0.0
    cy_vx: Optional[float] = 0.0
    cy_vy: Optional[float] = 0.0
    cy_vz: Optional[float] = 0.0
    cz_vx: Optional[float] = 0.0
    cz_vy: Optional[float] = 0.0
    cz_vz: Optional[float] = 0.0
    cvx_vx: Optional[float] = 0.0
    cvx_vy: Optional[float] = 0.0
    cvx_vz: Optional[float] = 0.0
    cvy_vy: Optional[float] = 0.0
    cvy_vz: Optional[float] = 0.0
    cvz_vz: Optional[float] = 0.0
    raw_matrix: Optional[Dict[str, Any]] = None


class CovarianceMatrixCreate(CovarianceMatrixBase):
    pass


class CovarianceMatrixResponse(CovarianceMatrixBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Orbit Solutions
# -----------------------------------------------------------------------------
class OrbitSolutionBase(BaseModel):
    norad_id: int
    epoch: datetime
    solution_type: str = "SGP4_TLE"
    satellite_id: Optional[uuid.UUID] = None
    state_vector_id: Optional[uuid.UUID] = None
    covariance_matrix_id: Optional[uuid.UUID] = None
    source_id: Optional[uuid.UUID] = None
    algorithm_version_id: Optional[uuid.UUID] = None
    fit_span_hours: Optional[float] = None
    observations_used: Optional[int] = None
    observations_available: Optional[int] = None
    weighted_rms: Optional[float] = None
    residuals_summary: Optional[Dict[str, Any]] = None
    semi_major_axis_km: Optional[float] = None
    eccentricity: Optional[float] = None
    inclination_deg: Optional[float] = None
    raan_deg: Optional[float] = None
    arg_of_perigee_deg: Optional[float] = None
    mean_anomaly_deg: Optional[float] = None
    period_minutes: Optional[float] = None
    bstar: Optional[float] = None


class OrbitSolutionCreate(OrbitSolutionBase):
    pass


class OrbitSolutionResponse(OrbitSolutionBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# OEM Records
# -----------------------------------------------------------------------------
class OEMRecordBase(BaseModel):
    object_name: str
    object_id: str
    originator: str
    start_time: datetime
    stop_time: datetime
    message_id: Optional[str] = None
    interpolation_method: Optional[str] = "HERMITE"
    interpolation_degree: Optional[int] = 7
    reference_frame: str = "ECI_J2000"
    time_system: str = "UTC"
    satellite_id: Optional[uuid.UUID] = None
    norad_id: Optional[int] = None
    source_id: Optional[uuid.UUID] = None
    raw_metadata: Optional[Dict[str, Any]] = None


class OEMRecordCreate(OEMRecordBase):
    ephemeris_points: Optional[List[StateVectorCreate]] = None


class OEMRecordResponse(OEMRecordBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Data Freshness
# -----------------------------------------------------------------------------
class DataFreshnessBase(BaseModel):
    source_id: uuid.UUID
    entity_type: str
    entity_id: Optional[uuid.UUID] = None
    norad_id: Optional[int] = None
    last_attempt_at: datetime
    last_success_at: Optional[datetime] = None
    latest_data_epoch: Optional[datetime] = None
    staleness_threshold_hours: float = 24.0
    sync_status: str = "healthy"
    records_synced: Optional[int] = 0
    error_message: Optional[str] = None


class DataFreshnessResponse(DataFreshnessBase):
    id: uuid.UUID
    updated_at: datetime

    class Config:
        from_attributes = True
