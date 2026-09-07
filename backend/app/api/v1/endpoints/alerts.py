import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

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
from app.schemas.maneuvers import ManeuverGenerationRequest, ManeuverGenerationResponse
from app.services.alert_service import AlertService
from app.services.data_quality_service import DataQualityService
from app.services.maneuver_candidates import ManeuverCandidateService
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


from app.services.probability_engine import ProbabilityEngine

def _format_alert(alert) -> dict:
    if isinstance(alert, ConjunctionAlert):
        hbr_a, hbr_a_known = ProbabilityEngine.resolve_hbr(
            getattr(alert, "satellite_a", None), norad_id=getattr(alert, "satellite_a_norad_id", None)
        )
        hbr_b, hbr_b_known = ProbabilityEngine.resolve_hbr(
            getattr(alert, "satellite_b", None), norad_id=getattr(alert, "satellite_b_norad_id", None)
        )
        rel_pos = None
        if alert.relative_position_x is not None:
            rel_pos = [
                float(alert.relative_position_x),
                float(alert.relative_position_y or 0.0),
                float(alert.relative_position_z or 0.0),
            ]
        rel_vel = None
        if alert.relative_velocity_x is not None:
            rel_vel = [
                float(alert.relative_velocity_x),
                float(alert.relative_velocity_y or 0.0),
                float(alert.relative_velocity_z or 0.0),
            ]
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
            "hbrA": hbr_a,
            "hbrAIsKnown": hbr_a_known,
            "hbrB": hbr_b,
            "hbrBIsKnown": hbr_b_known,
            "combinedHbr": round(hbr_a + hbr_b, 2),
            "primaryDataQuality": None,
            "secondaryDataQuality": None,
            "relativePosition": rel_pos,
            "relativeVelocity": rel_vel,
            "radialSeparationKm": alert.radial_separation_km,
            "alongTrackSeparationKm": alert.along_track_separation_km,
            "crossTrackSeparationKm": alert.cross_track_separation_km,
            "relativeVelocityAngleDeg": alert.relative_velocity_angle_deg,
            "relativeInclinationDeg": alert.relative_inclination_deg,
            "encounterGeometry": alert.encounter_geometry,
        }
    else:
        pri_norad = alert.conjunction_event.primary_norad_id if getattr(alert, "conjunction_event", None) else (alert.satellite_a.norad_id if getattr(alert, "satellite_a", None) else 0)
        sec_norad = alert.conjunction_event.secondary_norad_id if getattr(alert, "conjunction_event", None) else (alert.satellite_b.norad_id if getattr(alert, "satellite_b", None) else 0)
        hbr_a, hbr_a_known = ProbabilityEngine.resolve_hbr(
            getattr(alert, "satellite_a", None), norad_id=pri_norad
        )
        hbr_b, hbr_b_known = ProbabilityEngine.resolve_hbr(
            getattr(alert, "satellite_b", None), norad_id=sec_norad
        )
        return {
            "id": str(alert.id),
            "primarySatellite": alert.conjunction_event.primary_satellite if getattr(alert, "conjunction_event", None) else (alert.satellite_a.name if getattr(alert, "satellite_a", None) else "Unknown"),
            "primaryNoradId": pri_norad,
            "secondaryObject": alert.conjunction_event.secondary_object if getattr(alert, "conjunction_event", None) else (alert.satellite_b.name if getattr(alert, "satellite_b", None) else "Unknown"),
            "secondaryNoradId": sec_norad,
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
            "hbrA": hbr_a,
            "hbrAIsKnown": hbr_a_known,
            "hbrB": hbr_b,
            "hbrBIsKnown": hbr_b_known,
            "combinedHbr": round(hbr_a + hbr_b, 2),
            "primaryDataQuality": None,
            "secondaryDataQuality": None,
        }


async def _format_alerts_with_quality(alerts: list, db: AsyncSession) -> list[dict]:
    quality_cache = {}
    now = datetime.now(timezone.utc)

    async def get_quality(norad_id: int, sat_id: Optional[Any] = None):
        cache_key = (norad_id, str(sat_id) if sat_id else None)
        if cache_key not in quality_cache:
            try:
                bundle = await DataQualityService.evaluate_orbit_quality(
                    db=db, norad_id=norad_id, satellite_id=sat_id, explicit_now=now
                )
            except Exception as exc:
                logger.error(
                    f"Exception calculating data quality for NORAD {norad_id} (sat_id={sat_id}): {type(exc).__name__}: {exc}. "
                    "Degrading gracefully to insufficient data bundle.",
                    exc_info=True,
                )
                bundle = DataQualityService.get_insufficient_data_bundle(
                    norad_id=norad_id, explicit_now=now, reason=f"Exception: {type(exc).__name__}: {exc}"
                )
            quality_cache[cache_key] = bundle
        return quality_cache[cache_key]

    formatted_list = []
    for a in alerts:
        base_dict = _format_alert(a)
        pri_norad = base_dict.get("primaryNoradId") or 0
        sec_norad = base_dict.get("secondaryNoradId") or 0
        pri_id = getattr(a, "satellite_a_id", None)
        sec_id = getattr(a, "satellite_b_id", None)

        try:
            base_dict["primaryDataQuality"] = await get_quality(pri_norad, pri_id)
        except Exception as exc:
            logger.error(f"Could not compute primary data quality for NORAD {pri_norad}: {type(exc).__name__}: {exc}", exc_info=True)
            base_dict["primaryDataQuality"] = DataQualityService.get_insufficient_data_bundle(
                pri_norad, explicit_now=now, reason=f"Exception: {type(exc).__name__}: {exc}"
            )

        try:
            base_dict["secondaryDataQuality"] = await get_quality(sec_norad, sec_id)
        except Exception as exc:
            logger.error(f"Could not compute secondary data quality for NORAD {sec_norad}: {type(exc).__name__}: {exc}", exc_info=True)
            base_dict["secondaryDataQuality"] = DataQualityService.get_insufficient_data_bundle(
                sec_norad, explicit_now=now, reason=f"Exception: {type(exc).__name__}: {exc}"
            )

        formatted_list.append(base_dict)

    return formatted_list


@router.get("", response_model=List[ConjunctionAlertResponse])
async def get_alerts(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AlertService(db)
    alerts = await service.get_all_alerts()
    return await _format_alerts_with_quality(alerts, db)



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

    formatted = await _format_alerts_with_quality([alert], db)
    return formatted[0]



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
        relative_velocity_km_s=0.08,
        probability=0.00045,
        risk_level="critical",
        status="open",
        detected_by="satguard_synthetic_test",
        relative_position_x=0.08,
        relative_position_y=0.40,
        relative_position_z=-0.08,
        relative_velocity_x=0.001,
        relative_velocity_y=-0.002,
        relative_velocity_z=0.0005,
        radial_separation_km=0.08,
        along_track_separation_km=0.40,
        cross_track_separation_km=-0.08,
        relative_velocity_angle_deg=0.002,
        relative_inclination_deg=0.001,
        encounter_geometry="co-orbital",
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
            relative_position_x=0.12,
            relative_position_y=0.28,
            relative_position_z=-0.15,
            relative_velocity_x=3.2,
            relative_velocity_y=9.8,
            relative_velocity_z=9.7,
            radial_separation_km=0.12,
            along_track_separation_km=0.28,
            cross_track_separation_km=-0.15,
            relative_velocity_angle_deg=92.4,
            relative_inclination_deg=74.1,
            encounter_geometry="crossing",
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
            relative_position_x=-0.25,
            relative_position_y=0.95,
            relative_position_z=0.52,
            relative_velocity_x=4.1,
            relative_velocity_y=7.2,
            relative_velocity_z=9.8,
            radial_separation_km=-0.25,
            along_track_separation_km=0.95,
            cross_track_separation_km=0.52,
            relative_velocity_angle_deg=84.2,
            relative_inclination_deg=58.7,
            encounter_geometry="crossing",
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
            relative_position_x=0.82,
            relative_position_y=2.45,
            relative_position_z=-1.24,
            relative_velocity_x=2.1,
            relative_velocity_y=6.4,
            relative_velocity_z=6.8,
            radial_separation_km=0.82,
            along_track_separation_km=2.45,
            cross_track_separation_km=-1.24,
            relative_velocity_angle_deg=67.8,
            relative_inclination_deg=42.3,
            encounter_geometry="crossing",
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
            relative_position_x=4.2,
            relative_position_y=28.1,
            relative_position_z=15.6,
            relative_velocity_x=1.8,
            relative_velocity_y=5.2,
            relative_velocity_z=4.9,
            radial_separation_km=4.2,
            along_track_separation_km=28.1,
            cross_track_separation_km=15.6,
            relative_velocity_angle_deg=52.1,
            relative_inclination_deg=9.8,
            encounter_geometry="crossing",
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


@router.post("/{alert_id}/maneuver-candidates", response_model=ManeuverGenerationResponse)
async def generate_maneuver_candidates(
    alert_id: str,
    request: Optional[ManeuverGenerationRequest] = None,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a grid of candidate collision-avoidance maneuvers for the given conjunction alert,
    propagates the perturbed primary satellite trajectory via Two-Body + J2 numerical integration,
    refines post-maneuver TCA and miss distance against the secondary object, and scores/ranks
    candidates by efficiency (miss-distance improvement per unit delta-v).
    """
    try:
        alert_uuid = uuid.UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert UUID format")

    service = ManeuverCandidateService(db)

    magnitude_grid = request.magnitude_grid_m_s if request else None
    timing_grid = request.timing_grid_hours if request else None
    directions = request.directions if request else None
    save_to_db = request.save_to_db if request is not None else True

    try:
        result = await service.generate_candidates_for_alert(
            alert_id=alert_uuid,
            magnitude_grid_m_s=magnitude_grid,
            timing_grid_hours=timing_grid,
            directions=directions,
            save_to_db=save_to_db,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error generating maneuver candidates for alert {alert_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Maneuver candidate generation failed: {str(exc)}")


@router.get("/{alert_id}/maneuver-candidates", response_model=ManeuverGenerationResponse)
async def get_maneuver_candidates(
    alert_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves previously computed and cached candidate collision-avoidance maneuvers for the given alert.
    """
    try:
        alert_uuid = uuid.UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert UUID format")

    service = ManeuverCandidateService(db)
    result = await service.get_saved_candidates_for_alert(alert_uuid)

    if not result:
        raise HTTPException(
            status_code=404,
            detail="No candidate maneuvers found for this alert. Call POST to generate candidates.",
        )
    return result


