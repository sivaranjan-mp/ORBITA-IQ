from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.core.limiter import limiter
from app.dependencies import get_current_user
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
    UserProfile,
)
from app.services.auth_service import GENERIC_RESET_MESSAGE, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def get_auth_service() -> AuthService:
    return AuthService()


@router.post("/login", response_model=TokenResponse, summary="Log in with Employee ID + password")
@limiter.limit(settings.rate_limit_login)
async def login(
    request: Request,
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    client_ip = request.client.host if request.client else None
    return service.login(payload, client_ip)


@router.post("/refresh", response_model=TokenResponse, summary="Exchange a refresh token for a new session")
async def refresh(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.refresh(payload.refresh_token)


@router.post("/logout", response_model=MessageResponse, summary="Revoke the current session")
async def logout(
    payload: LogoutRequest,
    _user: UserProfile = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    if payload.refresh_token:
        service.logout(payload.refresh_token)
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserProfile, summary="Get the current authenticated user's profile")
async def me(user: UserProfile = Depends(get_current_user)):
    return user


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    summary="Request a password reset email by Employee ID",
)
@limiter.limit(settings.rate_limit_password_reset)
async def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    service: AuthService = Depends(get_auth_service),
):
    service.request_password_reset(payload)
    # Always return the same generic message — do not reveal whether the
    # employee ID exists in the system.
    return MessageResponse(message=GENERIC_RESET_MESSAGE)
