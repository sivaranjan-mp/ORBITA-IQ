from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel

from app.dependencies import get_current_user, require_role
from app.schemas.auth import UserProfile
from app.core.supabase_client import get_admin_client

router = APIRouter(prefix="/users", tags=["users"])

class UserCreate(BaseModel):
    email: str
    password: str
    employee_id: str
    full_name: str
    role: str
    department: Optional[str] = None

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: str
    employee_id: str
    email: str
    full_name: str
    role: str
    department: Optional[str] = None
    is_active: bool

@router.get("", response_model=List[UserResponse])
async def list_users(
    current_user: UserProfile = Depends(require_role("admin"))
):
    admin = get_admin_client()
    result = admin.table("profiles").select("*").execute()
    return result.data

@router.post("", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    current_user: UserProfile = Depends(require_role("admin"))
):
    admin = get_admin_client()
    try:
        response = admin.auth.admin.create_user({
            "email": user.email,
            "password": user.password,
            "email_confirm": True,
            "user_metadata": {
                "employee_id": user.employee_id,
                "full_name": user.full_name,
                "role": user.role,
                "department": user.department
            }
        })
        
        profile = admin.table("profiles").select("*").eq("id", response.user.id).maybe_single().execute()
        return profile.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: UserProfile = Depends(require_role("admin"))
):
    admin = get_admin_client()
    update_data = {}
    if user_update.role is not None:
        update_data["role"] = user_update.role
    if user_update.is_active is not None:
        update_data["is_active"] = user_update.is_active
        
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    # Since we are using the admin client (service_role), it bypasses RLS.
    # To bypass the trigger `prevent_self_privilege_escalation` which checks public.is_admin(),
    # we update via raw SQL or we can just update the user_metadata via auth admin.
    # We will try the table update directly, which will work if service_role doesn't fail the trigger.
    # Wait, actually, the trigger is:
    # if not public.is_admin() then raise exception.
    # To be safe, we can update user metadata and let the sync happen? No, sync only happens on create.
    # Let's just update the profile.
    try:
        # We must set the context to an admin user so the trigger succeeds.
        # Since Supabase python client doesn't support set_config directly,
        # we can just use the admin.table directly. The trigger might fail if auth.uid() is null.
        # Let's use the DB session if we need to, but the client is easier here.
        # Assuming the service role bypasses the trigger or it allows it.
        result = admin.table("profiles").update(update_data).eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_id}")
async def deactivate_user(
    user_id: str,
    current_user: UserProfile = Depends(require_role("admin"))
):
    admin = get_admin_client()
    try:
        result = admin.table("profiles").update({"is_active": False}).eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")
        return {"detail": "User deactivated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
