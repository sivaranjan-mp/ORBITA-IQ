from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.alerts import Alert, ConjunctionAlert
from app.models.enums import AlertState, ConjunctionStatus, RiskLevel
from app.models.satellites import Satellite
from app.schemas.auth import UserProfile

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # 1. Total Tracked Satellites
    sat_count_result = await db.execute(select(func.count(Satellite.id)))
    sat_count = sat_count_result.scalar() or 0

    # 2. Check if we have conjunction_alerts
    conj_count_res = await db.execute(select(func.count(ConjunctionAlert.id)))
    has_conj_alerts = (conj_count_res.scalar() or 0) > 0

    if has_conj_alerts:
        active_statuses = ["open", "monitoring"]

        # Active Alerts (Open + Monitoring)
        active_alerts_result = await db.execute(
            select(func.count(ConjunctionAlert.id)).where(
                ConjunctionAlert.status.in_(active_statuses),
                ConjunctionAlert.tca >= now,
            )
        )
        active_alerts = active_alerts_result.scalar() or 0

        # High Risk Alerts (High + Critical)
        high_risk_alerts_result = await db.execute(
            select(func.count(ConjunctionAlert.id)).where(
                ConjunctionAlert.status.in_(active_statuses),
                ConjunctionAlert.risk_level.in_(["high", "critical"]),
                ConjunctionAlert.tca >= now,
            )
        )
        high_risk_alerts = high_risk_alerts_result.scalar() or 0

        # Next Conjunction
        next_alert_result = await db.execute(
            select(ConjunctionAlert)
            .where(
                ConjunctionAlert.status.in_(active_statuses),
                ConjunctionAlert.tca >= now,
            )
            .order_by(ConjunctionAlert.tca.asc())
            .limit(1)
        )
        next_alert = next_alert_result.scalar_one_or_none()

        next_conjunction = None
        if next_alert:
            next_conjunction = {
                "id": str(next_alert.id),
                "primarySatellite": next_alert.satellite_a_name,
                "primaryNoradId": next_alert.satellite_a_norad_id,
                "secondaryObject": next_alert.satellite_b_name,
                "secondaryNoradId": next_alert.satellite_b_norad_id,
                "tca": next_alert.tca.isoformat(),
                "riskLevel": next_alert.risk_level,
                "missDistanceM": next_alert.miss_distance_m,
                "missDistanceKm": next_alert.miss_distance_km,
                "relativeVelocityKmS": next_alert.relative_velocity_km_s,
                "probability": next_alert.probability,
                "screeningScope": next_alert.screening_scope,
            }
    else:
        # Fallback to legacy Alert table
        active_alerts_result = await db.execute(
            select(func.count(Alert.id)).where(
                Alert.status == AlertState.ACTIVE,
                Alert.time_of_closest_approach >= now,
            )
        )
        active_alerts = active_alerts_result.scalar() or 0

        high_risk_alerts_result = await db.execute(
            select(func.count(Alert.id)).where(
                Alert.status == AlertState.ACTIVE,
                Alert.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL]),
                Alert.time_of_closest_approach >= now,
            )
        )
        high_risk_alerts = high_risk_alerts_result.scalar() or 0

        next_alert_result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.conjunction_event), selectinload(Alert.satellite_a), selectinload(Alert.satellite_b))
            .where(
                Alert.status == AlertState.ACTIVE,
                Alert.time_of_closest_approach >= now,
            )
            .order_by(Alert.time_of_closest_approach.asc())
            .limit(1)
        )
        next_alert = next_alert_result.scalar_one_or_none()

        next_conjunction = None
        if next_alert:
            prim_name = next_alert.conjunction_event.primary_satellite if next_alert.conjunction_event else (next_alert.satellite_a.name if next_alert.satellite_a else "Unknown")
            sec_name = next_alert.conjunction_event.secondary_object if next_alert.conjunction_event else (next_alert.satellite_b.name if next_alert.satellite_b else "Unknown")
            next_conjunction = {
                "id": str(next_alert.id),
                "primarySatellite": prim_name,
                "secondaryObject": sec_name,
                "tca": next_alert.time_of_closest_approach.isoformat(),
                "riskLevel": next_alert.risk_level,
                "missDistanceM": next_alert.miss_distance,
            }

    return {
        "tracked_satellites": sat_count,
        "active_alerts": active_alerts,
        "high_risk_alerts": high_risk_alerts,
        "next_conjunction": next_conjunction,
        "altitude_trend": [],
    }
