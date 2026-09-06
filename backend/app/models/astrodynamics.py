import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.satellites import Satellite


class DataSource(Base):
    __tablename__ = 'data_sources'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    is_authoritative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    api_endpoint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AlgorithmVersion(Base):
    __tablename__ = 'algorithm_versions'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class OEMRecord(Base):
    __tablename__ = 'oem_records'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    satellite_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('satellites.id', ondelete='SET NULL'), nullable=True
    )
    norad_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    object_name: Mapped[str] = mapped_column(String, nullable=False)
    object_id: Mapped[str] = mapped_column(String, nullable=False)
    originator: Mapped[str] = mapped_column(String, nullable=False)
    message_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stop_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interpolation_method: Mapped[Optional[str]] = mapped_column(String, default="HERMITE")
    interpolation_degree: Mapped[Optional[int]] = mapped_column(Integer, default=7)
    reference_frame: Mapped[str] = mapped_column(String, default="ECI_J2000", nullable=False)
    time_system: Mapped[str] = mapped_column(String, default="UTC", nullable=False)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('data_sources.id', ondelete='SET NULL'), nullable=True, index=True
    )
    raw_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    state_vectors: Mapped[List["StateVector"]] = relationship(
        back_populates="oem_record", cascade="all, delete-orphan", order_by="StateVector.sequence_idx"
    )


class StateVector(Base):
    __tablename__ = 'state_vectors'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    satellite_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('satellites.id', ondelete='SET NULL'), nullable=True, index=True
    )
    norad_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    epoch: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reference_frame: Mapped[str] = mapped_column(String, default="TEME", nullable=False)
    x_km: Mapped[float] = mapped_column(Float, nullable=False)
    y_km: Mapped[float] = mapped_column(Float, nullable=False)
    z_km: Mapped[float] = mapped_column(Float, nullable=False)
    vx_kms: Mapped[float] = mapped_column(Float, nullable=False)
    vy_kms: Mapped[float] = mapped_column(Float, nullable=False)
    vz_kms: Mapped[float] = mapped_column(Float, nullable=False)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('data_sources.id', ondelete='SET NULL'), nullable=True, index=True
    )
    oem_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('oem_records.id', ondelete='CASCADE'), nullable=True, index=True
    )
    sequence_idx: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    entity_tag: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    oem_record: Mapped[Optional["OEMRecord"]] = relationship(back_populates="state_vectors")
    covariance: Mapped[Optional["CovarianceMatrix"]] = relationship(
        back_populates="state_vector", uselist=False, cascade="all, delete-orphan"
    )


class CovarianceMatrix(Base):
    __tablename__ = 'covariance_matrices'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    state_vector_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('state_vectors.id', ondelete='CASCADE'), nullable=True, index=True
    )
    reference_frame: Mapped[str] = mapped_column(String, default="RTN", nullable=False)

    # Position-Position Covariance (km^2)
    cx_x: Mapped[float] = mapped_column(Float, nullable=False)
    cx_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cx_z: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cy_y: Mapped[float] = mapped_column(Float, nullable=False)
    cy_z: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cz_z: Mapped[float] = mapped_column(Float, nullable=False)

    # Position-Velocity Cross-Terms (km^2/s)
    cx_vx: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cx_vy: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cx_vz: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cy_vx: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cy_vy: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cy_vz: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cz_vx: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cz_vy: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cz_vz: Mapped[Optional[float]] = mapped_column(Float, default=0.0)

    # Velocity-Velocity Covariance ((km/s)^2)
    cvx_vx: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cvx_vy: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cvx_vz: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cvy_vy: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cvy_vz: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    cvz_vz: Mapped[Optional[float]] = mapped_column(Float, default=0.0)

    raw_matrix: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    state_vector: Mapped[Optional["StateVector"]] = relationship(back_populates="covariance")


class OrbitSolution(Base):
    __tablename__ = 'orbit_solutions'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    satellite_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('satellites.id', ondelete='SET NULL'), nullable=True, index=True
    )
    norad_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    epoch: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    solution_type: Mapped[str] = mapped_column(String, default="SGP4_TLE", nullable=False)
    state_vector_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('state_vectors.id', ondelete='SET NULL'), nullable=True, index=True
    )
    covariance_matrix_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('covariance_matrices.id', ondelete='SET NULL'), nullable=True, index=True
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('data_sources.id', ondelete='SET NULL'), nullable=True, index=True
    )
    algorithm_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('algorithm_versions.id', ondelete='SET NULL'), nullable=True, index=True
    )

    # Solution quality / OD fit metadata
    fit_span_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    observations_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    observations_available: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weighted_rms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    residuals_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Keplerian representation summary for fast filtering
    semi_major_axis_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eccentricity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    inclination_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raan_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    arg_of_perigee_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mean_anomaly_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    period_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bstar: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    state_vector: Mapped[Optional["StateVector"]] = relationship()
    covariance_matrix: Mapped[Optional["CovarianceMatrix"]] = relationship()
    source: Mapped[Optional["DataSource"]] = relationship()
    algorithm_version: Mapped[Optional["AlgorithmVersion"]] = relationship()


class DataFreshness(Base):
    __tablename__ = 'data_freshness'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('data_sources.id', ondelete='CASCADE'), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    norad_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    last_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_data_epoch: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    staleness_threshold_hours: Mapped[float] = mapped_column(Float, default=24.0, nullable=False)
    sync_status: Mapped[str] = mapped_column(String, default="healthy", nullable=False, index=True)
    records_synced: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    source: Mapped["DataSource"] = relationship()


class CDMRecord(Base):
    __tablename__ = 'cdm_records'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    primary_norad_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    secondary_norad_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tca: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Extended fields
    message_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    originator: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    emergency_reportable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    primary_state_vector_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('state_vectors.id', ondelete='SET NULL'), nullable=True, index=True
    )
    secondary_state_vector_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('state_vectors.id', ondelete='SET NULL'), nullable=True, index=True
    )
    primary_covariance_matrix_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('covariance_matrices.id', ondelete='SET NULL'), nullable=True, index=True
    )
    secondary_covariance_matrix_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('covariance_matrices.id', ondelete='SET NULL'), nullable=True, index=True
    )
    miss_distance_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relative_speed_km_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    collision_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('data_sources.id', ondelete='SET NULL'), nullable=True, index=True
    )
    algorithm_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('algorithm_versions.id', ondelete='SET NULL'), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    primary_state_vector: Mapped[Optional["StateVector"]] = relationship(
        foreign_keys=[primary_state_vector_id]
    )
    secondary_state_vector: Mapped[Optional["StateVector"]] = relationship(
        foreign_keys=[secondary_state_vector_id]
    )
    primary_covariance_matrix: Mapped[Optional["CovarianceMatrix"]] = relationship(
        foreign_keys=[primary_covariance_matrix_id]
    )
    secondary_covariance_matrix: Mapped[Optional["CovarianceMatrix"]] = relationship(
        foreign_keys=[secondary_covariance_matrix_id]
    )
    source: Mapped[Optional["DataSource"]] = relationship(foreign_keys=[source_id])
    algorithm_version: Mapped[Optional["AlgorithmVersion"]] = relationship(foreign_keys=[algorithm_version_id])
