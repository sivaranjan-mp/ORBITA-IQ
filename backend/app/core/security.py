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

from app.core.config import get_settings

settings = get_settings()

jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"


class JWKManager:
    def __init__(self, url: str):
        self.url = url
        self._client = PyJWKClient(self.url, cache_keys=True)

    def get_signing_key(self, token: str):
        try:
            return self._client.get_signing_key_from_jwt(token)
        except PyJWKClientError:
            # Force a refetch by resetting the client instance to handle key rotation
            self._client = PyJWKClient(self.url, cache_keys=True)
            return self._client.get_signing_key_from_jwt(token)


jwk_manager = JWKManager(jwks_url)


class TokenError(Exception):
    """Raised when a bearer token fails signature, expiry, or audience checks."""


def decode_access_token(token: str) -> dict:
    try:
        # We try to get the signing key (which handles fetching and caching the JWKS).
        # If it fails, our manager refetches once automatically.
        signing_key = jwk_manager.get_signing_key(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience=settings.access_token_audience,
        )
    except (PyJWTError, PyJWKClientError) as exc:
        raise TokenError(str(exc)) from exc
