from sqlalchemy import Column, String, Float, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone

from app.db.session import Base

class ConjunctionEvent(Base):
    __tablename__ = 'conjunction_events'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    primary_satellite = Column(String, nullable=False)
    primary_norad_id = Column(Integer, nullable=False)
    secondary_object = Column(String, nullable=False)
    secondary_norad_id = Column(Integer, nullable=False)
    tca = Column(DateTime(timezone=True), nullable=False)
    miss_distance_m = Column(Float, nullable=False)
    probability = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    status = Column(String, default="open")
    detected_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
