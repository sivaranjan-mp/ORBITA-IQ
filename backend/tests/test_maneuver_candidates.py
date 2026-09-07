import math
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sgp4.api import Satrec

from app.main import app
from app.models.alerts import ConjunctionAlert
from app.models.catalog import CatalogSatellite
from app.models.enums import ManeuverDirection, RiskLevel
from app.models.maneuvers import ManeuverCandidate
from app.schemas.auth import UserProfile
from app.services.maneuver_candidates import (
    ALL_MANEUVER_DIRECTIONS,
    DEFAULT_MAGNITUDE_GRID_M_S,
    DEFAULT_TIMING_GRID_HOURS,
    ManeuverCandidateService,
    apply_delta_v,
    build_rtn_frame,
    propagate_perturbed_arc,
    refine_candidate_tca,
    sgp4_state_at_datetime,
    two_body_j2_dynamics,
)

client = TestClient(app)

# Sample TLEs for testing
ISS_LINE1 = "1 25544U 98067A   26250.12345678  .00016717  00000+0  10270-3 0  9001"
ISS_LINE2 = "2 25544  51.6400 208.1234 0001000 120.1234 240.1234 15.49876543123456"

# Synthetic companion object TLE
DEB_LINE1 = "1 99001U 20001A   26250.12345678  .00010000  00000+0  10000-3 0  9002"
DEB_LINE2 = "2 99001  51.6420 208.1250 0001000 120.1250 240.1250 15.49876543123457"


# ============================================================================
# 1. RTN Frame Construction Unit Tests
# ============================================================================

def test_build_rtn_frame_equatorial_circular():
    """
    In an equatorial circular orbit with r = [7000, 0, 0] km and v = [0, 7.5, 0] km/s:
    - R_hat should be [1, 0, 0]
    - N_hat should be [0, 0, 1] (angular momentum in +Z)
    - T_hat should be [0, 1, 0] (along-track in +Y)
    """
    r = np.array([7000.0, 0.0, 0.0])
    v = np.array([0.0, 7.5, 0.0])

    r_hat, t_hat, n_hat = build_rtn_frame(r, v)

    np.testing.assert_allclose(r_hat, [1.0, 0.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(t_hat, [0.0, 1.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(n_hat, [0.0, 0.0, 1.0], atol=1e-12)


def test_build_rtn_frame_orthonormality_arbitrary_orbit():
    """
    Verifies that for an arbitrary inclined elliptic orbit, the RTN triad is strictly
    orthonormal and right-handed: R x T = N, T x N = R, N x R = T.
    """
    r = np.array([4500.0, -3200.0, 3800.0])
    v = np.array([2.1, 5.8, -4.2])

    r_hat, t_hat, n_hat = build_rtn_frame(r, v)

    # Unit norms
    assert math.isclose(float(np.linalg.norm(r_hat)), 1.0, rel_tol=1e-12)
    assert math.isclose(float(np.linalg.norm(t_hat)), 1.0, rel_tol=1e-12)
    assert math.isclose(float(np.linalg.norm(n_hat)), 1.0, rel_tol=1e-12)

    # Mutually orthogonal
    assert abs(float(np.dot(r_hat, t_hat))) < 1e-12
    assert abs(float(np.dot(r_hat, n_hat))) < 1e-12
    assert abs(float(np.dot(t_hat, n_hat))) < 1e-12

    # Right-handed cross products
    np.testing.assert_allclose(np.cross(r_hat, t_hat), n_hat, atol=1e-12)
    np.testing.assert_allclose(np.cross(t_hat, n_hat), r_hat, atol=1e-12)
    np.testing.assert_allclose(np.cross(n_hat, r_hat), t_hat, atol=1e-12)


def test_build_rtn_frame_degenerate_cases():
    """Tests error handling for zero norm position or collinear r and v."""
    with pytest.raises(ValueError, match="Position vector norm is too small"):
        build_rtn_frame(np.array([0.0, 0.0, 0.0]), np.array([0.0, 7.5, 0.0]))

    with pytest.raises(ValueError, match="Velocity and position vectors are collinear"):
        build_rtn_frame(np.array([7000.0, 0.0, 0.0]), np.array([7.5, 0.0, 0.0]))


# ============================================================================
# 2. Delta-V Application & Sign Convention Tests
# ============================================================================

def test_apply_delta_v_radial_positive():
    """Positive radial burn adds velocity in the +R_hat direction."""
    r = np.array([6800.0, 0.0, 0.0])
    v = np.array([0.0, 7.6, 0.0])
    mag_m_s = 0.5

    r_pert, v_pert, comps = apply_delta_v(r, v, ManeuverDirection.RADIAL_POSITIVE, mag_m_s)

    r_hat, _, _ = build_rtn_frame(r, v)
    delta_v_vec = v_pert - v

    np.testing.assert_allclose(r_pert, r)
    assert comps["delta_v_r_m_s"] == 0.5
    assert comps["delta_v_t_m_s"] == 0.0
    assert comps["delta_v_n_m_s"] == 0.0
    # Positive dot product along R
    assert float(np.dot(delta_v_vec, r_hat)) > 0
    assert math.isclose(float(np.linalg.norm(delta_v_vec)), 0.5 / 1000.0, rel_tol=1e-9)


def test_apply_delta_v_radial_negative():
    """Negative radial burn adds velocity in the -R_hat direction."""
    r = np.array([6800.0, 0.0, 0.0])
    v = np.array([0.0, 7.6, 0.0])
    mag_m_s = 1.0

    r_pert, v_pert, comps = apply_delta_v(r, v, ManeuverDirection.RADIAL_NEGATIVE, mag_m_s)

    r_hat, _, _ = build_rtn_frame(r, v)
    delta_v_vec = v_pert - v

    assert comps["delta_v_r_m_s"] == -1.0
    assert float(np.dot(delta_v_vec, r_hat)) < 0
    assert math.isclose(float(np.linalg.norm(delta_v_vec)), 1.0 / 1000.0, rel_tol=1e-9)


def test_apply_delta_v_along_track_directions():
    """
    along_track_later is prograde (+T_hat), along_track_earlier is retrograde (-T_hat).
    """
    r = np.array([6800.0, 0.0, 0.0])
    v = np.array([0.0, 7.6, 0.0])
    _, t_hat, _ = build_rtn_frame(r, v)

    # Prograde (later)
    _, v_later, comps_later = apply_delta_v(r, v, ManeuverDirection.ALONG_TRACK_LATER, 2.0)
    assert comps_later["delta_v_t_m_s"] == 2.0
    assert float(np.dot(v_later - v, t_hat)) > 0

    # Retrograde (earlier)
    _, v_earlier, comps_earlier = apply_delta_v(r, v, ManeuverDirection.ALONG_TRACK_EARLIER, 2.0)
    assert comps_earlier["delta_v_t_m_s"] == -2.0
    assert float(np.dot(v_earlier - v, t_hat)) < 0


def test_apply_delta_v_cross_track_directions():
    """
    cross_track_positive is normal (+N_hat), cross_track_negative is south (-N_hat).
    """
    r = np.array([6800.0, 0.0, 0.0])
    v = np.array([0.0, 7.6, 0.0])
    _, _, n_hat = build_rtn_frame(r, v)

    # Positive cross-track (+N)
    _, v_pos, comps_pos = apply_delta_v(r, v, ManeuverDirection.CROSS_TRACK_POSITIVE, 0.5)
    assert comps_pos["delta_v_n_m_s"] == 0.5
    assert float(np.dot(v_pos - v, n_hat)) > 0

    # Negative cross-track (-N)
    _, v_neg, comps_neg = apply_delta_v(r, v, ManeuverDirection.CROSS_TRACK_NEGATIVE, 0.5)
    assert comps_neg["delta_v_n_m_s"] == -0.5
    assert float(np.dot(v_neg - v, n_hat)) < 0


# ============================================================================
# 3. Two-Body + J2 Dynamics & Numerical Propagator Tests
# ============================================================================

def test_two_body_j2_dynamics_derivatives():
    """Verifies that the dynamics function computes valid finite derivatives."""
    y = np.array([7000.0, 0.0, 0.0, 0.0, 7.546, 0.0])
    dydt = two_body_j2_dynamics(0.0, y)

    # Velocities match
    np.testing.assert_allclose(dydt[0:3], [0.0, 7.546, 0.0])

    # Radial acceleration is inward (negative X)
    assert dydt[3] < 0
    assert math.isfinite(dydt[3])
    assert math.isfinite(dydt[4])
    assert math.isfinite(dydt[5])


def test_propagate_perturbed_arc_conservation():
    """
    Verifies that numerical propagation over 1 orbital period (~5400s) maintains
    the orbit radius within expected small bounds for a circular orbit.
    """
    # Circular LEO orbit ~400km altitude -> r = 6778 km, v = ~7.67 km/s
    r0 = np.array([6778.0, 0.0, 0.0])
    v0 = np.array([0.0, 7.67, 0.0])

    trajectory = propagate_perturbed_arc(r0, v0, duration_seconds=5400.0)

    # Evaluate at t=0
    r_start, v_start = trajectory(0.0)
    np.testing.assert_allclose(r_start, r0, atol=1e-6)

    # Evaluate at 1 period
    r_end, v_end = trajectory(5400.0)
    r_end_norm = float(np.linalg.norm(r_end))
    assert math.isclose(r_end_norm, 6778.0, rel_tol=0.01)


def test_physics_along_track_prograde_increases_period():
    """
    Prograde burn increases semi-major axis, which means the satellite moves slower
    in true anomaly, ending up lagging (behind in phase) compared to unperturbed orbit.
    """
    r0 = np.array([6800.0, 0.0, 0.0])
    v0 = np.array([0.0, 7.65, 0.0])

    # Unperturbed
    unperturbed = propagate_perturbed_arc(r0, v0, duration_seconds=5000.0)
    r_unp, _ = unperturbed(5000.0)

    # Prograde +10 m/s
    r_pert, v_pert, _ = apply_delta_v(r0, v0, ManeuverDirection.ALONG_TRACK_LATER, 10.0)
    prograde = propagate_perturbed_arc(r_pert, v_pert, duration_seconds=5000.0)
    r_prog, _ = prograde(5000.0)

    # Positions should diverge over time
    dist_diff = np.linalg.norm(r_prog - r_unp)
    assert dist_diff > 1.0  # Significant difference (> 1 km separation)


# ============================================================================
# 4. End-to-End Maneuver Candidate Generation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_maneuver_candidate_generator_synthetic_conjunction():
    """
    End-to-end test generating candidate maneuvers for an alert with synthetic Satrecs.
    Verifies candidate count, efficiency ranking, and metric outputs.
    """
    satrec_iss = Satrec.twoline2rv(ISS_LINE1, ISS_LINE2)
    satrec_deb = Satrec.twoline2rv(DEB_LINE1, DEB_LINE2)

    now = datetime.now(timezone.utc)
    tca = now + timedelta(hours=18.0)
    alert_id = uuid.uuid4()

    mock_alert = ConjunctionAlert(
        id=alert_id,
        satellite_a_norad_id=25544,
        satellite_a_name="ISS (ZARYA)",
        satellite_b_norad_id=99001,
        satellite_b_name="SYNTHETIC-DEB",
        screening_scope="fleet_vs_catalog",
        tca=tca,
        miss_distance_km=0.35,
        miss_distance_m=350.0,
        relative_velocity_km_s=11.2,
        probability=0.00045,
        risk_level="critical",
        status="open",
        detected_by="satguard",
        computed_at=now,
    )

    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = mock_alert
    db.execute.return_value = mock_res

    service = ManeuverCandidateService(db)

    # Use a compact grid for test speed: 6 directions x 2 magnitudes x 2 timings = 24 candidates
    custom_mags = [0.1, 1.0]
    custom_timings = [12.0, 6.0]

    result = await service.generate_candidates_for_alert(
        alert_id=alert_id,
        magnitude_grid_m_s=custom_mags,
        timing_grid_hours=custom_timings,
        save_to_db=False,
        primary_satrec_override=satrec_iss,
        secondary_satrec_override=satrec_deb,
    )

    assert result["alert_id"] == str(alert_id)
    assert result["total_candidates"] == 24
    candidates = result["candidates"]
    assert len(candidates) == 24

    # Verify candidates are sorted by efficiency descending
    efficiencies = [c["efficiency_m_per_m_s"] for c in candidates]
    assert efficiencies == sorted(efficiencies, reverse=True)

    # Verify candidate fields
    top_cand = candidates[0]
    assert top_cand["direction"] in [d.value for d in ALL_MANEUVER_DIRECTIONS]
    assert top_cand["delta_v_m_s"] in custom_mags
    assert top_cand["time_before_tca_hours"] in custom_timings
    assert top_cand["resulting_miss_distance_m"] > 0
    assert "critical" in top_cand["risk_level_change"]
    assert top_cand["fuel_cost_proxy_m_s"] == top_cand["delta_v_m_s"]


@pytest.mark.asyncio
async def test_get_saved_candidates_for_alert():
    """Tests fetching previously saved candidate records."""
    alert_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_alert = ConjunctionAlert(
        id=alert_id,
        satellite_a_norad_id=25544,
        satellite_a_name="ISS (ZARYA)",
        satellite_b_norad_id=99001,
        satellite_b_name="SYNTHETIC-DEB",
        screening_scope="fleet_vs_catalog",
        tca=now + timedelta(hours=12.0),
        miss_distance_km=0.5,
        miss_distance_m=500.0,
        relative_velocity_km_s=10.0,
        probability=0.0001,
        risk_level="high",
        status="open",
        detected_by="satguard",
        computed_at=now,
    )

    mock_candidate = ManeuverCandidate(
        id=uuid.uuid4(),
        alert_id=alert_id,
        direction="along_track_later",
        delta_v_m_s=0.5,
        delta_v_r_m_s=0.0,
        delta_v_t_m_s=0.5,
        delta_v_n_m_s=0.0,
        burn_epoch=now + timedelta(hours=6.0),
        time_before_tca_hours=6.0,
        resulting_tca=now + timedelta(hours=12.0),
        resulting_miss_distance_m=12500.0,
        resulting_miss_distance_km=12.5,
        resulting_relative_velocity_km_s=10.0,
        resulting_probability=1e-7,
        resulting_risk_level="low",
        miss_distance_improvement_m=12000.0,
        risk_level_change="high -> low",
        efficiency_m_per_m_s=24000.0,
        fuel_cost_proxy_m_s=0.5,
        created_at=now,
        updated_at=now,
    )

    db = AsyncMock()
    mock_res_alert = MagicMock()
    mock_res_alert.scalars.return_value.first.return_value = mock_alert

    mock_res_cand = MagicMock()
    mock_res_cand.scalars.return_value.all.return_value = [mock_candidate]

    db.execute.side_effect = [mock_res_alert, mock_res_cand]

    service = ManeuverCandidateService(db)
    result = await service.get_saved_candidates_for_alert(alert_id)

    assert result is not None
    assert result["alert_id"] == str(alert_id)
    assert result["total_candidates"] == 1
    assert result["candidates"][0]["direction"] == "along_track_later"
    assert result["candidates"][0]["efficiency_m_per_m_s"] == 24000.0


# ============================================================================
# 5. API Endpoint Tests
# ============================================================================

def test_maneuver_candidates_endpoint_unauthenticated():
    """Validates that endpoint requires authentication."""
    response = client.post(f"/api/v1/alerts/{uuid.uuid4()}/maneuver-candidates")
    assert response.status_code in (401, 403)


def test_maneuver_candidates_invalid_uuid():
    """Validates 400 or 422 on invalid UUID formatting."""
    response = client.post("/api/v1/alerts/invalid-uuid-string/maneuver-candidates")
    assert response.status_code in (400, 422, 401, 403)


def test_generate_maneuver_candidates_endpoint_authenticated():
    """Validates POST endpoint execution with mocked operator user and mock DB."""
    from app.dependencies import get_current_user
    from app.db.session import get_db

    operator_user = UserProfile(
        id="user-123",
        employee_id="OP-001",
        email="operator@orbita-iq.com",
        full_name="Orbit Operator",
        role="operator",
        is_active=True,
    )

    alert_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    tca = now + timedelta(hours=12.0)

    mock_alert = ConjunctionAlert(
        id=alert_id,
        satellite_a_norad_id=25544,
        satellite_a_name="ISS (ZARYA)",
        satellite_b_norad_id=99001,
        satellite_b_name="SYNTHETIC-DEB",
        screening_scope="fleet_vs_catalog",
        tca=tca,
        miss_distance_km=0.4,
        miss_distance_m=400.0,
        relative_velocity_km_s=11.0,
        probability=0.0002,
        risk_level="critical",
        status="open",
        detected_by="satguard",
        computed_at=now,
    )

    sat_a = CatalogSatellite(
        norad_id=25544,
        name="ISS (ZARYA)",
        line1=ISS_LINE1,
        line2=ISS_LINE2,
    )
    sat_b = CatalogSatellite(
        norad_id=99001,
        name="SYNTHETIC-DEB",
        line1=DEB_LINE1,
        line2=DEB_LINE2,
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_res_alert = MagicMock()
    mock_res_alert.scalars.return_value.first.return_value = mock_alert

    mock_res_a = MagicMock()
    mock_res_a.scalars.return_value.first.return_value = sat_a

    mock_res_b = MagicMock()
    mock_res_b.scalars.return_value.first.return_value = sat_b

    mock_db.execute.side_effect = [
        mock_res_alert,
        mock_res_a,
        mock_res_b,
        MagicMock(),  # delete old candidates
    ]

    app.dependency_overrides[get_current_user] = lambda: operator_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        payload = {
            "magnitude_grid_m_s": [0.05, 0.5],
            "timing_grid_hours": [6.0],
            "directions": ["along_track_later", "radial_positive"],
            "save_to_db": True,
        }
        response = client.post(
            f"/api/v1/alerts/{alert_id}/maneuver-candidates",
            json=payload,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["alert_id"] == str(alert_id)
        assert data["primary_satellite_name"] == "ISS (ZARYA)"
        assert data["total_candidates"] == 4  # 2 directions x 2 mags x 1 timing
        assert len(data["candidates"]) == 4
        assert data["candidates"][0]["efficiency_m_per_m_s"] >= data["candidates"][1]["efficiency_m_per_m_s"]
    finally:
        app.dependency_overrides.clear()


def test_get_maneuver_candidates_endpoint_authenticated():
    """Validates GET endpoint execution returning previously computed candidates."""
    from app.dependencies import get_current_user
    from app.db.session import get_db

    operator_user = UserProfile(
        id="user-123",
        employee_id="OP-001",
        email="operator@orbita-iq.com",
        full_name="Orbit Operator",
        role="operator",
        is_active=True,
    )

    alert_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_alert = ConjunctionAlert(
        id=alert_id,
        satellite_a_norad_id=25544,
        satellite_a_name="ISS (ZARYA)",
        satellite_b_norad_id=99001,
        satellite_b_name="SYNTHETIC-DEB",
        screening_scope="fleet_vs_catalog",
        tca=now + timedelta(hours=12.0),
        miss_distance_km=0.5,
        miss_distance_m=500.0,
        relative_velocity_km_s=10.0,
        probability=0.0001,
        risk_level="high",
        status="open",
        detected_by="satguard",
        computed_at=now,
    )

    mock_cand = ManeuverCandidate(
        id=uuid.uuid4(),
        alert_id=alert_id,
        direction="along_track_later",
        delta_v_m_s=0.5,
        delta_v_r_m_s=0.0,
        delta_v_t_m_s=0.5,
        delta_v_n_m_s=0.0,
        burn_epoch=now + timedelta(hours=6.0),
        time_before_tca_hours=6.0,
        resulting_tca=now + timedelta(hours=12.0),
        resulting_miss_distance_m=12500.0,
        resulting_miss_distance_km=12.5,
        resulting_relative_velocity_km_s=10.0,
        resulting_probability=1e-7,
        resulting_risk_level="low",
        miss_distance_improvement_m=12000.0,
        risk_level_change="high -> low",
        efficiency_m_per_m_s=24000.0,
        fuel_cost_proxy_m_s=0.5,
        created_at=now,
        updated_at=now,
    )

    mock_db = AsyncMock()
    mock_res_alert = MagicMock()
    mock_res_alert.scalars.return_value.first.return_value = mock_alert

    mock_res_cand = MagicMock()
    mock_res_cand.scalars.return_value.all.return_value = [mock_cand]

    mock_db.execute.side_effect = [mock_res_alert, mock_res_cand]

    app.dependency_overrides[get_current_user] = lambda: operator_user
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = client.get(f"/api/v1/alerts/{alert_id}/maneuver-candidates")
        assert response.status_code == 200
        data = response.json()
        assert data["alert_id"] == str(alert_id)
        assert data["total_candidates"] == 1
        assert data["candidates"][0]["direction"] == "along_track_later"
    finally:
        app.dependency_overrides.clear()


