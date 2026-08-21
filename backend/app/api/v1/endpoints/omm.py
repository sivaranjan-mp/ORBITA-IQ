from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Any, Dict

from app.core.supabase_client import get_admin_client
from app.dependencies import get_current_user
from app.schemas.auth import UserProfile
from app.services.omm_parser import parse_omm_json

router = APIRouter(prefix="/omm", tags=["omm"])


class OMMUploadRequest(BaseModel):
    payload: Dict[str, Any]


@router.post("/upload")
async def upload_omm(request: OMMUploadRequest, current_user: UserProfile = Depends(get_current_user)):
    # Verify user is admin or operator
    if current_user.role not in ["admin", "operator"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to upload telemetry")

    admin = get_admin_client()

    parsed = parse_omm_json(request.payload)
    norad_id = parsed.get("norad_id")

    if not norad_id:
        raise HTTPException(
            status_code=400, detail="Missing NORAD_CAT_ID in OMM payload")

    # Check if satellite exists
    sat_res = admin.table("satellites").select("id").eq(
        "norad_id", norad_id).maybe_single().execute()
    if not sat_res or not sat_res.data:
        raise HTTPException(
            status_code=404, detail=f"Satellite with NORAD ID {norad_id} not found in database")

    sat_id = sat_res.data["id"]

    # Insert OMM
    new_omm = {
        "satellite_id": sat_id,
        "epoch": parsed["epoch"].isoformat() if parsed["epoch"] else None,
        "payload": request.payload
    }

    insert_res = admin.table("omm_records").insert(new_omm).execute()
    if not insert_res.data:
        raise HTTPException(
            status_code=500, detail="Failed to insert OMM record")

    return {"message": "OMM payload uploaded successfully", "id": insert_res.data[0]["id"]}
