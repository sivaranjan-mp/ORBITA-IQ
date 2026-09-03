from datetime import datetime, timezone
from typing import List, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.alerts import Alert, AlertHistory, ConjunctionAlert
from app.models.conjunctions import ConjunctionEvent
from app.repositories.alerts_repository import AlertsRepository


class AlertService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AlertsRepository(session)

    async def get_all_conjunction_alerts(self) -> List[ConjunctionAlert]:
        return await self.repository.get_all_conjunction_alerts()

    async def get_all_alerts(self) -> List[Union[ConjunctionAlert, Alert]]:
        try:
            alerts = await self.repository.get_all_conjunction_alerts()
            if alerts:
                return alerts
        except Exception:
            pass
        return await self.repository.get_all_alerts()

    async def get_alert(self, alert_id: str) -> Optional[Union[ConjunctionAlert, Alert]]:
        try:
            conj_alert = await self.repository.get_conjunction_alert_by_id(alert_id)
            if conj_alert:
                return conj_alert
        except Exception:
            pass
        return await self.repository.get_alert_by_id(alert_id)

    async def update_alert_status(self, alert_id: str, new_status: str) -> Optional[Union[ConjunctionAlert, Alert]]:
        alert = await self.get_alert(alert_id)
        if not alert:
            return None

        if isinstance(alert, ConjunctionAlert):
            alert.status = new_status
            alert.updated_at = datetime.now(timezone.utc)
            self.session.add(alert)
            await self.session.commit()
            await self.session.refresh(alert)
            return alert

        # Legacy Alert
        history = AlertHistory(
            alert_id=alert.id,
            risk_level=alert.risk_level,
            miss_distance=alert.miss_distance,
            relative_velocity=alert.relative_velocity,
            timestamp=datetime.now(timezone.utc)
        )

        alert.status = new_status
        self.session.add(history)
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)

        return alert

    async def create_alert_from_conjunction(self, event: ConjunctionEvent) -> Alert:
        existing = await self.session.execute(
            select(Alert).where(Alert.conjunction_event_id == event.id)
        )
        alert = existing.scalars().first()

        if alert:
            alert.risk_level = event.risk_level
            alert.miss_distance = event.miss_distance_m
            alert.relative_velocity = event.relative_velocity_km_s
            alert.time_of_closest_approach = event.tca

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
            from app.models.satellites import Satellite
            sat_a = (await self.session.execute(select(Satellite).where(Satellite.norad_id == event.primary_norad_id))).scalars().first()
            sat_b = (await self.session.execute(select(Satellite).where(Satellite.norad_id == event.secondary_norad_id))).scalars().first()

            if not sat_a:
                raise ValueError(f"Primary satellite with NORAD ID {event.primary_norad_id} not found")

            alert = Alert(
                conjunction_event_id=event.id,
                satellite_a_id=sat_a.id,
                satellite_b_id=sat_b.id if sat_b else None,
                miss_distance=event.miss_distance_m,
                relative_velocity=event.relative_velocity_km_s,
                time_of_closest_approach=event.tca,
                risk_level=event.risk_level,
                status='active'
            )
            self.session.add(alert)
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
