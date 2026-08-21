from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.models.satellites import Satellite
from app.models.alerts import Alert

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc)

    sat_count_result = await db.execute(select(func.count(Satellite.id)))
    sat_count = sat_count_result.scalar() or 0

    active_alerts_result = await db.execute(select(func.count(Alert.id)).where(Alert.status == 'active'))
    active_alerts = active_alerts_result.scalar() or 0

    high_risk_alerts_result = await db.execute(select(func.count(Alert.id)).where(Alert.risk_level.in_(['high', 'critical'])))
    high_risk_alerts = high_risk_alerts_result.scalar() or 0

    next_alert_result = await db.execute(
        select(Alert).options(selectinload(Alert.conjunction_event)).order_by(
            Alert.time_of_closest_approach.asc()).limit(1)
    )
    next_alert = next_alert_result.scalar_one_or_none()

    next_conjunction = None
    if next_alert and next_alert.conjunction_event:
        next_conjunction = {
            "primarySatellite": next_alert.conjunction_event.primary_satellite,
            "secondaryObject": next_alert.conjunction_event.secondary_object,
            "tca": next_alert.time_of_closest_approach.isoformat(),
            "riskLevel": next_alert.risk_level,
            "missDistanceM": next_alert.miss_distance
        }

    return {
        "tracked_satellites": sat_count,
        "active_alerts": active_alerts,
        "high_risk_alerts": high_risk_alerts,
        "next_conjunction": next_conjunction,
        "altitude_trend": [
            {"time": (now - timedelta(hours=i)).isoformat(), "altitude": 400.0 + i*0.1} for i in range(24, -1, -1)
        ]
    }
