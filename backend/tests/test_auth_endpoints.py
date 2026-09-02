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
    response = client.post("/api/v1/auth/login",
                           json={"employee_id": "EMP-0001"})
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


def test_update_me_authenticated():
    from unittest.mock import MagicMock, patch
    from app.dependencies import get_current_user
    from app.schemas.auth import UserProfile

    user = UserProfile(
        id="user-123",
        employee_id="EMP-0001",
        full_name="Original Name",
        role="operator",
        department="Operations",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        mock_admin = MagicMock()
        mock_res = MagicMock()
        mock_res.data = [{
            "id": "user-123",
            "employee_id": "EMP-0001",
            "full_name": "Updated Name",
            "role": "operator",
            "department": "Engineering",
            "is_active": True,
            "last_login_at": None,
        }]
        mock_admin.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_res

        with patch("app.api.v1.endpoints.auth.get_admin_client", return_value=mock_admin):
            response = client.patch(
                "/api/v1/auth/me",
                json={"full_name": "Updated Name", "department": "Engineering"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["full_name"] == "Updated Name"
            assert data["department"] == "Engineering"
    finally:
        app.dependency_overrides.clear()

