import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.api.v1.endpoints.alerts import _format_alerts_with_quality, get_alerts
from app.models.alerts import ConjunctionAlert
from app.models.catalog import CatalogSatellite
from app.schemas.auth import UserProfile

client = TestClient(app)


def test_get_alerts_unauthenticated():
    response = client.get("/api/v1/alerts")
    assert response.status_code in (401, 403)
    assert response.status_code != 500


def test_update_alert_status_invalid_status():
    response = client.put("/api/v1/alerts/123/status",
                          json={"status": "invalid_status"})
    assert response.status_code in (400, 422, 401, 403)
    assert response.status_code != 500


@pytest.mark.asyncio
async def test_format_alerts_with_quality_mixed_data():
    now = datetime.now(timezone.utc)

    # 1. Alert with ISS (known catalog) vs SYNTHETIC-DEB (untracked object)
    alert = ConjunctionAlert(
        id=uuid.uuid4(),
        satellite_a_norad_id=25544,
        satellite_a_name="ISS (ZARYA)",
        satellite_b_norad_id=99001,
        satellite_b_name="SYNTHETIC-DEB-ALPHA",
        screening_scope="fleet_vs_catalog",
        tca=now + timedelta(hours=12),
        miss_distance_km=0.45,
        miss_distance_m=450.0,
        relative_velocity_km_s=11.2,
        probability=0.00045,
        risk_level="critical",
        status="open",
        detected_by="satguard",
        computed_at=now,
    )

    cat_sat = CatalogSatellite(
        norad_id=25544,
        name="ISS (ZARYA)",
        epoch=now - timedelta(hours=3.0),
        orbit_regime="LEO",
        eccentricity=0.0001,
        apogee_km=420.0,
        perigee_km=415.0,
        inclination_deg=51.64,
        line1="1 25544U 98067A   26250.12345678  .00016717  00000+0  10270-3 0  9001",
        line2="2 25544  51.6400 208.1234 0001000 120.1234 240.1234 15.49876543123456",
    )

    db = AsyncMock()

    # Mock DB queries:
    # 1) ISS: get_active_params -> None, fleet sat -> None, catalog sat -> cat_sat
    # 2) SYNTHETIC-DEB (99001): fleet sat -> None, catalog sat -> None
    mock_res_params = MagicMock()
    mock_res_params.scalars.return_value.first.return_value = None
    mock_res_none = MagicMock()
    mock_res_none.scalars.return_value.first.return_value = None
    mock_res_iss = MagicMock()
    mock_res_iss.scalars.return_value.first.return_value = cat_sat

    db.execute = AsyncMock(side_effect=[
        mock_res_params,
        mock_res_none,
        mock_res_iss,
        mock_res_none,
        mock_res_none,
    ])

    formatted = await _format_alerts_with_quality([alert], db)
    assert len(formatted) == 1
    item = formatted[0]

    # Primary should have real quality bundle
    pri_dq = item["primaryDataQuality"]
    assert pri_dq is not None
    assert pri_dq.source_code == "CELESTRAK"
    assert pri_dq.is_authoritative is True
    assert pri_dq.data_quality == "HIGH"
    assert pri_dq.freshness_tier == "FRESH"

    # Secondary (untracked 99001) should degrade gracefully to insufficient data bundle
    sec_dq = item["secondaryDataQuality"]
    assert sec_dq is not None
    assert sec_dq.source_code == "UNKNOWN"
    assert sec_dq.data_quality == "UNRELIABLE"
    assert sec_dq.freshness_tier == "CRITICAL"
    assert sec_dq.confidence_score == 5.0
    assert "Insufficient" in sec_dq.propagation_model or "Unavailable" in sec_dq.propagation_model

