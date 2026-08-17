from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.services.satellite_service import SatelliteService
from app.core.supabase_client import get_admin_client

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("")
async def get_dashboard(
    current_user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Tracked Satellites
    sat_service = SatelliteService(db)
    satellites = await sat_service.get_all_satellites()
    tracked_satellites = len(satellites)
    
    # 2. Active & High Risk Alerts (using Supabase admin client since alerts module hasn't been migrated to SQLAlchemy)
    admin = get_admin_client()
    alerts_res = admin.table("conjunction_events").select("*").execute()
    
    all_alerts = alerts_res.data if alerts_res and alerts_res.data else []
    
    active_alerts = 0
    high_risk_alerts = 0
    next_conjunction = None
    
    now = datetime.utcnow().isoformat()
    
    for alert in all_alerts:
        if alert.get("status") in ["open", "monitoring"]:
            active_alerts += 1
            if alert.get("risk_level") in ["high", "critical"]:
                high_risk_alerts += 1
                
        # Find next upcoming conjunction
        tca = alert.get("tca")
        if tca and tca > now:
            if not next_conjunction or tca < next_conjunction.get("tca"):
                next_conjunction = alert
                
    # Format the next conjunction
    formatted_next = None
    if next_conjunction:
        formatted_next = {
            "primarySatellite": next_conjunction.get("primary_satellite"),
            "secondaryObject": next_conjunction.get("secondary_object"),
            "tca": next_conjunction.get("tca"),
            "riskLevel": next_conjunction.get("risk_level"),
            "missDistanceM": next_conjunction.get("miss_distance_m")
        }

    return {
        "tracked_satellites": tracked_satellites,
        "active_alerts": active_alerts,
        "high_risk_alerts": high_risk_alerts,
        "next_conjunction": formatted_next
    }
