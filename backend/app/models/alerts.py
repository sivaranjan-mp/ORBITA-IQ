from sqlalchemy import String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from app.db.session import Base
from app.models.enums import AlertState, RiskLevel

if TYPE_CHECKING:
    from app.models.satellites import Satellite
    from app.models.conjunctions import ConjunctionEvent


class Alert(Base):
    __tablename__ = 'alerts'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conjunction_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('conjunction_events.id', ondelete='CASCADE'), nullable=False)
    satellite_a_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('satellites.id', ondelete='CASCADE'), nullable=False)
    satellite_b_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('satellites.id', ondelete='CASCADE'), nullable=True)
    miss_distance: Mapped[float] = mapped_column(Float, nullable=False)
    relative_velocity: Mapped[Optional[float]
                              ] = mapped_column(Float, nullable=True)
    time_of_closest_approach: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    risk_level: Mapped[str] = mapped_column(
        ENUM(RiskLevel, name="risk_level", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        ENUM(AlertState, name="alert_state", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default="active"
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(
        timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    conjunction_event: Mapped["ConjunctionEvent"] = relationship(
        lazy="selectin")
    satellite_a: Mapped["Satellite"] = relationship(
        foreign_keys=[satellite_a_id], lazy="selectin")
    satellite_b: Mapped[Optional["Satellite"]] = relationship(
        foreign_keys=[satellite_b_id], lazy="selectin")
    history: Mapped[list["AlertHistory"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan", lazy="selectin")


class AlertHistory(Base):
    __tablename__ = 'alert_history'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('alerts.id', ondelete='CASCADE'), nullable=False)
    risk_level: Mapped[str] = mapped_column(
        ENUM(RiskLevel, name="risk_level", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    miss_distance: Mapped[float] = mapped_column(Float, nullable=False)
    relative_velocity: Mapped[Optional[float]
                              ] = mapped_column(Float, nullable=True)
    timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    alert: Mapped["Alert"] = relationship(back_populates="history")
