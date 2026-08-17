"""
Smoke tests for the auth API surface.

These validate request/response contracts and status codes without
hitting a live Supabase project — Supabase clients are monkeypatched
in a full test suite via dependency overrides on get_auth_service.
Included here to show the expected testing shape for CI.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_rejects_missing_fields():
    response = client.post("/api/v1/auth/login", json={"employee_id": "EMP-0001"})
    assert response.status_code == 422


def test_login_rejects_short_password():
    response = client.post(
        "/api/v1/auth/login",
        json={"employee_id": "EMP-0001", "password": "short"},
    )
    assert response.status_code == 422


def test_me_requires_bearer_token():
    response = client.get("/api/v1/auth/me")
    assert response.status_code in (401, 403)
