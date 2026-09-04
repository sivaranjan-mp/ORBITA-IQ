import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.alerts import ConjunctionAlert


class AIManeuverAdvisory(Base):
    """
    Cached qualitative LLM-generated maneuver advisory for an active conjunction alert.
    """
    __tablename__ = 'ai_maneuver_advisories'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('conjunction_alerts.id', ondelete='CASCADE'),
        unique=True,
        nullable=False,
        index=True
    )
    satellite_norad_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    recommendation_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_used: Mapped[str] = mapped_column(String, nullable=False, default="claude-3-5-haiku-20241022")
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    alert: Mapped[Optional["ConjunctionAlert"]] = relationship(
        "ConjunctionAlert", back_populates="ai_advisory", lazy="selectin"
    )
