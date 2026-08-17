"""
FastAPI dependencies for authentication and role-based authorization.

get_current_user:
    Validates the bearer token, then loads the caller's profile
    (employee_id, role, active flag, ...) from public.profiles using
    the admin (service-role) client so this works regardless of RLS.

require_role(*roles):
    A dependency factory used on route declarations, e.g.:
        Depends(require_role("admin"))
        Depends(require_role("admin", "operator"))
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import TokenError, decode_access_token
from app.core.supabase_client import get_admin_client
from app.schemas.auth import UserProfile

bearer_scheme = HTTPBearer(auto_error=True)

PROFILE_COLUMNS = "id, employee_id, full_name, role, department, is_active, last_login_at"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserProfile:
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")

    admin = get_admin_client()
    result = (
        admin.table("profiles")
        .select(PROFILE_COLUMNS)
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )

    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User profile not found.")

    profile = result.data
    if not profile.get("is_active", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated.")

    return UserProfile(**profile)


def require_role(*allowed_roles: str):
    async def _checker(user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return user

    return _checker
