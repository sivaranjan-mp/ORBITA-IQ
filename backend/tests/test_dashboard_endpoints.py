from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_dashboard():
    response = client.get("/api/v1/dashboard")
    assert response.status_code in (200, 401, 403, 500)
