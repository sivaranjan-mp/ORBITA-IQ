from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.auth import UserProfile

client = TestClient(app)


def test_get_dashboard_unauthenticated():
    app.dependency_overrides.clear()
    response = client.get("/api/v1/dashboard")
    assert response.status_code in (401, 403)


def test_get_dashboard_with_altitude_trend():
    app.dependency_overrides.clear()
    
    mock_user = UserProfile(
        id="user-123",
        employee_id="EMP-0001",
        email="operator@orbita.ai",
        full_name="Orbit Operator",
        role="operator",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_db = AsyncMock()
    
    # Mock queries:
    # 1. count(Satellite.id) -> 614
    # 2. count(ConjunctionAlert.id) -> 5
    # 3. active alerts count -> 3
    # 4. high risk alerts count -> 1
    # 5. next alert -> None
    # 6. avg(OrbitState.altitude_km) -> 645.2
    
    m_sat_count = MagicMock()
    m_sat_count.scalar.return_value = 614

    m_conj_count = MagicMock()
    m_conj_count.scalar.return_value = 5

    m_active = MagicMock()
    m_active.scalar.return_value = 3

    m_high = MagicMock()
    m_high.scalar.return_value = 1

    m_next = MagicMock()
    m_next.scalar_one_or_none.return_value = None

    m_avg_alt = MagicMock()
    m_avg_alt.scalar.return_value = 645.2

    mock_db.execute.side_effect = [
        m_sat_count,
        m_conj_count,
        m_active,
        m_high,
        m_next,
        m_avg_alt,
    ]
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    data = response.json()

    assert data["tracked_satellites"] == 614
    assert data["active_alerts"] == 3
    assert data["high_risk_alerts"] == 1
    assert "altitude_trend" in data
    assert isinstance(data["altitude_trend"], list)
    assert len(data["altitude_trend"]) == 14

    # Verify structure of each trend item
    for item in data["altitude_trend"]:
        assert "day" in item
        assert "altitudeKm" in item
        assert isinstance(item["altitudeKm"], (int, float))
        assert item["altitudeKm"] > 0

