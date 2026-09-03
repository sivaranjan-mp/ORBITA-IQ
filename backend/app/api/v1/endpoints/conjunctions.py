from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.constants import DEFAULT_LOOKAHEAD_HOURS
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.alerts import ConjunctionAlert
from app.models.conjunctions import ConjunctionEvent
from app.schemas.auth import UserProfile
from app.services.satguard_service import SatguardService

router = APIRouter(prefix="/conjunctions", tags=["conjunctions"])


def _format_conjunction_alert(event: ConjunctionAlert) -> dict:
    return {
        "id": str(event.id),
        "primarySatelliteId": str(event.satellite_a_id) if event.satellite_a_id else "unknown",
        "primarySatelliteName": event.satellite_a_name,
        "primaryNoradId": event.satellite_a_norad_id,
        "secondarySatelliteId": str(event.satellite_b_id) if event.satellite_b_id else "unknown",
        "secondarySatelliteName": event.satellite_b_name,
        "secondaryNoradId": event.satellite_b_norad_id,
        "tca": event.tca,
        "missDistanceKm": event.miss_distance_km,
        "relativeVelocityKmS": event.relative_velocity_km_s,
        "probability": event.probability,
        "riskLevel": event.risk_level,
        "status": event.status,
        "screeningScope": event.screening_scope,
        "detectedBy": event.detected_by,
        "createdAt": event.created_at,
    }


def _format_legacy_conjunction(event: ConjunctionEvent) -> dict:
    return {
        "id": str(event.id),
        "primarySatelliteId": "unknown",
        "primarySatelliteName": event.primary_satellite,
        "primaryNoradId": event.primary_norad_id,
        "secondarySatelliteId": "unknown",
        "secondarySatelliteName": event.secondary_object,
        "secondaryNoradId": event.secondary_norad_id,
        "tca": event.tca,
        "missDistanceKm": event.miss_distance_m / 1000.0,
        "relativeVelocityKmS": event.relative_velocity_km_s,
        "probability": event.probability,
        "riskLevel": event.risk_level,
        "status": event.status,
        "screeningScope": "fleet_vs_catalog",
        "detectedBy": event.detected_by,
        "createdAt": event.created_at,
    }


@router.get("")
async def get_conjunctions(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ConjunctionAlert).order_by(ConjunctionAlert.tca.asc())
    result = await db.execute(stmt)
    events = result.scalars().all()

    if events:
        return [_format_conjunction_alert(e) for e in events]

    legacy_stmt = select(ConjunctionEvent).order_by(ConjunctionEvent.tca.asc())
    legacy_res = await db.execute(legacy_stmt)
    legacy_events = legacy_res.scalars().all()
    return [_format_legacy_conjunction(e) for e in legacy_events]


@router.post("/screen")
async def manual_screen(
    lookahead_hours: float = Query(DEFAULT_LOOKAHEAD_HOURS, description="Screening horizon in hours (default 120h/5d)"),
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(
            status_code=403, detail="Operator or admin role required for manual screening"
        )

    service = SatguardService(db)
    metrics = await service.screen_all(lookahead_hours=lookahead_hours)

    return {
        "message": "Screening complete",
        "events_created": metrics.get("events_created", 0),
        "total_detected": metrics.get("total_detected", 0),
        "stage1_survivors": metrics.get("stage1_survivors", 0),
        "duration_seconds": metrics.get("duration_seconds", 0.0),
    }
