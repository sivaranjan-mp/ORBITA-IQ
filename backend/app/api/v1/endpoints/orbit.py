from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.satellites import OrbitState
from app.schemas.auth import UserProfile

router = APIRouter(prefix="/orbit", tags=["orbit"])


@router.get("/{satellite_id}")
async def get_orbit_state(
    satellite_id: str,
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Simply fetch the latest pre-computed state from the database
    result = await db.execute(select(OrbitState).where(OrbitState.satellite_id == satellite_id))
    orbit_state = result.scalars().first()

    if not orbit_state:
        raise HTTPException(
            status_code=404, detail="Orbit state not found. Wait for the background scheduler to process it.")

    return {
        "latitude": orbit_state.latitude_deg,
        "longitude": orbit_state.longitude_deg,
        "altitude": orbit_state.altitude_km,
        "velocity": orbit_state.velocity_km_s,
        "epoch": orbit_state.epoch.isoformat()
    }
