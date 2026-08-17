"""
Local verification of Supabase-issued JWTs.

Supabase signs access tokens with a project-specific HS256 secret
(found in Project Settings -> API -> JWT Secret). Verifying locally
(instead of calling Supabase on every request) avoids a network
round-trip per protected request while remaining cryptographically
sound, as long as SUPABASE_JWT_SECRET is kept secret on the backend.
"""
import jwt
from jwt import PyJWTError

from app.core.config import get_settings

settings = get_settings()


class TokenError(Exception):
    """Raised when a bearer token fails signature, expiry, or audience checks."""


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.access_token_audience,
        )
    except PyJWTError as exc:
        raise TokenError(str(exc)) from exc
