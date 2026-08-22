"""
Centralized application settings.

All values are loaded from environment variables (see .env.example).
Using pydantic-settings gives us validation + type coercion + a single
source of truth instead of scattered os.environ.get() calls.
"""
from functools import lru_cache
from typing import Union, Annotated

from pydantic import model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


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
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, list[str]]) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_cors(self) -> "Settings":
        if self.environment == "production":
            is_invalid = (
                not self.cors_origins or
                any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origins)
            )
            if is_invalid:
                raise ValueError(
                    "CORS_ORIGINS must be explicitly set to real origins in production.")
        return self

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
    kwargs: dict = {}
    return Settings(**kwargs)
