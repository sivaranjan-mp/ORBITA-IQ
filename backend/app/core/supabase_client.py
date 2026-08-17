"""
Two distinct Supabase clients are used, deliberately:

- admin client (service_role key): bypasses Row Level Security. Used
  ONLY on the server to resolve employee_id -> email, manage lockouts,
  write audit logs, and read profile rows. NEVER expose this key to
  the frontend.

- public client (anon key): respects RLS and is the client used to
  actually validate a user's password via Supabase GoTrue
  (sign_in_with_password, refresh_session, reset_password_for_email).
  This ensures password verification always goes through Supabase's
  own auth engine rather than anything custom.
"""
from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings

settings = get_settings()


@lru_cache
def get_admin_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@lru_cache
def get_public_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_anon_key)
