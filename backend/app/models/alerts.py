from sqlalchemy import Column, String, Float, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone

from app.db.session import Base
from app.models.satellites import Satellite
from app.models.conjunctions import ConjunctionEvent

class Alert(Base):
    __tablename__ = 'alerts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conjunction_event_id = Column(UUID(as_uuid=True), ForeignKey('conjunction_events.id', ondelete='CASCADE'), nullable=False)
    satellite_a_id = Column(UUID(as_uuid=True), ForeignKey('satellites.id', ondelete='CASCADE'), nullable=False)
    satellite_b_id = Column(UUID(as_uuid=True), ForeignKey('satellites.id', ondelete='CASCADE'), nullable=True)
    miss_distance = Column(Float, nullable=False)
    relative_velocity = Column(Float, nullable=True)
    time_of_closest_approach = Column(DateTime(timezone=True), nullable=False)
    risk_level = Column(String, nullable=False)
    status = Column(String, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    conjunction_event = relationship("ConjunctionEvent", lazy="selectin")
    satellite_a = relationship("Satellite", foreign_keys=[satellite_a_id], lazy="selectin")
    satellite_b = relationship("Satellite", foreign_keys=[satellite_b_id], lazy="selectin")
    history = relationship("AlertHistory", back_populates="alert", cascade="all, delete-orphan", lazy="selectin")

class AlertHistory(Base):
    __tablename__ = 'alert_history'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey('alerts.id', ondelete='CASCADE'), nullable=False)
    risk_level = Column(String, nullable=False)
    miss_distance = Column(Float, nullable=False)
    relative_velocity = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    alert = relationship("Alert", back_populates="history")
