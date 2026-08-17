from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.schemas.satellites import (
    SatelliteAddRequest, 
    SatelliteResponse, 
    SatelliteUpdateRequest,
    TLEUploadRequest,
    OMMUploadRequest
)
from app.services.satellite_service import SatelliteService
from app.models.satellites import Satellite

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
        "altitudeKm": 0.0,
        "inclinationDeg": 0.0,
        "periodMinutes": 0.0,
        "eccentricity": 0.0,
        "raanDeg": 0.0,
        "meanAnomalyDeg": 0.0,
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

@router.get("", response_model=List[SatelliteResponse])
async def list_satellites(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = SatelliteService(db)
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
    service = SatelliteService(db)
    try:
        sat = await service.add_satellite_by_norad(request.norad_id)
        return _format_satellite_response(sat)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{id}", response_model=SatelliteResponse)
async def update_satellite(
    id: str, 
    request: SatelliteUpdateRequest, 
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
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
        raise HTTPException(status_code=403, detail="Only admins can delete satellites")
        
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
    service = SatelliteService(db)
    try:
        sat = await service.upload_omm(request.payload)
        return {"message": "OMM payload uploaded successfully", "id": str(sat.id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
