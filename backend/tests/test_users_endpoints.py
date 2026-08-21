from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_users_requires_auth():
    response = client.get("/api/v1/users")
    assert response.status_code in (401, 403)


def test_create_user_requires_auth():
    response = client.post("/api/v1/users", json={
        "email": "test@example.com",
        "password": "password123",
        "employee_id": "EMP-9999",
        "full_name": "Test User",
        "role": "operator"
    })
    assert response.status_code in (401, 403)


def test_update_user_requires_auth():
    response = client.patch("/api/v1/users/123", json={"role": "admin"})
    assert response.status_code in (401, 403)


def test_deactivate_user_requires_auth():
    response = client.delete("/api/v1/users/123")
    assert response.status_code in (401, 403)
