from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from datetime import datetime, timezone

from app.models.conjunctions import ConjunctionEvent
from app.schemas.alerts import AlertStatusUpdate

class ConjunctionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_alerts(self):
        result = await self.db.execute(select(ConjunctionEvent).order_by(ConjunctionEvent.tca.desc()))
        return result.scalars().all()

    async def update_alert_status(self, alert_id: str, status: str):
        stmt = update(ConjunctionEvent).where(ConjunctionEvent.id == alert_id).values(status=status)
        await self.db.execute(stmt)
        await self.db.commit()
        
        result = await self.db.execute(select(ConjunctionEvent).where(ConjunctionEvent.id == alert_id))
        return result.scalars().first()

    async def seed_mock_alerts(self, mock_alerts: list):
        # Delete existing
        await self.db.execute(delete(ConjunctionEvent))
        
        # Insert new
        events = [ConjunctionEvent(**alert) for alert in mock_alerts]
        self.db.add_all(events)
        await self.db.commit()
        
        # Return inserted
        result = await self.db.execute(select(ConjunctionEvent).order_by(ConjunctionEvent.tca.desc()))
        return result.scalars().all()
