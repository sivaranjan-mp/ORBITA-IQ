import logging
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import DEFAULT_LOOKAHEAD_HOURS
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.alerts import Alert, ConjunctionAlert
from app.models.enums import SatelliteStatus
from app.models.satellites import Satellite, TLERecord
from app.schemas.alerts import (
    AlertStatusUpdate,
    ConjunctionAlertResponse,
    ScreeningRunResponse,
)
from app.schemas.auth import UserProfile
from app.services.alert_service import AlertService
from app.services.satguard_service import SatguardService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _format_alert(alert) -> dict:
    if isinstance(alert, ConjunctionAlert):
        return {
            "id": str(alert.id),
            "primarySatellite": alert.satellite_a_name,
            "primaryNoradId": alert.satellite_a_norad_id,
            "secondaryObject": alert.satellite_b_name,
            "secondaryNoradId": alert.satellite_b_norad_id,
            "tca": alert.tca,
            "missDistanceM": alert.miss_distance_m,
            "missDistanceKm": alert.miss_distance_km,
            "relativeVelocityKmS": alert.relative_velocity_km_s,
            "probability": alert.probability,
            "riskLevel": alert.risk_level,
            "status": alert.status,
            "screeningScope": alert.screening_scope,
            "detectedBy": alert.detected_by,
            "createdAt": alert.created_at,
            "computedAt": alert.computed_at,
        }
    else:
        return {
            "id": str(alert.id),
            "primarySatellite": alert.conjunction_event.primary_satellite if getattr(alert, "conjunction_event", None) else (alert.satellite_a.name if getattr(alert, "satellite_a", None) else "Unknown"),
            "primaryNoradId": alert.conjunction_event.primary_norad_id if getattr(alert, "conjunction_event", None) else (alert.satellite_a.norad_id if getattr(alert, "satellite_a", None) else 0),
            "secondaryObject": alert.conjunction_event.secondary_object if getattr(alert, "conjunction_event", None) else (alert.satellite_b.name if getattr(alert, "satellite_b", None) else "Unknown"),
            "secondaryNoradId": alert.conjunction_event.secondary_norad_id if getattr(alert, "conjunction_event", None) else (alert.satellite_b.norad_id if getattr(alert, "satellite_b", None) else 0),
            "tca": alert.time_of_closest_approach,
            "missDistanceM": alert.miss_distance,
            "missDistanceKm": alert.miss_distance / 1000.0,
            "relativeVelocityKmS": alert.relative_velocity,
            "probability": alert.conjunction_event.probability if getattr(alert, "conjunction_event", None) else 0.0,
            "riskLevel": alert.risk_level,
            "status": alert.status,
            "screeningScope": "fleet_vs_catalog",
            "detectedBy": alert.conjunction_event.detected_by if getattr(alert, "conjunction_event", None) else "satguard",
            "createdAt": alert.created_at,
            "computedAt": alert.created_at,
        }


@router.get("", response_model=List[ConjunctionAlertResponse])
async def get_alerts(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AlertService(db)
    alerts = await service.get_all_alerts()
    return [_format_alert(a) for a in alerts]


@router.put("/{alert_id}/status", response_model=ConjunctionAlertResponse)
async def update_alert_status(
    alert_id: str,
    update: AlertStatusUpdate,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid_statuses = ["active", "acknowledged", "open", "monitoring", "resolved", "dismissed"]
    if update.status.lower() not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{update.status}'. Allowed: {', '.join(valid_statuses)}",
        )

    service = AlertService(db)
    alert = await service.update_alert_status(alert_id, update.status.lower())

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return _format_alert(alert)


@router.post("/screen", response_model=ScreeningRunResponse)
async def trigger_screening(
    lookahead_hours: float = Query(DEFAULT_LOOKAHEAD_HOURS, description="Screening lookahead window in hours"),
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    service = SatguardService(db)
    metrics = await service.screen_all(lookahead_hours=lookahead_hours)

    return ScreeningRunResponse(
        message="5-day conjunction assessment screening completed successfully.",
        eventsCreated=metrics.get("events_created", 0),
        totalDetected=metrics.get("total_detected", 0),
        stage1Survivors=metrics.get("stage1_survivors", 0),
        durationSeconds=metrics.get("duration_seconds", 0.0),
    )


@router.post("/seed-synthetic", response_model=List[ConjunctionAlertResponse])
async def seed_synthetic_conjunction(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Seeds a test pair of objects (e.g. STARLETTE vs synthetic companion) with known
    close approach inside the 5-day window for pipeline validation.
    """
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    now = datetime.now(timezone.utc)
    tca_test = now + timedelta(hours=18.5)

    alert = ConjunctionAlert(
        satellite_a_norad_id=25544,
        satellite_a_name="ISS (ZARYA)",
        satellite_b_norad_id=99001,
        satellite_b_name="SYNTHETIC-DEB-ALPHA",
        screening_scope="fleet_vs_catalog",
        tca=tca_test,
        miss_distance_km=0.42,
        miss_distance_m=420.0,
        relative_velocity_km_s=11.4,
        probability=0.00045,
        risk_level="critical",
        status="open",
        detected_by="satguard_synthetic_test",
        computed_at=now,
    )
    db.add(alert)
    await db.commit()

    service = AlertService(db)
    alerts = await service.get_all_alerts()
    return [_format_alert(a) for a in alerts]


@router.post("/seed", response_model=List[ConjunctionAlertResponse])
async def seed_mock_alerts(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    settings = get_settings()
    if settings.environment != "development":
        raise HTTPException(
            status_code=403, detail="Mock data is only available in development mode"
        )

    now = datetime.now(timezone.utc)
    def hours(h): return (now + timedelta(hours=h))

    mock_alerts = [
        ConjunctionAlert(
            satellite_a_norad_id=25544,
            satellite_a_name="ISS (ZARYA)",
            satellite_b_norad_id=33591,
            satellite_b_name="COSMOS 2251 DEB",
            screening_scope="fleet_vs_catalog",
            tca=hours(6.2),
            miss_distance_km=0.34,
            miss_distance_m=340.0,
            relative_velocity_km_s=14.2,
            probability=0.00042,
            risk_level="critical",
            status="open",
            detected_by="satguard",
            computed_at=now,
        ),
        ConjunctionAlert(
            satellite_a_norad_id=48274,
            satellite_a_name="STARLINK-3011",
            satellite_b_norad_id=29657,
            satellite_b_name="FENGYUN 1C DEB",
            screening_scope="fleet_vs_catalog",
            tca=hours(14.8),
            miss_distance_km=1.12,
            miss_distance_m=1120.0,
            relative_velocity_km_s=12.8,
            probability=0.000037,
            risk_level="high",
            status="monitoring",
            detected_by="satguard",
            computed_at=now,
        ),
        ConjunctionAlert(
            satellite_a_norad_id=43013,
            satellite_a_name="NOAA-20",
            satellite_b_norad_id=22285,
            satellite_b_name="SL-16 R/B",
            screening_scope="fleet_vs_catalog",
            tca=hours(28.4),
            miss_distance_km=2.87,
            miss_distance_m=2870.0,
            relative_velocity_km_s=9.6,
            probability=0.0000041,
            risk_level="medium",
            status="monitoring",
            detected_by="cdm_upload",
            computed_at=now,
        ),
        ConjunctionAlert(
            satellite_a_norad_id=25544,
            satellite_a_name="ISS (ZARYA)",
            satellite_b_norad_id=48274,
            satellite_b_name="TIANGONG",
            screening_scope="fleet_vs_fleet",
            tca=hours(82.1),
            miss_distance_km=32.4,
            miss_distance_m=32400.0,
            relative_velocity_km_s=7.5,
            probability=0.0000001,
            risk_level="low",
            status="open",
            detected_by="satguard",
            computed_at=now,
        ),
    ]

    await db.execute(delete(ConjunctionAlert))
    for alert in mock_alerts:
        db.add(alert)

    await db.commit()

    service = AlertService(db)
    alerts = await service.get_all_alerts()
    return [_format_alert(a) for a in alerts]


@router.post("/seed-simulated", response_model=List[ConjunctionAlertResponse])
async def seed_simulated_fleet_alerts(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Seeds simulated collision alerts for 15-23 satellites with collision dates
    between 7 and 14 days, and risk levels medium and low.
    """
    await db.execute(delete(ConjunctionAlert))
    await db.commit()

    service = AlertService(db)
    created = await service.seed_simulated_alerts()
    return [_format_alert(a) for a in created]

