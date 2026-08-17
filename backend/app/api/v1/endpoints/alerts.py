from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime, timedelta, timezone

from app.core.supabase_client import get_admin_client, get_public_client
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.schemas.alerts import ConjunctionAlertResponse, AlertStatusUpdate

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("", response_model=List[ConjunctionAlertResponse])
async def get_alerts(current_user: UserProfile = Depends(get_current_user)):
    admin = get_admin_client()
    
    res = admin.table("conjunction_events").select("*").order("tca", desc=True).execute()
    
    responses = []
    for alert in res.data:
        responses.append({
            "id": alert["id"],
            "primarySatellite": alert["primary_satellite"],
            "primaryNoradId": alert["primary_norad_id"],
            "secondaryObject": alert["secondary_object"],
            "secondaryNoradId": alert["secondary_norad_id"],
            "tca": alert["tca"],
            "missDistanceM": alert["miss_distance_m"],
            "probability": alert["probability"],
            "riskLevel": alert["risk_level"],
            "status": alert["status"],
            "detectedBy": alert["detected_by"],
            "createdAt": alert["created_at"],
        })
        
    return responses

@router.put("/{alert_id}/status", response_model=ConjunctionAlertResponse)
async def update_alert_status(alert_id: str, update: AlertStatusUpdate, current_user: UserProfile = Depends(get_current_user)):
    admin = get_admin_client()
    
    if update.status not in ["open", "monitoring", "resolved", "dismissed"]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    res = admin.table("conjunction_events").update({"status": update.status}).eq("id", alert_id).execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    alert = res.data[0]
    return {
        "id": alert["id"],
        "primarySatellite": alert["primary_satellite"],
        "primaryNoradId": alert["primary_norad_id"],
        "secondaryObject": alert["secondary_object"],
        "secondaryNoradId": alert["secondary_norad_id"],
        "tca": alert["tca"],
        "missDistanceM": alert["miss_distance_m"],
        "probability": alert["probability"],
        "riskLevel": alert["risk_level"],
        "status": alert["status"],
        "detectedBy": alert["detected_by"],
        "createdAt": alert["created_at"],
    }

@router.post("/seed", response_model=List[ConjunctionAlertResponse])
async def seed_mock_alerts(current_user: UserProfile = Depends(get_current_user)):
    admin = get_admin_client()
    
    now = datetime.now(timezone.utc)
    hours = lambda h: (now + timedelta(hours=h)).isoformat()
    
    mock_alerts = [
      {
        "primary_satellite": "ISS (ZARYA)",
        "primary_norad_id": 25544,
        "secondary_object": "COSMOS 2251 DEB",
        "secondary_norad_id": 33591,
        "tca": hours(6.2),
        "miss_distance_m": 340,
        "probability": 0.00042,
        "risk_level": "critical",
        "status": "open",
        "detected_by": "satguard"
      },
      {
        "primary_satellite": "STARLINK-3011",
        "primary_norad_id": 48274,
        "secondary_object": "FENGYUN 1C DEB",
        "secondary_norad_id": 29657,
        "tca": hours(14.8),
        "miss_distance_m": 1120,
        "probability": 0.000037,
        "risk_level": "high",
        "status": "monitoring",
        "detected_by": "satguard"
      },
      {
        "primary_satellite": "NOAA-20",
        "primary_norad_id": 43013,
        "secondary_object": "SL-16 R/B",
        "secondary_norad_id": 22285,
        "tca": hours(28.4),
        "miss_distance_m": 2870,
        "probability": 0.0000041,
        "risk_level": "medium",
        "status": "monitoring",
        "detected_by": "cdm_upload"
      }
    ]
    
    # Delete existing
    admin.table("conjunction_events").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    
    # Insert new
    res = admin.table("conjunction_events").insert(mock_alerts).execute()
    
    responses = []
    for alert in res.data:
        responses.append({
            "id": alert["id"],
            "primarySatellite": alert["primary_satellite"],
            "primaryNoradId": alert["primary_norad_id"],
            "secondaryObject": alert["secondary_object"],
            "secondaryNoradId": alert["secondary_norad_id"],
            "tca": alert["tca"],
            "missDistanceM": alert["miss_distance_m"],
            "probability": alert["probability"],
            "riskLevel": alert["risk_level"],
            "status": alert["status"],
            "detectedBy": alert["detected_by"],
            "createdAt": alert["created_at"],
        })
        
    return responses
