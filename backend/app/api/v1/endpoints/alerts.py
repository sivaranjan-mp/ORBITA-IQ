import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import DEFAULT_LOOKAHEAD_HOURS
from app.core.supabase_client import get_admin_client
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.alerts import Alert, AlertStatusHistory, ConjunctionAlert
from app.models.enums import SatelliteStatus
from app.models.satellites import Satellite, TLERecord
from app.schemas.alerts import (
    AlertStatusHistoryListResponse,
    AlertStatusHistoryResponse,
    AlertStatusUpdate,
    ConjunctionAlertResponse,
    ScreeningRunResponse,
)
from app.schemas.auth import UserProfile
from app.services.alert_service import AlertService
from app.services.satguard_service import SatguardService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])

_PROFILES_LOOKUP_CACHE: dict[str, dict] = {}
_PROFILES_LOOKUP_TIMESTAMP: float = 0.0
_PROFILES_LOOKUP_TTL: float = 60.0  # seconds


def _get_profiles_lookup() -> dict[str, dict]:
    global _PROFILES_LOOKUP_CACHE, _PROFILES_LOOKUP_TIMESTAMP
    now = time.time()
    if _PROFILES_LOOKUP_CACHE and (now - _PROFILES_LOOKUP_TIMESTAMP) < _PROFILES_LOOKUP_TTL:
        return _PROFILES_LOOKUP_CACHE

    try:
        admin = get_admin_client()
        result = admin.table("profiles").select("id, employee_id, full_name, role").execute()
        if result and result.data:
            lookup = {}
            for p in result.data:
                if p.get("id"):
                    lookup[str(p["id"])] = p
                if p.get("employee_id"):
                    lookup[str(p["employee_id"]).strip().upper()] = p
            _PROFILES_LOOKUP_CACHE = lookup
            _PROFILES_LOOKUP_TIMESTAMP = now
            return _PROFILES_LOOKUP_CACHE
    except Exception as exc:
        logger.warning(f"Could not load operator profiles from Supabase: {exc}")
    return _PROFILES_LOOKUP_CACHE or {}


def _format_history_item(
    h: AlertStatusHistory,
    profiles_lookup: dict,
    current_user: Optional[UserProfile] = None
) -> AlertStatusHistoryResponse:
    alert = h.alert
    changed_by_str = str(h.changed_by) if h.changed_by else None
    operator_name = "Automated System"

    if changed_by_str and changed_by_str in profiles_lookup:
        profile = profiles_lookup[changed_by_str]
        operator_name = profile.get("full_name") or profile.get("employee_id") or "Operator"
    elif current_user and changed_by_str == current_user.id:
        operator_name = current_user.full_name or current_user.employee_id
    elif changed_by_str:
        operator_name = f"Operator ({changed_by_str[:8]})"

    action_label = h.new_status.capitalize() if h.new_status else "Updated"

    return AlertStatusHistoryResponse(
        id=str(h.id),
        alertId=str(h.alert_id),
        primarySatellite=alert.satellite_a_name if alert else "Unknown",
        primaryNoradId=alert.satellite_a_norad_id if alert else 0,
        secondaryObject=alert.satellite_b_name if alert else "Unknown",
        secondaryNoradId=alert.satellite_b_norad_id if alert else 0,
        riskLevel=alert.risk_level if alert else "low",
        previousStatus=h.previous_status,
        newStatus=h.new_status,
        actionTaken=action_label,
        changedBy=changed_by_str,
        operatorName=operator_name,
        changedAt=h.changed_at,
        notes=h.notes,
    )


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


@router.get("/history", response_model=AlertStatusHistoryListResponse)
async def get_alert_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    alert_id: Optional[str] = Query(None, description="Filter by conjunction alert ID"),
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AlertService(db)
    items, total = await service.get_alert_history(page=page, limit=limit, alert_id=alert_id)

    profiles_lookup = _get_profiles_lookup()
    formatted = [
        _format_history_item(h, profiles_lookup, current_user)
        for h in items
    ]

    total_pages = max(1, (total + limit - 1) // limit) if total > 0 else 1

    return AlertStatusHistoryListResponse(
        items=formatted,
        total=total,
        page=page,
        limit=limit,
        totalPages=total_pages,
    )


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
    alert = await service.update_alert_status(
        alert_id=alert_id,
        new_status=update.status.lower(),
        changed_by=current_user.id,
        notes=update.notes,
    )

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

