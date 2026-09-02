import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.satellites import _format_satellite_response
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.schemas.catalog import (
    CatalogListResponse,
    CatalogSyncResponse,
    CatalogSyncStatusResponse,
)
from app.schemas.satellites import SatelliteResponse
from app.services.catalog_service import CatalogService, sync_tracker
from app.services.satellite_service import SatelliteService

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


@router.get("/sync/status", response_model=CatalogSyncStatusResponse)
async def get_catalog_sync_status(
    current_user: UserProfile = Depends(get_current_user),
):
    return sync_tracker.get_status_response()


@router.post("/sync", response_model=CatalogSyncResponse)
async def sync_catalog(
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Bypass fair-use cooldown"),
    current_user: UserProfile = Depends(get_current_user),
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only operators and admins can synchronize the catalog.",
        )

    # 1. Guard against concurrent syncs
    if sync_tracker.status == "running":
        return CatalogSyncResponse(
            syncedCount=sync_tracker.synced_count,
            message="Catalog synchronization is already running in the background.",
            status="running",
        )

    # 2. Fair-use cooldown (3 minutes between syncs unless force=True)
    if not force and sync_tracker.last_sync_completed_at:
        elapsed_seconds = (datetime.now(timezone.utc) - sync_tracker.last_sync_completed_at).total_seconds()
        if elapsed_seconds < 180:
            remaining = int(180 - elapsed_seconds)
            return CatalogSyncResponse(
                syncedCount=sync_tracker.synced_count,
                message=f"Catalog was recently synchronized. Please wait {remaining}s before syncing again.",
                status="completed",
            )

    # 3. Trigger background execution
    background_tasks.add_task(CatalogService.run_sync_background_job)
    return CatalogSyncResponse(
        syncedCount=0,
        message="CelesTrak active catalog synchronization initiated in background.",
        status="running",
    )


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
