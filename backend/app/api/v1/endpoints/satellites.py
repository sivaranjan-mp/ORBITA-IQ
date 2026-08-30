import asyncio
import logging
from typing import List
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
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
from app.services.satellite_service import SatelliteService
from app.models.satellites import Satellite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/satellites", tags=["satellites"])


def _format_satellite_response(sat: Satellite) -> dict:
    resp = {
        "id": str(sat.id),
        "noradId": sat.norad_id,
        "name": sat.name,
        "internationalDesignator": sat.international_designator or "",
        "objectType": sat.object_type,
        "status": sat.status,
        "ownerOrg": sat.owner_org or "Unknown",
        "altitudeKm": None,
        "inclinationDeg": None,
        "periodMinutes": None,
        "eccentricity": None,
        "lastTleEpoch": None,
        "raanDeg": None,
        "meanAnomalyDeg": None,
    }

    if sat.orbit_state:
        resp.update({
            "altitudeKm": sat.orbit_state.altitude_km,
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
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ORBITA-IQ/1.0)"}
    try:
        async with httpx.AsyncClient(headers=headers) as client:
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
        
    return [_format_satellite_response(sat) for sat in satellites]


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
    return _format_satellite_response(sat)


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
        return _format_satellite_response(sat)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
        return _format_satellite_response(sat)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
        return _format_satellite_response(sat)
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
        raise HTTPException(status_code=400, detail=str(e))


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
