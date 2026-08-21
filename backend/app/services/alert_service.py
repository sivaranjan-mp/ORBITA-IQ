from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime, timezone

from app.models.alerts import Alert, AlertHistory
from app.models.conjunctions import ConjunctionEvent
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

    async def create_alert_from_conjunction(self, event: ConjunctionEvent) -> Alert:
        # Check if an alert already exists for this conjunction event
        existing = await self.session.execute(
            select(Alert).where(Alert.conjunction_event_id == event.id)
        )
        alert = existing.scalars().first()

        if alert:
            # Update the existing alert if the new risk level is higher or it's just an update
            # Normally we might update distance and velocity, but for now we just update risk
            alert.risk_level = event.risk_level
            alert.miss_distance = event.miss_distance_m
            alert.relative_velocity = event.relative_velocity_km_s
            alert.time_of_closest_approach = event.tca
            # Add history
            history = AlertHistory(
                alert_id=alert.id,
                risk_level=alert.risk_level,
                miss_distance=alert.miss_distance,
                relative_velocity=alert.relative_velocity,
                timestamp=datetime.now(timezone.utc)
            )
            self.session.add(history)
            self.session.add(alert)
        else:
            # Create a new alert
            alert = Alert(
                conjunction_event_id=event.id,
                satellite_a_id=event.primary_satellite_id,
                satellite_b_id=event.secondary_satellite_id,
                miss_distance=event.miss_distance_m,
                relative_velocity=event.relative_velocity_km_s,
                time_of_closest_approach=event.tca,
                risk_level=event.risk_level,
                status='active'
            )
            self.session.add(alert)
            # Flush to get alert.id for history
            await self.session.flush()
            
            history = AlertHistory(
                alert_id=alert.id,
                risk_level=alert.risk_level,
                miss_distance=alert.miss_distance,
                relative_velocity=alert.relative_velocity,
                timestamp=datetime.now(timezone.utc)
            )
            self.session.add(history)

        await self.session.commit()
        await self.session.refresh(alert)
        return alert
