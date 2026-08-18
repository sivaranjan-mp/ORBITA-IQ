from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
import uuid

from app.models.alerts import Alert, AlertHistory

class AlertsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_alerts(self) -> List[Alert]:
        stmt = select(Alert).options(
            selectinload(Alert.conjunction_event),
            selectinload(Alert.satellite_a),
            selectinload(Alert.satellite_b),
            selectinload(Alert.history)
        ).order_by(Alert.time_of_closest_approach.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_alert_by_id(self, alert_id: str) -> Optional[Alert]:
        stmt = select(Alert).where(Alert.id == alert_id).options(
            selectinload(Alert.conjunction_event),
            selectinload(Alert.satellite_a),
            selectinload(Alert.satellite_b),
            selectinload(Alert.history)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_alert(self, alert: Alert) -> Alert:
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    async def add_history(self, history: AlertHistory) -> AlertHistory:
        self.session.add(history)
        await self.session.commit()
        await self.session.refresh(history)
        return history
