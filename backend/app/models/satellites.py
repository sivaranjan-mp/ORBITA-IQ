from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from app.db.session import Base


class Satellite(Base):
    __tablename__ = 'satellites'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    norad_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    international_designator: Mapped[Optional[str]
                                     ] = mapped_column(String, nullable=True)
    object_type: Mapped[Optional[str]] = mapped_column(
        String, default="payload")
    status: Mapped[Optional[str]] = mapped_column(String, default="active")
    owner_org: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(
        timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    orbit_state: Mapped[Optional["OrbitState"]] = relationship(
        back_populates="satellite", uselist=False, cascade="all, delete-orphan")
    tle_records: Mapped[List["TLERecord"]] = relationship(
        back_populates="satellite", cascade="all, delete-orphan")
    omm_records: Mapped[List["OMMRecord"]] = relationship(
        back_populates="satellite", cascade="all, delete-orphan")


class OrbitState(Base):
    __tablename__ = 'orbit_state'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    satellite_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(
        'satellites.id', ondelete='CASCADE'), unique=True, nullable=False)
    altitude_km: Mapped[float] = mapped_column(Float, nullable=False)
    latitude_deg: Mapped[float] = mapped_column(
        Float, nullable=False, default=0)
    longitude_deg: Mapped[float] = mapped_column(
        Float, nullable=False, default=0)
    velocity_km_s: Mapped[float] = mapped_column(
        Float, nullable=False, default=0)
    inclination_deg: Mapped[float] = mapped_column(Float, nullable=False)
    period_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    eccentricity: Mapped[float] = mapped_column(Float, nullable=False)
    raan_deg: Mapped[float] = mapped_column(Float, nullable=False)
    mean_anomaly_deg: Mapped[float] = mapped_column(Float, nullable=False)
    epoch: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)

    x_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    y_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vx_kms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vy_kms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vz_kms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(
        timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    satellite: Mapped["Satellite"] = relationship(back_populates="orbit_state")


class TLERecord(Base):
    __tablename__ = 'tle_records'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    satellite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('satellites.id', ondelete='CASCADE'), nullable=False)
    line1: Mapped[str] = mapped_column(String, nullable=False)
    line2: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String, default="celestrak")
    epoch: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    satellite: Mapped["Satellite"] = relationship(back_populates="tle_records")


class OMMRecord(Base):
    __tablename__ = 'omm_records'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    satellite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('satellites.id', ondelete='CASCADE'), nullable=False)
    epoch: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    satellite: Mapped["Satellite"] = relationship(back_populates="omm_records")
