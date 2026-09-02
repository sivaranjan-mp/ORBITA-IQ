import pytest
from app.core.config import Settings

def test_cors_origins_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://my-app.vercel.app,https://other.com")
    monkeypatch.setenv("SUPABASE_URL", "test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test")
    
    settings = Settings()
    assert settings.cors_origins == ["https://my-app.vercel.app", "https://other.com"]

def test_cors_origins_json_array(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://my-app.vercel.app", "https://other.com"]')
    monkeypatch.setenv("SUPABASE_URL", "test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test")
    
    settings = Settings()
    assert settings.cors_origins == ["https://my-app.vercel.app", "https://other.com"]

def test_cors_origins_empty_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "")
    monkeypatch.setenv("SUPABASE_URL", "test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test")
    
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:5173"]

def test_cors_origins_single_plain_origin(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://orbita-iq.vercel.app")
    monkeypatch.setenv("SUPABASE_URL", "test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test")
    
    settings = Settings()
    assert settings.cors_origins == ["https://orbita-iq.vercel.app"]

def test_cors_origins_production_empty_raises(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SUPABASE_URL", "test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test")
    
    with pytest.raises(ValueError, match="CORS_ORIGINS must be explicitly set to real origins in production"):
        Settings()
