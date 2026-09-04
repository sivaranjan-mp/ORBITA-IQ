import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.schemas.ai_advisory import (
    AdvisoryRecommendationRequest,
    AIManeuverAdvisoryResponse,
)
from app.schemas.auth import UserProfile
from app.services.ai_advisory_service import AIAdvisoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistant", tags=["ai-assistant"])


@router.get("/advisories", response_model=List[AIManeuverAdvisoryResponse])
async def list_cached_advisories(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all cached qualitative AI maneuver advisories.
    Zero LLM API cost (serves precomputed/cached analysis).
    """
    service = AIAdvisoryService(db)
    return await service.get_all_advisories()


@router.get("/advisories/{alert_id}", response_model=AIManeuverAdvisoryResponse)
async def get_advisory_for_alert(
    alert_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the cached AI advisory for a specific conjunction alert if present.
    """
    service = AIAdvisoryService(db)
    alert = await service.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conjunction alert '{alert_id}' not found.",
        )

    cached = await service.get_cached_advisory(alert.id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI advisory generated yet for alert '{alert_id}'.",
        )

    return service._format_advisory_response(cached, alert, is_cached=True)


@router.post("/recommend", response_model=AIManeuverAdvisoryResponse)
async def generate_maneuver_recommendation(
    payload: AdvisoryRecommendationRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    On-demand endpoint to generate a qualitative collision avoidance advisory
    for a given conjunction alert using an LLM.
    Results are cached in Postgres; pass force_refresh=True to regenerate.
    """
    # Restrict paid on-demand generation to operator/admin roles
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only operators and admins can trigger AI advisory generation.",
        )

    service = AIAdvisoryService(db)
    try:
        advisory = await service.generate_or_get_advisory(
            alert_id=payload.alert_id,
            force_refresh=payload.force_refresh,
        )
        return advisory
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )
    except Exception as err:
        logger.exception(f"Failed to generate AI advisory: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Advisory generation failed: {str(err)}",
        )
