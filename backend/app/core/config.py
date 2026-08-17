"""
Centralized application settings.

All values are loaded from environment variables (see .env.example).
Using pydantic-settings gives us validation + type coercion + a single
source of truth instead of scattered os.environ.get() calls.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- Supabase ----
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # ---- App ----
    environment: str = "development"
    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]

    # ---- Auth / JWT ----
    access_token_audience: str = "authenticated"

    # ---- Account lockout policy ----
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # ---- Rate limiting ----
    rate_limit_login: str = "10/minute"
    rate_limit_password_reset: str = "5/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
