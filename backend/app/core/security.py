"""
Local verification of Supabase-issued JWTs.

Supabase signs access tokens with a project-specific HS256 secret
(found in Project Settings -> API -> JWT Secret). Verifying locally
(instead of calling Supabase on every request) avoids a network
round-trip per protected request while remaining cryptographically
sound, as long as SUPABASE_JWT_SECRET is kept secret on the backend.
"""
import jwt
from jwt import PyJWKClient, PyJWTError
from jwt.exceptions import PyJWKClientError

try:
    import cryptography  # noqa: F401
except ImportError:
    raise RuntimeError(
        "CRITICAL STARTUP FAILURE: The 'cryptography' package is missing. "
        "PyJWT requires it for validating ES256/RS256 tokens. "
        "Make sure PyJWT[crypto] is in requirements.txt."
    )

from app.core.config import get_settings

settings = get_settings()

jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"

# PyJWKClient automatically caches keys when cache_keys=True, and automatically
# performs one refetch attempt if it encounters an unrecognized 'kid' in a token.
# Transient network failures during refetch will raise a connection error, but
# importantly will NOT wipe the last known successful cache.
jwks_client = PyJWKClient(jwks_url, cache_keys=True)


class TokenError(Exception):
    """Raised when a bearer token fails signature, expiry, or audience checks."""


def decode_access_token(token: str) -> dict:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience=settings.access_token_audience,
        )
    except (PyJWTError, PyJWKClientError) as exc:
        raise TokenError(str(exc)) from exc
