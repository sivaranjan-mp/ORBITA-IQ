from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.models.conjunctions import ConjunctionEvent
from app.services.satguard_service import SatguardService

router = APIRouter(prefix="/conjunctions", tags=["conjunctions"])


def _format_conjunction(event: ConjunctionEvent) -> dict:
    return {
        "id": str(event.id),
        "primarySatelliteId": str(event.primary_satellite_id),
        "primarySatelliteName": event.primary_satellite.name if event.primary_satellite else "Unknown",
        "primaryNoradId": event.primary_satellite.norad_id if event.primary_satellite else 0,
        "secondarySatelliteId": str(event.secondary_satellite_id),
        "secondarySatelliteName": event.secondary_satellite.name if event.secondary_satellite else "Unknown",
        "secondaryNoradId": event.secondary_satellite.norad_id if event.secondary_satellite else 0,
        "tca": event.tca,
        "missDistanceKm": event.miss_distance_m / 1000.0,
        "relativeVelocityKmS": event.relative_velocity_km_s,
        "probability": event.probability,
        "riskLevel": event.risk_level,
        "status": event.status,
        "detectedBy": event.detected_by,
        "createdAt": event.created_at
    }


@router.get("")
async def get_conjunctions(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ConjunctionEvent).options(
        selectinload(ConjunctionEvent.primary_satellite),
        selectinload(ConjunctionEvent.secondary_satellite)
    ).order_by(ConjunctionEvent.tca.asc())

    result = await db.execute(stmt)
    events = result.scalars().all()

    return [_format_conjunction(e) for e in events]


@router.post("/screen")
async def manual_screen(
    background_tasks: BackgroundTasks,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Enforce admin only
    if getattr(current_user, 'role', '') != 'admin':
        raise HTTPException(
            status_code=403, detail="Admin role required for manual screening")

    # We run it synchronously to return the count, since it's an admin endpoint
    # and they probably want to see the result immediately.
    # For large datasets, this should be sent to background_tasks.
    service = SatguardService(db)
    events_created = await service.screen_all(lookahead_hours=72, step_size_s=60, miss_dist_threshold_km=5.0)

    return {"message": "Screening complete", "events_created": events_created}
