from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timezone

from app.models.alerts import Alert, AlertHistory
from app.repositories.alerts_repository import AlertsRepository

class AlertService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AlertsRepository(session)

    async def get_all_alerts(self) -> List[Alert]:
        return await self.repository.get_all_alerts()

    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        return await self.repository.get_alert_by_id(alert_id)

    async def update_alert_status(self, alert_id: str, new_status: str) -> Optional[Alert]:
        alert = await self.repository.get_alert_by_id(alert_id)
        if not alert:
            return None

        # Add history entry
        history = AlertHistory(
            alert_id=alert.id,
            risk_level=alert.risk_level,
            miss_distance=alert.miss_distance,
            relative_velocity=alert.relative_velocity,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Update the alert itself
        alert.status = new_status
        
        # Add the history to the session (Alert update cascades or we just add it)
        self.session.add(history)
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        
        return alert
