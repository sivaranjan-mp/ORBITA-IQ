from sqlalchemy import Integer, String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from typing import Optional

from app.db.session import Base


class CatalogSatellite(Base):
    __tablename__ = 'catalog_satellites'

    norad_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    international_designator: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    object_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, default="payload")
    orbit_regime: Mapped[Optional[str]] = mapped_column(String, nullable=True, default="LEO", index=True)
    apogee_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    perigee_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    inclination_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    period_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eccentricity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    line1: Mapped[str] = mapped_column(String, nullable=False)
    line2: Mapped[str] = mapped_column(String, nullable=False)
    epoch: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
