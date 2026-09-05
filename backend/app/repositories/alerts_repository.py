from typing import List, Optional, Tuple
import uuid
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload

from app.models.alerts import Alert, AlertHistory, AlertStatusHistory, ConjunctionAlert


class AlertsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_conjunction_alerts(self) -> List[ConjunctionAlert]:
        stmt = select(ConjunctionAlert).options(
            selectinload(ConjunctionAlert.satellite_a),
            selectinload(ConjunctionAlert.satellite_b),
        ).order_by(ConjunctionAlert.tca.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_conjunction_alert_by_id(self, alert_id: str) -> Optional[ConjunctionAlert]:
        stmt = select(ConjunctionAlert).where(ConjunctionAlert.id == alert_id).options(
            selectinload(ConjunctionAlert.satellite_a),
            selectinload(ConjunctionAlert.satellite_b),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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

    async def add_status_history(self, history: AlertStatusHistory) -> AlertStatusHistory:
        self.session.add(history)
        await self.session.commit()
        await self.session.refresh(history)
        return history

    async def get_alert_status_history(
        self,
        page: int = 1,
        limit: int = 20,
        alert_id: Optional[str] = None
    ) -> Tuple[List[AlertStatusHistory], int]:
        stmt = select(AlertStatusHistory).options(
            joinedload(AlertStatusHistory.alert)
        )
        count_stmt = select(func.count()).select_from(AlertStatusHistory)

        if alert_id:
            try:
                alert_uuid = uuid.UUID(str(alert_id))
                stmt = stmt.where(AlertStatusHistory.alert_id == alert_uuid)
                count_stmt = count_stmt.where(AlertStatusHistory.alert_id == alert_uuid)
            except (ValueError, TypeError):
                pass

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one() or 0

        offset = max(0, (page - 1) * limit)
        stmt = stmt.order_by(AlertStatusHistory.changed_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        items = result.scalars().all()

        return list(items), total

