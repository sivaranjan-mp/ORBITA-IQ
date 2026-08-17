from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone

from app.db.session import Base

class Satellite(Base):
    __tablename__ = 'satellites'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    norad_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    international_designator = Column(String, nullable=True)
    object_type = Column(String, default="payload")
    status = Column(String, default="active")
    owner_org = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    orbit_state = relationship("OrbitState", back_populates="satellite", uselist=False, cascade="all, delete-orphan")
    tle_records = relationship("TLERecord", back_populates="satellite", cascade="all, delete-orphan")
    omm_records = relationship("OMMRecord", back_populates="satellite", cascade="all, delete-orphan")

class OrbitState(Base):
    __tablename__ = 'orbit_state'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    satellite_id = Column(UUID(as_uuid=True), ForeignKey('satellites.id', ondelete='CASCADE'), unique=True, nullable=False)
    altitude_km = Column(Float, nullable=False)
    latitude_deg = Column(Float, nullable=False, default=0)
    longitude_deg = Column(Float, nullable=False, default=0)
    velocity_km_s = Column(Float, nullable=False, default=0)
    inclination_deg = Column(Float, nullable=False)
    period_minutes = Column(Float, nullable=False)
    eccentricity = Column(Float, nullable=False)
    raan_deg = Column(Float, nullable=False)
    mean_anomaly_deg = Column(Float, nullable=False)
    epoch = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    satellite = relationship("Satellite", back_populates="orbit_state")

class TLERecord(Base):
    __tablename__ = 'tle_records'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    satellite_id = Column(UUID(as_uuid=True), ForeignKey('satellites.id', ondelete='CASCADE'), nullable=False)
    line1 = Column(String, nullable=False)
    line2 = Column(String, nullable=False)
    source = Column(String, default="celestrak")
    epoch = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    satellite = relationship("Satellite", back_populates="tle_records")

class OMMRecord(Base):
    __tablename__ = 'omm_records'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    satellite_id = Column(UUID(as_uuid=True), ForeignKey('satellites.id', ondelete='CASCADE'), nullable=False)
    epoch = Column(DateTime(timezone=True), nullable=True)
    payload = Column(String, nullable=False) # JSON is stored as String/JSONB. We'll simplify to String mapping for SQLAlchemy or use JSONB
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    satellite = relationship("Satellite", back_populates="omm_records")
