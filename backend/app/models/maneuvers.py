import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ManeuverDirection, RiskLevel

if TYPE_CHECKING:
    from app.models.alerts import ConjunctionAlert


class ManeuverCandidate(Base):
    """
    Generated candidate collision-avoidance maneuver for a conjunction alert.
    Stores burn magnitude, direction in RTN frame, burn epoch, and resulting
    post-maneuver close approach metrics propagated via Two-Body + J2 numerical integration.
    """
    __tablename__ = 'maneuver_candidates'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('conjunction_alerts.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    direction: Mapped[str] = mapped_column(
        ENUM(
            ManeuverDirection,
            name="maneuver_direction",
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        index=True
    )

    delta_v_m_s: Mapped[float] = mapped_column(Float, nullable=False)
    delta_v_r_m_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delta_v_t_m_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delta_v_n_m_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    burn_epoch: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    time_before_tca_hours: Mapped[float] = mapped_column(Float, nullable=False)

    resulting_tca: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resulting_miss_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    resulting_miss_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    resulting_relative_velocity_km_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resulting_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    resulting_risk_level: Mapped[str] = mapped_column(
        ENUM(
            RiskLevel,
            name="risk_level",
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default="low"
    )

    miss_distance_improvement_m: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level_change: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    efficiency_m_per_m_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    fuel_cost_proxy_m_s: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    alert: Mapped[Optional["ConjunctionAlert"]] = relationship(
        "ConjunctionAlert", back_populates="maneuver_candidates", lazy="selectin"
    )
