from sqlalchemy import String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
from datetime import datetime, timezone

from app.db.session import Base
from app.models.enums import RiskLevel, ConjunctionStatus
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.satellites import Satellite


class ConjunctionEvent(Base):
    __tablename__ = 'conjunction_events'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    primary_satellite: Mapped[str] = mapped_column(String, nullable=False)
    primary_norad_id: Mapped[int] = mapped_column(nullable=False)
    secondary_object: Mapped[str] = mapped_column(String, nullable=False)
    secondary_norad_id: Mapped[int] = mapped_column(nullable=False)
    tca: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    miss_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    relative_velocity_km_s: Mapped[Optional[float]
                                   ] = mapped_column(Float, nullable=True)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(
        ENUM(RiskLevel, name="risk_level", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    status: Mapped[Optional[str]] = mapped_column(
        ENUM(ConjunctionStatus, name="alert_status", create_type=False, values_callable=lambda x: [e.value for e in x]),
        default="open"
    )
    detected_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
