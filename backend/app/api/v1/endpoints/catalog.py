import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.schemas.catalog import CatalogListResponse, CatalogSyncResponse
from app.schemas.satellites import SatelliteResponse
from app.services.catalog_service import CatalogService
from app.services.satellite_service import SatelliteService
from app.api.v1.endpoints.satellites import _format_satellite_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=CatalogListResponse)
async def list_catalog(
    search: Optional[str] = Query(None, description="Search by name, NORAD ID, or international designator"),
    regime: Optional[str] = Query("ALL", description="Filter by orbit regime: ALL, LEO, MEO, GEO, HEO"),
    object_type: Optional[str] = Query("all", description="Filter by object type: all, payload, rocket_body, debris"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=100, description="Items per page"),
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CatalogService(db)
    return await service.search_catalog(
        query=search,
        regime=regime,
        object_type=object_type,
        page=page,
        limit=limit,
        user_employee_id=current_user.employee_id,
    )


@router.post("/sync", response_model=CatalogSyncResponse)
async def sync_catalog(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only operators and admins can synchronize the catalog.",
        )
    service = CatalogService(db)
    count, msg = await service.sync_celestrak_active_catalog()
    return CatalogSyncResponse(syncedCount=count, message=msg)


@router.post("/track/{norad_id}", response_model=SatelliteResponse)
async def track_catalog_satellite(
    norad_id: int,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to track satellites.",
        )
    sat_service = SatelliteService(db)
    try:
        sat = await sat_service.add_satellite_by_norad(
            norad_id, owner_org=current_user.employee_id
        )
        return _format_satellite_response(sat, owner_name=current_user.full_name)
    except Exception as exc:
        logger.exception(f"Error tracking satellite {norad_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track satellite: {str(exc)}",
        )
