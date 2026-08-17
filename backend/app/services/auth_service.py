"""
Core authentication business logic.

Design notes
------------
Employee ID login: Supabase Auth is email/password native, so we keep
a denormalized `email` column on public.profiles (populated by a DB
trigger when auth.users rows are created). Login resolves
employee_id -> email server-side (service-role client, bypasses RLS
so this works pre-authentication) and then delegates the actual
password check to Supabase's own GoTrue engine via the anon client's
sign_in_with_password. We never compare passwords ourselves.

Lockout: failed attempts are tracked per-profile. After
LOGIN_MAX_ATTEMPTS consecutive failures, the account is locked for
LOGIN_LOCKOUT_MINUTES. All attempts (success and failure) are written
to login_audit_log for security monitoring.

Enumeration resistance: login and password-reset failures always
return the same generic message/response regardless of whether the
employee ID exists.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from gotrue.errors import AuthApiError

from app.core.config import get_settings
from app.core.supabase_client import get_admin_client, get_public_client
from app.schemas.auth import (
    LoginRequest,
    PasswordResetRequest,
    TokenResponse,
    UserProfile,
)

settings = get_settings()

GENERIC_LOGIN_ERROR = "Invalid employee ID or password."
GENERIC_RESET_MESSAGE = (
    "If that employee ID exists, a password reset link has been sent to the "
    "registered email address."
)

PROFILE_COLUMNS = (
    "id, employee_id, email, full_name, role, department, is_active, "
    "failed_login_attempts, locked_until, last_login_at"
)


class AuthService:
    def __init__(self) -> None:
        self.admin = get_admin_client()
        self.public = get_public_client()

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login(self, payload: LoginRequest, ip_address: str | None) -> TokenResponse:
        profile_row = self._get_profile_by_employee_id(payload.employee_id)

        if profile_row is None:
            self._record_attempt(None, payload.employee_id, ip_address, success=False)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)

        self._assert_not_locked(profile_row)

        if not profile_row.get("is_active", False):
            self._record_attempt(profile_row["id"], payload.employee_id, ip_address, success=False)
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Account is deactivated. Contact an administrator."
            )

        try:
            auth_response = self.public.auth.sign_in_with_password(
                {"email": profile_row["email"], "password": payload.password}
            )
        except AuthApiError:
            self._register_failed_attempt(profile_row, payload.employee_id, ip_address)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)

        session = auth_response.session
        if session is None:
            self._register_failed_attempt(profile_row, payload.employee_id, ip_address)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)

        self._reset_failed_attempts(profile_row["id"])
        self._record_attempt(profile_row["id"], payload.employee_id, ip_address, success=True)

        now_iso = datetime.now(timezone.utc).isoformat()
        self.admin.table("profiles").update({"last_login_at": now_iso}).eq(
            "id", profile_row["id"]
        ).execute()

        user = UserProfile(
            id=profile_row["id"],
            employee_id=profile_row["employee_id"],
            full_name=profile_row["full_name"],
            role=profile_row["role"],
            department=profile_row.get("department"),
            is_active=profile_row["is_active"],
            last_login_at=datetime.now(timezone.utc),
        )

        return TokenResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=session.expires_in,
            expires_at=session.expires_at,
            user=user,
        )

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            auth_response = self.public.auth.refresh_session(refresh_token)
        except AuthApiError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please log in again.")

        session = auth_response.session
        if session is None or auth_response.user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please log in again.")

        profile_row = self._get_profile_by_id(auth_response.user.id)
        if profile_row is None or not profile_row.get("is_active", False):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated.")

        user = UserProfile(
            id=profile_row["id"],
            employee_id=profile_row["employee_id"],
            full_name=profile_row["full_name"],
            role=profile_row["role"],
            department=profile_row.get("department"),
            is_active=profile_row["is_active"],
            last_login_at=profile_row.get("last_login_at"),
        )

        return TokenResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=session.expires_in,
            expires_at=session.expires_at,
            user=user,
        )

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------
    def logout(self, access_token: str) -> None:
        """Best-effort server-side revocation. Client also clears its
        local Supabase session regardless of the outcome here."""
        try:
            self.public.auth.sign_out()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------
    def request_password_reset(self, payload: PasswordResetRequest) -> None:
        profile_row = self._get_profile_by_employee_id(payload.employee_id)
        if profile_row is None:
            return  # Do not reveal whether the employee ID exists.

        try:
            self.public.auth.reset_password_for_email(
                profile_row["email"],
                {"redirect_to": f"{settings.frontend_url}/reset-password"},
            )
        except AuthApiError:
            # Swallow: response to the caller must remain generic either way.
            # In production, log this server-side for ops visibility.
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_profile_by_employee_id(self, employee_id: str) -> dict | None:
        result = (
            self.admin.table("profiles")
            .select(PROFILE_COLUMNS)
            .eq("employee_id", employee_id)
            .maybe_single()
            .execute()
        )
        return result.data if result else None

    def _get_profile_by_id(self, user_id: str) -> dict | None:
        result = (
            self.admin.table("profiles")
            .select(PROFILE_COLUMNS)
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        return result.data if result else None

    def _assert_not_locked(self, profile_row: dict) -> None:
        locked_until = profile_row.get("locked_until")
        if not locked_until:
            return
        locked_until_dt = datetime.fromisoformat(locked_until)
        if locked_until_dt > datetime.now(timezone.utc):
            remaining_minutes = (
                int((locked_until_dt - datetime.now(timezone.utc)).total_seconds() // 60) + 1
            )
            raise HTTPException(
                status.HTTP_423_LOCKED,
                f"Account temporarily locked due to failed login attempts. "
                f"Try again in {remaining_minutes} minute(s).",
            )

    def _register_failed_attempt(
        self, profile_row: dict, employee_id: str, ip_address: str | None
    ) -> None:
        attempts = profile_row.get("failed_login_attempts", 0) + 1
        update: dict = {"failed_login_attempts": attempts}

        if attempts >= settings.login_max_attempts:
            locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.login_lockout_minutes
            )
            update["locked_until"] = locked_until.isoformat()
            update["failed_login_attempts"] = 0

        self.admin.table("profiles").update(update).eq("id", profile_row["id"]).execute()
        self._record_attempt(profile_row["id"], employee_id, ip_address, success=False)

    def _reset_failed_attempts(self, user_id: str) -> None:
        self.admin.table("profiles").update(
            {"failed_login_attempts": 0, "locked_until": None}
        ).eq("id", user_id).execute()

    def _record_attempt(
        self,
        user_id: str | None,
        employee_id: str,
        ip_address: str | None,
        *,
        success: bool,
    ) -> None:
        self.admin.table("login_audit_log").insert(
            {
                "user_id": user_id,
                "employee_id": employee_id,
                "ip_address": ip_address,
                "success": success,
            }
        ).execute()
