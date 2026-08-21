from sqlalchemy import String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
from datetime import datetime, timezone

from app.db.session import Base
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.satellites import Satellite


class ConjunctionEvent(Base):
    __tablename__ = 'conjunction_events'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    primary_satellite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('satellites.id', ondelete='CASCADE'), nullable=False)
    secondary_satellite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('satellites.id', ondelete='CASCADE'), nullable=False)
    tca: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    miss_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    relative_velocity_km_s: Mapped[Optional[float]
                                   ] = mapped_column(Float, nullable=True)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[Optional[str]] = mapped_column(
        String, default="open")  # was just default="open" originally
    detected_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    primary_satellite: Mapped["Satellite"] = relationship(
        foreign_keys=[primary_satellite_id])
    secondary_satellite: Mapped["Satellite"] = relationship(
        foreign_keys=[secondary_satellite_id])
