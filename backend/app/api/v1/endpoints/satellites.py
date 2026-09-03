import asyncio
import logging
import time
from typing import List, Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.core.supabase_client import get_admin_client
from app.schemas.satellites import (
    SatelliteAddRequest,
    SatelliteAddFromTLERequest,
    SatelliteResponse,
    SatelliteUpdateRequest,
    TLEUploadRequest,
    OMMUploadRequest,
    SatelliteBulkAddRequest,
    SatelliteBulkAddResponse,
    SatelliteBulkAddResult,
)
from app.services.celestrak_service import CELESTRAK_HEADERS
from app.services.satellite_service import SatelliteService
from app.models.satellites import Satellite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/satellites", tags=["satellites"])


_PROFILES_CACHE: dict[str, str] = {}
_PROFILES_CACHE_TIMESTAMP: float = 0.0
_PROFILES_CACHE_TTL: float = 60.0  # seconds


def _get_owner_profiles_map() -> dict[str, str]:
    global _PROFILES_CACHE, _PROFILES_CACHE_TIMESTAMP
    now = time.time()
    if _PROFILES_CACHE and (now - _PROFILES_CACHE_TIMESTAMP) < _PROFILES_CACHE_TTL:
        return _PROFILES_CACHE

    try:
        admin = get_admin_client()
        result = admin.table("profiles").select("employee_id, full_name").execute()
        if result and result.data:
            _PROFILES_CACHE = {
                p["employee_id"].strip().upper(): p["full_name"].strip()
                for p in result.data
                if p.get("employee_id") and p.get("full_name")
            }
            _PROFILES_CACHE_TIMESTAMP = now
            return _PROFILES_CACHE
    except Exception as exc:
        logger.warning(f"Could not load owner profiles from Supabase: {exc}")
    return _PROFILES_CACHE or {}


def _format_satellite_response(sat: Satellite, owner_name: Optional[str] = None) -> dict:
    owner_emp_id = sat.owner_org if sat.owner_org and sat.owner_org != "Unknown" else None
    resp = {
        "id": str(sat.id),
        "noradId": sat.norad_id,
        "name": sat.name,
        "internationalDesignator": sat.international_designator or "",
        "objectType": sat.object_type or "payload",
        "status": sat.status or "active",
        "ownerOrg": sat.owner_org or "Unknown",
        "ownerName": owner_name,
        "ownerEmployeeId": owner_emp_id,
        "altitudeKm": None,
        "latitudeDeg": None,
        "longitudeDeg": None,
        "velocityKmS": None,
        "inclinationDeg": None,
        "periodMinutes": None,
        "eccentricity": None,
        "lastTleEpoch": None,
        "raanDeg": None,
        "meanAnomalyDeg": None,
    }

    if sat.orbit_state and sat.orbit_state.latitude_deg is not None and sat.orbit_state.latitude_deg != 0.0:
        resp.update({
            "altitudeKm": sat.orbit_state.altitude_km,
            "latitudeDeg": sat.orbit_state.latitude_deg,
            "longitudeDeg": sat.orbit_state.longitude_deg,
            "velocityKmS": sat.orbit_state.velocity_km_s,
            "inclinationDeg": sat.orbit_state.inclination_deg,
            "periodMinutes": sat.orbit_state.period_minutes,
            "eccentricity": sat.orbit_state.eccentricity,
            "lastTleEpoch": sat.orbit_state.epoch,
            "raanDeg": sat.orbit_state.raan_deg,
            "meanAnomalyDeg": sat.orbit_state.mean_anomaly_deg,
        })
    else:
        # Fallback to dynamic live SGP4 propagation from stored TLE
        line1, line2 = None, None
        if hasattr(sat, 'tle_records') and sat.tle_records:
            latest_tle = max(sat.tle_records, key=lambda t: t.epoch)
            line1, line2 = latest_tle.line1, latest_tle.line2

        if line1 and line2:
            from datetime import datetime, timezone
            from app.services.sgp4_service import propagate_tle
            now_utc = datetime.now(timezone.utc)
            state = propagate_tle(line1, line2, now_utc)
            if state:
                resp.update({
                    "altitudeKm": state["altitude_km"],
                    "latitudeDeg": state["latitude_deg"],
                    "longitudeDeg": state["longitude_deg"],
                    "velocityKmS": state["velocity_km_s"],
                    "inclinationDeg": state["inclination_deg"],
                    "periodMinutes": state["period_minutes"],
                    "eccentricity": state["eccentricity"],
                    "lastTleEpoch": state["epoch"],
                    "raanDeg": state["raan_deg"],
                    "meanAnomalyDeg": state["mean_anomaly_deg"],
                })
        elif sat.orbit_state:
            resp.update({
                "altitudeKm": sat.orbit_state.altitude_km,
                "latitudeDeg": sat.orbit_state.latitude_deg,
                "longitudeDeg": sat.orbit_state.longitude_deg,
                "velocityKmS": sat.orbit_state.velocity_km_s,
                "inclinationDeg": sat.orbit_state.inclination_deg,
                "periodMinutes": sat.orbit_state.period_minutes,
                "eccentricity": sat.orbit_state.eccentricity,
                "lastTleEpoch": sat.orbit_state.epoch,
                "raanDeg": sat.orbit_state.raan_deg,
                "meanAnomalyDeg": sat.orbit_state.mean_anomaly_deg,
            })
    return resp


@router.get("/debug/celestrak")
async def debug_celestrak(norad_id: int = 25544):
    """
    Temporary debug endpoint to test CelesTrak connection directly and in isolation.
    """
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=tle"
    try:
        async with httpx.AsyncClient(headers=CELESTRAK_HEADERS) as client:
            response = await client.get(url, timeout=10.0)
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "text_snippet": response.text[:300],
                "url": url
            }
    except Exception as exc:
        return {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "url": url
        }


@router.get("", response_model=List[SatelliteResponse])
async def list_satellites(
    scope: str = "mine",
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = SatelliteService(db)
    
    if scope == "mine":
        satellites = await service.get_all_satellites(owner_org=current_user.employee_id)
    else:
        satellites = await service.get_all_satellites()
        
    profiles_map = _get_owner_profiles_map()
    return [
        _format_satellite_response(
            sat,
            owner_name=profiles_map.get((sat.owner_org or "").strip().upper())
            or (current_user.full_name if (sat.owner_org or "").strip().upper() == current_user.employee_id.strip().upper() else None)
        )
        for sat in satellites
    ]


@router.get("/{id}", response_model=SatelliteResponse)
async def get_satellite(
    id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = SatelliteService(db)
    sat = await service.get_satellite_by_id(id)
    if not sat:
        raise HTTPException(status_code=404, detail="Satellite not found")
    profiles_map = _get_owner_profiles_map()
    owner_name = profiles_map.get((sat.owner_org or "").strip().upper()) or (
        current_user.full_name if (sat.owner_org or "").strip().upper() == current_user.employee_id.strip().upper() else None
    )
    return _format_satellite_response(sat, owner_name=owner_name)


@router.post("/norad", response_model=SatelliteResponse)
async def add_satellite_by_norad(
    request: SatelliteAddRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    service = SatelliteService(db)
    try:
        sat = await service.add_satellite_by_norad(request.norad_id, owner_org=current_user.employee_id)
        return _format_satellite_response(sat, owner_name=current_user.full_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException as e:
        logger.warning(f"HTTPException while adding satellite {request.norad_id}: {e.status_code} - {e.detail}")
        raise
    except Exception as e:
        logger.exception(f"Unhandled exception while adding satellite by NORAD ID {request.norad_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual", response_model=SatelliteResponse)
async def add_satellite_manual(
    request: SatelliteAddFromTLERequest,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    service = SatelliteService(db)
    try:
        sat = await service.add_satellite_from_tle(request.raw_tle, owner_org=current_user.employee_id)
        return _format_satellite_response(sat, owner_name=current_user.full_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException as e:
        logger.warning(f"HTTPException while adding satellite from TLE: {e.status_code} - {e.detail}")
        raise
    except Exception as e:
        logger.exception(f"Unhandled exception while adding satellite from TLE: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/norad/bulk", response_model=SatelliteBulkAddResponse)
async def add_satellites_by_norad_bulk(
    request: SatelliteBulkAddRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    service = SatelliteService(db)
    
    successful = 0
    failed = 0
    results = []

    for norad_id in request.norad_ids:
        try:
            # We catch exceptions to prevent one failure from stopping the whole batch
            await service.add_satellite_by_norad(norad_id, owner_org=current_user.employee_id)
            successful += 1
            results.append(SatelliteBulkAddResult(
                norad_id=norad_id,
                success=True
            ))
        except ValueError as e:
            failed += 1
            results.append(SatelliteBulkAddResult(
                norad_id=norad_id,
                success=False,
                reason=str(e)
            ))
        except HTTPException as e:
            failed += 1
            results.append(SatelliteBulkAddResult(
                norad_id=norad_id,
                success=False,
                reason=str(e.detail)
            ))
        except Exception as e:
            logger.exception(f"Unhandled exception while bulk adding satellite by NORAD ID {norad_id}: {e}")
            failed += 1
            results.append(SatelliteBulkAddResult(
                norad_id=norad_id,
                success=False,
                reason="Internal Server Error"
            ))
        
        # Sleep to avoid rate limiting from CelesTrak. 1 second is safe.
        await asyncio.sleep(1.0)

    return SatelliteBulkAddResponse(
        successful=successful,
        failed=failed,
        results=results
    )


@router.put("/{id}", response_model=SatelliteResponse)
async def update_satellite(
    id: str,
    request: SatelliteUpdateRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update satellites")
    service = SatelliteService(db)
    try:
        sat = await service.update_satellite(id, request)
        profiles_map = _get_owner_profiles_map()
        owner_name = profiles_map.get((sat.owner_org or "").strip().upper())
        return _format_satellite_response(sat, owner_name=owner_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{id}")
async def delete_satellite(
    id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403, detail="Only admins can delete satellites")

    service = SatelliteService(db)
    success = await service.delete_satellite(id)
    if not success:
        raise HTTPException(status_code=404, detail="Satellite not found")
    return {"message": "Satellite successfully deleted"}


@router.post("/upload-tle")
async def upload_tle(
    request: TLEUploadRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can upload TLEs")
    service = SatelliteService(db)
    try:
        sat = await service.upload_tle(request.norad_id, request.raw_tle)
        return {"message": "TLE uploaded successfully", "id": str(sat.id)}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/upload-omm")
async def upload_omm(
    request: OMMUploadRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can upload OMMs")
    service = SatelliteService(db)
    try:
        sat = await service.upload_omm(request.payload.model_dump())
        return {"message": "OMM payload uploaded successfully", "id": str(sat.id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
