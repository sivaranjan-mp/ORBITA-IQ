from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Any, Dict

from app.core.supabase_client import get_admin_client
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.services.cdm_parser import parse_cdm_json

router = APIRouter(prefix="/cdm", tags=["cdm"])


class CDMUploadRequest(BaseModel):
    payload: Dict[str, Any]


@router.post("/upload")
async def upload_cdm(request: CDMUploadRequest, current_user: UserProfile = Depends(get_current_user)):
    # Verify user is admin or operator
    if current_user.role not in ["admin", "operator"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to upload telemetry")

    admin = get_admin_client()

    parsed = parse_cdm_json(request.payload)

    if not parsed.get("primary_norad_id") or not parsed.get("secondary_norad_id"):
        raise HTTPException(
            status_code=400, detail="Missing primary or secondary NORAD IDs in CDM")

    if not parsed.get("tca"):
        raise HTTPException(
            status_code=400, detail="Missing TCA (Time of Closest Approach)")

    # Insert CDM record
    new_cdm = {
        "primary_norad_id": parsed.get("primary_norad_id"),
        "secondary_norad_id": parsed.get("secondary_norad_id"),
        "tca": parsed["tca"].isoformat() if parsed["tca"] else None,
        "payload": request.payload
    }

    cdm_res = admin.table("cdm_records").insert(new_cdm).execute()
    if not cdm_res.data:
        raise HTTPException(
            status_code=500, detail="Failed to insert CDM record")

    # Insert into conjunction_events (basic conversion)
    prob = parsed.get("collision_probability") or 0
    risk = "low"
    if float(prob) > 1e-4:
        risk = "critical"
    elif float(prob) > 1e-5:
        risk = "high"
    elif float(prob) > 1e-6:
        risk = "medium"

    new_event = {
        "primary_satellite": f"Object {parsed.get('primary_norad_id')}",
        "primary_norad_id": parsed.get("primary_norad_id"),
        "secondary_object": f"Object {parsed.get('secondary_norad_id')}",
        "secondary_norad_id": parsed.get("secondary_norad_id"),
        "tca": parsed["tca"].isoformat() if parsed["tca"] else None,
        "miss_distance_m": float(parsed.get("miss_distance") or 0),
        "probability": float(prob),
        "risk_level": risk,
        "status": "open",
        "detected_by": "cdm_upload"
    }

    admin.table("conjunction_events").insert(new_event).execute()

    return {"message": "CDM payload uploaded successfully", "id": cdm_res.data[0]["id"]}
