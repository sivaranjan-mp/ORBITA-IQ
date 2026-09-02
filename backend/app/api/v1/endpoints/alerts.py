from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.schemas.alerts import ConjunctionAlertResponse, AlertStatusUpdate
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _format_alert(alert) -> dict:
    return {
        "id": str(alert.id),
        "primarySatellite": alert.conjunction_event.primary_satellite if alert.conjunction_event else "Unknown",
        "primaryNoradId": alert.conjunction_event.primary_norad_id if alert.conjunction_event else 0,
        "secondaryObject": alert.conjunction_event.secondary_object if alert.conjunction_event else "Unknown",
        "secondaryNoradId": alert.conjunction_event.secondary_norad_id if alert.conjunction_event else 0,
        "tca": alert.time_of_closest_approach,
        "missDistanceM": alert.miss_distance,
        "probability": alert.conjunction_event.probability if alert.conjunction_event else 0.0,
        "riskLevel": alert.risk_level,
        "status": alert.status,
        "detectedBy": alert.conjunction_event.detected_by if alert.conjunction_event else "Unknown",
        "createdAt": alert.created_at,
    }


@router.get("", response_model=List[ConjunctionAlertResponse])
async def get_alerts(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = AlertService(db)
    alerts = await service.get_all_alerts()
    return [_format_alert(a) for a in alerts]


@router.put("/{alert_id}/status", response_model=ConjunctionAlertResponse)
async def update_alert_status(
    alert_id: str,
    update: AlertStatusUpdate,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if update.status not in ["active", "acknowledged", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    service = AlertService(db)
    alert = await service.update_alert_status(alert_id, update.status)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return _format_alert(alert)


@router.post("/seed", response_model=List[ConjunctionAlertResponse])
async def seed_mock_alerts(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    settings = get_settings()
    if settings.environment != "development":
        raise HTTPException(
            status_code=403, detail="Mock data is only available in development mode")

    from app.services.conjunction_service import ConjunctionService
    from app.models.alerts import Alert
    from app.models.satellites import Satellite
    from app.models.enums import SatelliteStatus
    from sqlalchemy import delete
    from sqlalchemy.future import select

    now = datetime.now(timezone.utc)
    def hours(h): return (now + timedelta(hours=h))

    mock_events = [
        {
            "primary_satellite": "ISS (ZARYA)",
            "primary_norad_id": 25544,
            "secondary_object": "COSMOS 2251 DEB",
            "secondary_norad_id": 33591,
            "tca": hours(6.2),
            "miss_distance_m": 340,
            "probability": 0.00042,
            "risk_level": "critical",
            "status": "open",
            "detected_by": "satguard"
        },
        {
            "primary_satellite": "STARLINK-3011",
            "primary_norad_id": 48274,
            "secondary_object": "FENGYUN 1C DEB",
            "secondary_norad_id": 29657,
            "tca": hours(14.8),
            "miss_distance_m": 1120,
            "probability": 0.000037,
            "risk_level": "high",
            "status": "monitoring",
            "detected_by": "satguard"
        },
        {
            "primary_satellite": "NOAA-20",
            "primary_norad_id": 43013,
            "secondary_object": "SL-16 R/B",
            "secondary_norad_id": 22285,
            "tca": hours(28.4),
            "miss_distance_m": 2870,
            "probability": 0.0000041,
            "risk_level": "medium",
            "status": "monitoring",
            "detected_by": "cdm_upload"
        }
    ]

    c_service = ConjunctionService(db)
    events = await c_service.seed_mock_alerts(mock_events)

    await db.execute(delete(Alert))

    for ev in events:
        sat_stmt = select(Satellite).where(Satellite.norad_id == ev.primary_norad_id)
        sat = (await db.execute(sat_stmt)).scalars().first()
        if not sat:
            sat = Satellite(
                norad_id=ev.primary_norad_id,
                name=ev.primary_satellite,
                status=SatelliteStatus.ACTIVE,
                owner_org=current_user.employee_id
            )
            db.add(sat)
            await db.flush()

        alert = Alert(
            conjunction_event_id=ev.id,
            satellite_a_id=sat.id,
            miss_distance=ev.miss_distance_m,
            time_of_closest_approach=ev.tca,
            risk_level=ev.risk_level,
            status="active"
        )
        db.add(alert)

    await db.commit()

    service = AlertService(db)
    alerts_created = await service.get_all_alerts()

    return [_format_alert(a) for a in alerts_created]
