import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import AlertState, ConjunctionStatus, RiskLevel

if TYPE_CHECKING:
    from app.models.conjunctions import ConjunctionEvent
    from app.models.satellites import Satellite


class ConjunctionAlert(Base):
    """
    Canonical single source of truth table for conjunction screening alerts
    across fleet vs fleet and fleet vs space catalog.
    """
    __tablename__ = 'conjunction_alerts'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    satellite_a_norad_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    satellite_a_name: Mapped[str] = mapped_column(String, nullable=False)
    satellite_b_norad_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    satellite_b_name: Mapped[str] = mapped_column(String, nullable=False)

    satellite_a_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('satellites.id', ondelete='CASCADE'), nullable=True
    )
    satellite_b_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('satellites.id', ondelete='SET NULL'), nullable=True
    )

    screening_scope: Mapped[str] = mapped_column(
        String, nullable=False, default="fleet_vs_catalog", index=True
    )
    tca: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    miss_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    miss_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    relative_velocity_km_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    risk_level: Mapped[str] = mapped_column(
        ENUM(RiskLevel, name="risk_level", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default="low",
        index=True
    )
    status: Mapped[str] = mapped_column(
        ENUM(ConjunctionStatus, name="alert_status", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default="open",
        index=True
    )
    detected_by: Mapped[str] = mapped_column(String, nullable=False, default="satguard")

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    satellite_a: Mapped[Optional["Satellite"]] = relationship(
        foreign_keys=[satellite_a_id], lazy="selectin"
    )
    satellite_b: Mapped[Optional["Satellite"]] = relationship(
        foreign_keys=[satellite_b_id], lazy="selectin"
    )


class Alert(Base):
    """
    Legacy Alert table maintained for backward compatibility.
    """
    __tablename__ = 'alerts'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conjunction_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('conjunction_events.id', ondelete='CASCADE'), nullable=False
    )
    satellite_a_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('satellites.id', ondelete='CASCADE'), nullable=False
    )
    satellite_b_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey('satellites.id', ondelete='CASCADE'), nullable=True
    )
    miss_distance: Mapped[float] = mapped_column(Float, nullable=False)
    relative_velocity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_of_closest_approach: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
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
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    conjunction_event: Mapped["ConjunctionEvent"] = relationship(lazy="selectin")
    satellite_a: Mapped["Satellite"] = relationship(
        foreign_keys=[satellite_a_id], lazy="selectin"
    )
    satellite_b: Mapped[Optional["Satellite"]] = relationship(
        foreign_keys=[satellite_b_id], lazy="selectin"
    )
    history: Mapped[List["AlertHistory"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan", lazy="selectin"
    )


class AlertHistory(Base):
    __tablename__ = 'alert_history'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('alerts.id', ondelete='CASCADE'), nullable=False
    )
    risk_level: Mapped[str] = mapped_column(
        ENUM(RiskLevel, name="risk_level", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    miss_distance: Mapped[float] = mapped_column(Float, nullable=False)
    relative_velocity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    alert: Mapped["Alert"] = relationship(back_populates="history")
