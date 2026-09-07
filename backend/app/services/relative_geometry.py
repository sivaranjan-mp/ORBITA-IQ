"""
Astrodynamics module for computing relative state, RIC (Radial / In-track / Cross-track)
frame decomposition, and encounter geometry at the Time of Closest Approach (TCA).
"""
from dataclasses import dataclass
from typing import Dict, Any, Tuple
import numpy as np


@dataclass
class EncounterGeometryResult:
    # Relative vectors (secondary - primary) in TEME frame
    relative_position_km: np.ndarray  # [x, y, z] km
    relative_velocity_km_s: np.ndarray  # [vx, vy, vz] km/s

    # Scalar magnitudes
    miss_distance_km: float
    relative_speed_km_s: float

    # RIC frame separation components (projected onto primary's orbital frame)
    radial_separation_km: float
    along_track_separation_km: float
    cross_track_separation_km: float

    # Encounter angles
    relative_velocity_angle_deg: float
    relative_inclination_deg: float

    # Derived qualitative classification: "co-orbital" | "head-on" | "crossing"
    encounter_geometry: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relative_position_x": float(self.relative_position_km[0]),
            "relative_position_y": float(self.relative_position_km[1]),
            "relative_position_z": float(self.relative_position_km[2]),
            "relative_velocity_x": float(self.relative_velocity_km_s[0]),
            "relative_velocity_y": float(self.relative_velocity_km_s[1]),
            "relative_velocity_z": float(self.relative_velocity_km_s[2]),
            "miss_distance_km": float(self.miss_distance_km),
            "relative_speed_km_s": float(self.relative_speed_km_s),
            "radial_separation_km": float(self.radial_separation_km),
            "along_track_separation_km": float(self.along_track_separation_km),
            "cross_track_separation_km": float(self.cross_track_separation_km),
            "relative_velocity_angle_deg": float(self.relative_velocity_angle_deg),
            "relative_inclination_deg": float(self.relative_inclination_deg),
            "encounter_geometry": self.encounter_geometry,
        }


def classify_encounter_geometry(
    relative_velocity_angle_deg: float,
    relative_inclination_deg: float,
    relative_speed_km_s: float,
) -> str:
    """
    Classifies encounter geometry based on physical astrodynamics parameters:
    - 'co-orbital': nearly coplanar orbits (rel inc < 5.0 deg), nearly aligned velocities
      (rel vel angle < 15.0 deg), and low relative speed (< 2.0 km/s).
    - 'head-on': opposing velocity vectors (rel vel angle >= 135.0 deg), typically high speed.
    - 'crossing': significant orbital plane intersection or crossing angle.
    """
    if (
        relative_inclination_deg < 5.0
        and relative_velocity_angle_deg < 15.0
        and relative_speed_km_s < 2.0
    ):
        return "co-orbital"
    elif relative_velocity_angle_deg >= 135.0:
        return "head-on"
    else:
        return "crossing"


def compute_relative_geometry(
    r_primary: np.ndarray,
    v_primary: np.ndarray,
    r_secondary: np.ndarray,
    v_secondary: np.ndarray,
) -> EncounterGeometryResult:
    """
    Computes precise relative state, RIC frame decomposition, and encounter geometry at TCA.

    Parameters:
    - r_primary: 3D position vector of primary object (km, TEME)
    - v_primary: 3D velocity vector of primary object (km/s, TEME)
    - r_secondary: 3D position vector of secondary object (km, TEME)
    - v_secondary: 3D velocity vector of secondary object (km/s, TEME)

    Returns:
    - EncounterGeometryResult dataclass containing relative state, RIC components,
      angular geometry, and derived classification.
    """
    r1 = np.asarray(r_primary, dtype=np.float64)
    v1 = np.asarray(v_primary, dtype=np.float64)
    r2 = np.asarray(r_secondary, dtype=np.float64)
    v2 = np.asarray(v_secondary, dtype=np.float64)

    # Step 2: Relative position and velocity (secondary - primary)
    delta_r = r2 - r1
    delta_v = v2 - v1

    miss_distance_km = float(np.linalg.norm(delta_r))
    relative_speed_km_s = float(np.linalg.norm(delta_v))

    # Step 3: RIC (Radial / In-track / Cross-track) frame construction from primary state
    # Radial unit vector r_hat: along primary position vector
    r1_norm = np.linalg.norm(r1)
    if r1_norm > 0:
        r_hat = r1 / r1_norm
    else:
        r_hat = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    # Cross-track / Normal unit vector h_hat: along primary angular momentum (r x v)
    h_primary = np.cross(r1, v1)
    h1_norm = np.linalg.norm(h_primary)
    if h1_norm > 0:
        h_hat = h_primary / h1_norm
    else:
        h_hat = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    # In-track unit vector i_hat: h_hat x r_hat (completes right-handed orthonormal basis)
    i_hat = np.cross(h_hat, r_hat)
    i_norm = np.linalg.norm(i_hat)
    if i_norm > 0:
        i_hat = i_hat / i_norm

    # Project relative position vector delta_r onto the primary RIC frame
    radial_separation_km = float(np.dot(delta_r, r_hat))
    along_track_separation_km = float(np.dot(delta_r, i_hat))
    cross_track_separation_km = float(np.dot(delta_r, h_hat))

    # Internal consistency check: sqrt(radial^2 + along_track^2 + cross_track^2) == |delta_r|
    ric_norm = np.sqrt(
        radial_separation_km ** 2 + along_track_separation_km ** 2 + cross_track_separation_km ** 2
    )
    if abs(ric_norm - miss_distance_km) > 1e-4:
        raise ValueError(
            f"RIC decomposition inconsistency: reconstructed norm {ric_norm:.6f} km "
            f"does not match miss distance {miss_distance_km:.6f} km"
        )

    # Step 4: Encounter geometry
    # Velocity vector angle between v_primary and v_secondary
    v1_norm = np.linalg.norm(v1)
    v2_norm = np.linalg.norm(v2)
    if v1_norm > 0 and v2_norm > 0:
        cos_v = np.clip(np.dot(v1, v2) / (v1_norm * v2_norm), -1.0, 1.0)
        relative_velocity_angle_deg = float(np.degrees(np.arccos(cos_v)))
    else:
        relative_velocity_angle_deg = 0.0

    # Relative inclination between orbital planes (angle between angular momentum vectors)
    h_secondary = np.cross(r2, v2)
    h2_norm = np.linalg.norm(h_secondary)
    if h1_norm > 0 and h2_norm > 0:
        cos_inc = np.clip(np.dot(h_primary, h_secondary) / (h1_norm * h2_norm), -1.0, 1.0)
        relative_inclination_deg = float(np.degrees(np.arccos(cos_inc)))
    else:
        relative_inclination_deg = 0.0

    # Derived qualitative classification
    encounter_geometry = classify_encounter_geometry(
        relative_velocity_angle_deg=relative_velocity_angle_deg,
        relative_inclination_deg=relative_inclination_deg,
        relative_speed_km_s=relative_speed_km_s,
    )

    return EncounterGeometryResult(
        relative_position_km=delta_r,
        relative_velocity_km_s=delta_v,
        miss_distance_km=miss_distance_km,
        relative_speed_km_s=relative_speed_km_s,
        radial_separation_km=radial_separation_km,
        along_track_separation_km=along_track_separation_km,
        cross_track_separation_km=cross_track_separation_km,
        relative_velocity_angle_deg=relative_velocity_angle_deg,
        relative_inclination_deg=relative_inclination_deg,
        encounter_geometry=encounter_geometry,
    )
