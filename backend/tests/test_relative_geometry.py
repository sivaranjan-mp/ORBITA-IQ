import numpy as np
import pytest
from app.services.relative_geometry import (
    compute_relative_geometry,
    classify_encounter_geometry,
    EncounterGeometryResult,
)


def test_ric_decomposition_orthonormal_and_reconstruction():
    """
    Validates that the RIC basis is orthonormal and reconstructs the Euclidean miss distance.
    """
    # Primary in 400km circular orbit moving primarily in y-direction
    r_prim = np.array([6778.0, 0.0, 0.0])
    v_prim = np.array([0.0, 7.67, 0.0])

    # Secondary offset by 0.2 km in radial, 0.4 km in-track, 0.3 km cross-track
    # True miss distance should be sqrt(0.2^2 + 0.4^2 + 0.3^2) = sqrt(0.04 + 0.16 + 0.09) = sqrt(0.29) ~= 0.538516 km
    r_sec = r_prim + np.array([0.2, 0.4, 0.3])
    v_sec = v_prim + np.array([0.001, -0.002, 0.0015])

    res = compute_relative_geometry(r_prim, v_prim, r_sec, v_sec)

    expected_miss = np.linalg.norm(r_sec - r_prim)
    assert pytest.approx(res.miss_distance_km, rel=1e-5) == expected_miss
    assert pytest.approx(res.radial_separation_km, abs=1e-4) == 0.2
    assert pytest.approx(res.along_track_separation_km, abs=1e-4) == 0.4
    assert pytest.approx(res.cross_track_separation_km, abs=1e-4) == 0.3

    # Pythagorean consistency
    ric_norm = np.sqrt(
        res.radial_separation_km**2
        + res.along_track_separation_km**2
        + res.cross_track_separation_km**2
    )
    assert pytest.approx(ric_norm, abs=1e-5) == res.miss_distance_km


def test_geometry_classification_co_orbital():
    """
    Validates classification of low-angle, low-speed co-orbital encounters.
    """
    r_prim = np.array([6778.0, 0.0, 0.0])
    v_prim = np.array([0.0, 7.67, 0.0])

    # Nearly identical state (slight in-track offset)
    r_sec = r_prim + np.array([0.01, 0.5, 0.0])
    v_sec = v_prim + np.array([0.0, 0.001, 0.0])

    res = compute_relative_geometry(r_prim, v_prim, r_sec, v_sec)
    assert res.encounter_geometry == "co-orbital"
    assert res.relative_velocity_angle_deg < 5.0
    assert res.relative_inclination_deg < 5.0


def test_geometry_classification_crossing():
    """
    Validates classification of cross-plane orbital encounters.
    """
    r_prim = np.array([6778.0, 0.0, 0.0])
    v_prim = np.array([0.0, 7.67, 0.0])

    # Secondary in an inclined plane crossing at an angle (~60 deg)
    r_sec = r_prim + np.array([0.1, 0.2, 0.3])
    # Velocity tilted by ~60 degrees into the z direction
    v_sec = np.array([0.0, 7.67 * 0.5, 7.67 * np.sqrt(3) / 2])

    res = compute_relative_geometry(r_prim, v_prim, r_sec, v_sec)
    assert res.encounter_geometry == "crossing"
    assert res.relative_velocity_angle_deg > 30.0
    assert res.relative_inclination_deg > 30.0


def test_geometry_classification_head_on():
    """
    Validates classification of counter-propagating head-on encounters.
    """
    r_prim = np.array([6778.0, 0.0, 0.0])
    v_prim = np.array([0.0, 7.67, 0.0])

    r_sec = r_prim + np.array([0.05, 0.1, 0.0])
    v_sec = np.array([0.0, -7.67, 0.0])  # Retrograde relative to primary

    res = compute_relative_geometry(r_prim, v_prim, r_sec, v_sec)
    assert res.encounter_geometry == "head-on"
    assert res.relative_velocity_angle_deg >= 135.0
    assert res.relative_speed_km_s > 14.0
