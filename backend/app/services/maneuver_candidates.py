import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import minimize_scalar
from sgp4.api import Satrec
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import (
    MU_EARTH_KM3_S2,
    WGS84_EARTH_RADIUS_KM,
)
from app.models.alerts import ConjunctionAlert
from app.models.catalog import CatalogSatellite
from app.models.enums import ManeuverDirection, RiskLevel
from app.models.maneuvers import ManeuverCandidate
from app.models.satellites import Satellite, TLERecord
from app.services.conjunction_engine import ConjunctionEngine
from app.services.probability_engine import ProbabilityEngine

logger = logging.getLogger(__name__)

# Astrodynamics Constants
J2_EARTH = 1.08262668e-3  # Earth's second zonal harmonic J2
DEFAULT_MAGNITUDE_GRID_M_S = [0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
DEFAULT_TIMING_GRID_HOURS = [24.0, 12.0, 6.0, 2.0, 1.0]

ALL_MANEUVER_DIRECTIONS = [
    ManeuverDirection.ALONG_TRACK_EARLIER,
    ManeuverDirection.ALONG_TRACK_LATER,
    ManeuverDirection.RADIAL_POSITIVE,
    ManeuverDirection.RADIAL_NEGATIVE,
    ManeuverDirection.CROSS_TRACK_POSITIVE,
    ManeuverDirection.CROSS_TRACK_NEGATIVE,
]


def build_rtn_frame(r_eci: np.ndarray, v_eci: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Constructs the orthonormal Radial / Transverse / Normal (RTN) basis from Cartesian ECI state (r, v).
    r_eci in km, v_eci in km/s.

    - Radial (R): r̂ = r / |r| (pointing outward from Earth center)
    - Normal (N): (r × v) / |r × v| (orbit angular momentum / cross-track normal)
    - Transverse (T): N × R (along-track / in orbital plane)

    Returns:
        (r_hat, t_hat, n_hat): 3D unit numpy arrays forming an orthonormal right-handed triad.
    """
    r_arr = np.asarray(r_eci, dtype=np.float64)
    v_arr = np.asarray(v_eci, dtype=np.float64)

    r_norm = np.linalg.norm(r_arr)
    if r_norm < 1e-6:
        raise ValueError("Position vector norm is too small to construct RTN frame.")

    r_hat = r_arr / r_norm

    h_vec = np.cross(r_arr, v_arr)
    h_norm = np.linalg.norm(h_vec)
    if h_norm < 1e-6:
        raise ValueError("Velocity and position vectors are collinear; cannot construct orbital plane normal.")

    n_hat = h_vec / h_norm
    t_hat = np.cross(n_hat, r_hat)

    # Ensure unit length
    t_hat = t_hat / np.linalg.norm(t_hat)

    return (r_hat, t_hat, n_hat)


def apply_delta_v(
    r_eci: np.ndarray,
    v_eci: np.ndarray,
    direction: Union[ManeuverDirection, str],
    delta_v_m_s: float,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """
    Applies a delta-v vector in the local RTN frame, rotates it to ECI, and adds it
    to the pre-maneuver velocity.

    Args:
        r_eci: Pre-maneuver position vector in ECI [km]
        v_eci: Pre-maneuver velocity vector in ECI [km/s]
        direction: One of the 6 discrete ManeuverDirection options
        delta_v_m_s: Delta-v magnitude in meters per second (m/s)

    Returns:
        (r_pert_eci, v_pert_eci, delta_v_components_dict):
            - r_pert_eci: Perturbed position [km] (identical to r_eci at impulse)
            - v_pert_eci: Perturbed velocity [km/s]
            - delta_v_components_dict: {"delta_v_r_m_s", "delta_v_t_m_s", "delta_v_n_m_s", "delta_v_m_s"}
    """
    r_hat, t_hat, n_hat = build_rtn_frame(r_eci, v_eci)
    dir_str = direction.value if isinstance(direction, ManeuverDirection) else str(direction).lower()

    dv_r_m_s = 0.0
    dv_t_m_s = 0.0
    dv_n_m_s = 0.0

    if dir_str == ManeuverDirection.ALONG_TRACK_EARLIER.value or dir_str == "along_track_earlier":
        # Retrograde burn: decreases semi-major axis, satellite speeds up/arrives earlier
        dv_t_m_s = -abs(delta_v_m_s)
        dv_eci_km_s = (dv_t_m_s / 1000.0) * t_hat
    elif dir_str == ManeuverDirection.ALONG_TRACK_LATER.value or dir_str == "along_track_later":
        # Prograde burn: increases semi-major axis, satellite arrives later
        dv_t_m_s = abs(delta_v_m_s)
        dv_eci_km_s = (dv_t_m_s / 1000.0) * t_hat
    elif dir_str == ManeuverDirection.RADIAL_POSITIVE.value or dir_str == "radial_positive":
        # Positive radial: outward burn
        dv_r_m_s = abs(delta_v_m_s)
        dv_eci_km_s = (dv_r_m_s / 1000.0) * r_hat
    elif dir_str == ManeuverDirection.RADIAL_NEGATIVE.value or dir_str == "radial_negative":
        # Negative radial: inward burn
        dv_r_m_s = -abs(delta_v_m_s)
        dv_eci_km_s = (dv_r_m_s / 1000.0) * r_hat
    elif dir_str == ManeuverDirection.CROSS_TRACK_POSITIVE.value or dir_str == "cross_track_positive":
        # Positive cross-track: normal / northward burn
        dv_n_m_s = abs(delta_v_m_s)
        dv_eci_km_s = (dv_n_m_s / 1000.0) * n_hat
    elif dir_str == ManeuverDirection.CROSS_TRACK_NEGATIVE.value or dir_str == "cross_track_negative":
        # Negative cross-track: southward burn
        dv_n_m_s = -abs(delta_v_m_s)
        dv_eci_km_s = (dv_n_m_s / 1000.0) * n_hat
    else:
        raise ValueError(f"Unknown maneuver direction: '{direction}'. Valid: {[d.value for d in ALL_MANEUVER_DIRECTIONS]}")

    v_pert_eci = np.asarray(v_eci, dtype=np.float64) + dv_eci_km_s
    r_pert_eci = np.asarray(r_eci, dtype=np.float64).copy()

    components = {
        "delta_v_m_s": float(abs(delta_v_m_s)),
        "delta_v_r_m_s": float(dv_r_m_s),
        "delta_v_t_m_s": float(dv_t_m_s),
        "delta_v_n_m_s": float(dv_n_m_s),
    }

    return (r_pert_eci, v_pert_eci, components)


def two_body_j2_dynamics(t: float, y: np.ndarray) -> np.ndarray:
    """
    Differential equations of motion for Two-Body gravity + J2 Earth oblateness perturbation.
    State y = [x, y, z, vx, vy, vz] in [km, km/s].
    Returns dydt = [vx, vy, vz, ax, ay, az] in [km/s, km/s^2].
    """
    x, y_pos, z = y[0], y[1], y[2]
    vx, vy, vz = y[3], y[4], y[5]

    r_sq = x * x + y_pos * y_pos + z * z
    r = math.sqrt(r_sq)

    if r < 1.0:
        return np.zeros(6, dtype=np.float64)

    r_cube = r_sq * r
    r_fifth = r_cube * r_sq

    # Two-body gravitational acceleration
    two_body_factor = -MU_EARTH_KM3_S2 / r_cube
    ax_2b = two_body_factor * x
    ay_2b = two_body_factor * y_pos
    az_2b = two_body_factor * z

    # J2 Oblateness perturbation acceleration
    # J2 factor = 1.5 * J2 * mu * Re^2 / r^5
    j2_coeff = 1.5 * J2_EARTH * MU_EARTH_KM3_S2 * (WGS84_EARTH_RADIUS_KM ** 2) / r_fifth
    z_sq_over_r_sq = (z * z) / r_sq

    ax_j2 = -j2_coeff * x * (1.0 - 5.0 * z_sq_over_r_sq)
    ay_j2 = -j2_coeff * y_pos * (1.0 - 5.0 * z_sq_over_r_sq)
    az_j2 = -j2_coeff * z * (3.0 - 5.0 * z_sq_over_r_sq)

    ax = ax_2b + ax_j2
    ay = ay_2b + ay_j2
    az = az_2b + az_j2

    return np.array([vx, vy, vz, ax, ay, az], dtype=np.float64)


def propagate_perturbed_arc(
    r0_eci: np.ndarray,
    v0_eci: np.ndarray,
    duration_seconds: float,
    method: str = "DOP853",
) -> Callable[[float], Tuple[np.ndarray, np.ndarray]]:
    """
    Numerically integrates the perturbed satellite state forward for `duration_seconds`
    using Two-Body + J2 force model. Returns a continuous callable `state_at(t_rel_seconds)`
    providing (r_eci, v_eci) at any time offset t_rel in [0, duration_seconds].
    """
    y0 = np.array([
        r0_eci[0], r0_eci[1], r0_eci[2],
        v0_eci[0], v0_eci[1], v0_eci[2],
    ], dtype=np.float64)

    sol = solve_ivp(
        two_body_j2_dynamics,
        (0.0, max(1.0, float(duration_seconds))),
        y0,
        method=method,
        dense_output=True,
        rtol=1e-9,
        atol=1e-10,
    )

    if not sol.success:
        logger.warning(f"Numerical propagation warning: {sol.message}")

    def state_at(t_rel: float) -> Tuple[np.ndarray, np.ndarray]:
        clamped_t = max(0.0, min(float(duration_seconds), float(t_rel)))
        y = sol.sol(clamped_t)
        return (y[0:3], y[3:6])

    return state_at


def sgp4_state_at_datetime(satrec: Satrec, dt: datetime) -> Tuple[np.ndarray, np.ndarray]:
    """
    Evaluates SGP4 state vector (r, v) in TEME/ECI at a given datetime.
    r in km, v in km/s.
    """
    jd = dt.toordinal() + 1721425.5
    fr = (dt.hour * 3600.0 + dt.minute * 60.0 + dt.second + dt.microsecond / 1e6) / 86400.0
    e, r, v = satrec.sgp4(jd, fr)
    if e != 0:
        logger.debug(f"SGP4 error code {e} at {dt.isoformat()}")
    return (np.array(r, dtype=np.float64), np.array(v, dtype=np.float64))


def refine_candidate_tca(
    primary_trajectory: Callable[[float], Tuple[np.ndarray, np.ndarray]],
    satrec_secondary: Satrec,
    burn_epoch: datetime,
    original_tca: datetime,
    max_duration_seconds: float,
) -> Tuple[datetime, float, float]:
    """
    Refines Time of Closest Approach (TCA), minimum miss distance (km), and relative velocity (km/s)
    between the numerically propagated perturbed primary satellite and the SGP4 propagated secondary object.

    Returns:
        (candidate_tca, miss_distance_km, relative_velocity_km_s)
    """
    t_orig_tca_rel = (original_tca - burn_epoch).total_seconds()

    def dist_func(t_rel_s: float) -> float:
        r_pri, _ = primary_trajectory(t_rel_s)
        dt = burn_epoch + timedelta(seconds=t_rel_s)
        r_sec, _ = sgp4_state_at_datetime(satrec_secondary, dt)
        return float(np.linalg.norm(r_pri - r_sec))

    # Search window centered around original TCA (+/- 1800s / 30 min)
    search_half_window_s = 1800.0
    bounds = (
        max(0.0, t_orig_tca_rel - search_half_window_s),
        min(max_duration_seconds, t_orig_tca_rel + search_half_window_s),
    )

    if bounds[1] <= bounds[0]:
        bounds = (0.0, max(1.0, max_duration_seconds))

    res = minimize_scalar(dist_func, bounds=bounds, method="bounded", options={"xatol": 1e-4})

    refined_t_rel = float(res.x) if res.success else t_orig_tca_rel
    candidate_tca = burn_epoch + timedelta(seconds=refined_t_rel)

    r_pri, v_pri = primary_trajectory(refined_t_rel)
    r_sec, v_sec = sgp4_state_at_datetime(satrec_secondary, candidate_tca)

    miss_dist_km = float(np.linalg.norm(r_pri - r_sec))
    rel_vel_km_s = float(np.linalg.norm(v_pri - v_sec))

    return (candidate_tca, miss_dist_km, rel_vel_km_s)


class ManeuverCandidateService:
    """
    Orchestrates the generation, short-arc Two-Body + J2 numerical propagation,
    TCA refinement, collision probability computation, and efficiency scoring
    for candidate collision-avoidance maneuvers.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_satrec_for_norad_id(
        self,
        norad_id: int,
        satellite_id: Optional[uuid.UUID] = None,
    ) -> Optional[Satrec]:
        """
        Retrieves the latest Satrec object for a satellite from either the fleet Satellite
        table or the CatalogSatellite table.
        """
        line1, line2 = None, None

        if satellite_id:
            stmt = select(Satellite).where(Satellite.id == satellite_id).options(selectinload(Satellite.tle_records))
            res = await self.db.execute(stmt)
            sat = res.scalars().first()
            if sat and sat.tle_records:
                latest_tle = max(sat.tle_records, key=lambda t: t.epoch)
                line1, line2 = latest_tle.line1, latest_tle.line2

        if not line1 or not line2:
            # Query CatalogSatellite
            cat_stmt = select(CatalogSatellite).where(CatalogSatellite.norad_id == norad_id)
            cat_res = await self.db.execute(cat_stmt)
            cat_sat = cat_res.scalars().first()
            if cat_sat and cat_sat.line1 and cat_sat.line2:
                line1, line2 = cat_sat.line1, cat_sat.line2

        if not line1 or not line2:
            # Check fleet satellite by norad_id directly
            sat_stmt = select(Satellite).where(Satellite.norad_id == norad_id).options(selectinload(Satellite.tle_records))
            sat_res = await self.db.execute(sat_stmt)
            fleet_sat = sat_res.scalars().first()
            if fleet_sat and fleet_sat.tle_records:
                latest_tle = max(fleet_sat.tle_records, key=lambda t: t.epoch)
                line1, line2 = latest_tle.line1, latest_tle.line2

        if line1 and line2:
            try:
                return Satrec.twoline2rv(line1, line2)
            except Exception as exc:
                logger.error(f"Failed to create Satrec for NORAD ID {norad_id}: {exc}")

        return None

    async def generate_candidates_for_alert(
        self,
        alert_id: uuid.UUID,
        magnitude_grid_m_s: Optional[List[float]] = None,
        timing_grid_hours: Optional[List[float]] = None,
        directions: Optional[List[str]] = None,
        save_to_db: bool = True,
        primary_satrec_override: Optional[Satrec] = None,
        secondary_satrec_override: Optional[Satrec] = None,
    ) -> Dict:
        """
        Generates candidate collision-avoidance maneuvers for an existing ConjunctionAlert.

        Args:
            alert_id: UUID of the ConjunctionAlert
            magnitude_grid_m_s: Optional list of burn magnitudes [m/s]
            timing_grid_hours: Optional list of burn offsets before TCA [hours]
            directions: Optional subset of ManeuverDirection strings
            save_to_db: Whether to delete old candidates and save new ones to the DB
            primary_satrec_override: Optional direct Satrec for primary (e.g. testing)
            secondary_satrec_override: Optional direct Satrec for secondary (e.g. testing)

        Returns:
            Dict matching ManeuverGenerationResponse payload.
        """
        stmt = select(ConjunctionAlert).where(ConjunctionAlert.id == alert_id)
        res = await self.db.execute(stmt)
        alert = res.scalars().first()

        if not alert:
            raise ValueError(f"ConjunctionAlert with ID {alert_id} not found.")

        # Resolve Satrecs
        satrec_primary = primary_satrec_override or await self.get_satrec_for_norad_id(
            alert.satellite_a_norad_id, alert.satellite_a_id
        )
        satrec_secondary = secondary_satrec_override or await self.get_satrec_for_norad_id(
            alert.satellite_b_norad_id, alert.satellite_b_id
        )

        if not satrec_primary:
            raise ValueError(
                f"Could not resolve TLE ephemeris for primary satellite {alert.satellite_a_name} (NORAD {alert.satellite_a_norad_id})."
            )
        if not satrec_secondary:
            raise ValueError(
                f"Could not resolve TLE ephemeris for secondary object {alert.satellite_b_name} (NORAD {alert.satellite_b_norad_id})."
            )

        # Grids
        magnitudes = magnitude_grid_m_s if magnitude_grid_m_s is not None else DEFAULT_MAGNITUDE_GRID_M_S
        timings = timing_grid_hours if timing_grid_hours is not None else DEFAULT_TIMING_GRID_HOURS

        if directions is not None:
            active_directions = [
                ManeuverDirection(d) if isinstance(d, str) else d for d in directions
            ]
        else:
            active_directions = ALL_MANEUVER_DIRECTIONS

        # Combined HBR for Pc calculations
        _, _, combined_hbr, _, _ = ProbabilityEngine.combine_hbr(
            norad_a=alert.satellite_a_norad_id,
            norad_b=alert.satellite_b_norad_id,
        )

        original_tca = alert.tca
        original_miss_distance_m = alert.miss_distance_m
        original_risk_level = alert.risk_level

        generated_candidates: List[Dict] = []
        now = datetime.now(timezone.utc)

        # Evaluate each burn timing offset
        for offset_hours in timings:
            offset_seconds = float(offset_hours) * 3600.0
            burn_epoch = original_tca - timedelta(seconds=offset_seconds)

            # Pre-maneuver unperturbed state of primary at burn epoch via SGP4
            r0_eci, v0_eci = sgp4_state_at_datetime(satrec_primary, burn_epoch)

            # Duration from burn epoch to slightly past TCA (e.g. +3600s buffer)
            prop_duration_s = offset_seconds + 3600.0

            # Evaluate each direction and magnitude
            for direction in active_directions:
                for mag_m_s in magnitudes:
                    r_pert_eci, v_pert_eci, components = apply_delta_v(
                        r0_eci, v0_eci, direction, mag_m_s
                    )

                    # Short-arc numerical propagation with Two-Body + J2
                    primary_trajectory = propagate_perturbed_arc(
                        r_pert_eci, v_pert_eci, duration_seconds=prop_duration_s
                    )

                    # Refine candidate TCA and compute post-maneuver miss distance
                    candidate_tca, cand_miss_km, cand_rel_vel = refine_candidate_tca(
                        primary_trajectory,
                        satrec_secondary,
                        burn_epoch,
                        original_tca,
                        max_duration_seconds=prop_duration_s,
                    )

                    cand_miss_m = cand_miss_km * 1000.0

                    # Compute collision probability Pc
                    prob_res = ProbabilityEngine.calculate_probability(
                        miss_distance_m=cand_miss_m,
                        hbr_m=combined_hbr,
                    )
                    cand_pc = prob_res.get("pc", 0.0)

                    # Classify resulting risk level
                    cand_risk_level = ConjunctionEngine.classify_risk(
                        probability=cand_pc,
                        miss_distance_m=cand_miss_m,
                    )

                    # Miss distance improvement (positive means safer / larger miss distance)
                    miss_improvement_m = cand_miss_m - original_miss_distance_m

                    # Efficiency: Miss distance improvement per unit delta-v (m / (m/s))
                    efficiency = miss_improvement_m / max(1e-6, mag_m_s) if mag_m_s > 0 else 0.0

                    risk_change = f"{original_risk_level} -> {cand_risk_level}"

                    dir_val = direction.value if isinstance(direction, ManeuverDirection) else str(direction)

                    generated_candidates.append({
                        "id": str(uuid.uuid4()),
                        "alert_id": str(alert.id),
                        "direction": dir_val,
                        "delta_v_m_s": float(mag_m_s),
                        "delta_v_r_m_s": float(components["delta_v_r_m_s"]),
                        "delta_v_t_m_s": float(components["delta_v_t_m_s"]),
                        "delta_v_n_m_s": float(components["delta_v_n_m_s"]),
                        "burn_epoch": burn_epoch,
                        "time_before_tca_hours": float(offset_hours),
                        "resulting_tca": candidate_tca,
                        "resulting_miss_distance_m": float(cand_miss_m),
                        "resulting_miss_distance_km": float(cand_miss_km),
                        "resulting_relative_velocity_km_s": float(cand_rel_vel) if cand_rel_vel else None,
                        "resulting_probability": float(cand_pc),
                        "resulting_risk_level": cand_risk_level,
                        "miss_distance_improvement_m": float(miss_improvement_m),
                        "risk_level_change": risk_change,
                        "efficiency_m_per_m_s": float(efficiency),
                        "fuel_cost_proxy_m_s": float(mag_m_s),
                        "created_at": now,
                    })

        # Sort candidates by efficiency descending (most efficient maneuver first), then miss distance
        generated_candidates.sort(
            key=lambda c: (c["efficiency_m_per_m_s"], c["resulting_miss_distance_m"]),
            reverse=True,
        )

        if save_to_db:
            # Delete existing candidates for this alert
            await self.db.execute(
                delete(ManeuverCandidate).where(ManeuverCandidate.alert_id == alert.id)
            )

            # Insert new candidate records
            for cand_data in generated_candidates:
                candidate_record = ManeuverCandidate(
                    id=uuid.UUID(cand_data["id"]),
                    alert_id=alert.id,
                    direction=cand_data["direction"],
                    delta_v_m_s=cand_data["delta_v_m_s"],
                    delta_v_r_m_s=cand_data["delta_v_r_m_s"],
                    delta_v_t_m_s=cand_data["delta_v_t_m_s"],
                    delta_v_n_m_s=cand_data["delta_v_n_m_s"],
                    burn_epoch=cand_data["burn_epoch"],
                    time_before_tca_hours=cand_data["time_before_tca_hours"],
                    resulting_tca=cand_data["resulting_tca"],
                    resulting_miss_distance_m=cand_data["resulting_miss_distance_m"],
                    resulting_miss_distance_km=cand_data["resulting_miss_distance_km"],
                    resulting_relative_velocity_km_s=cand_data["resulting_relative_velocity_km_s"],
                    resulting_probability=cand_data["resulting_probability"],
                    resulting_risk_level=cand_data["resulting_risk_level"],
                    miss_distance_improvement_m=cand_data["miss_distance_improvement_m"],
                    risk_level_change=cand_data["risk_level_change"],
                    efficiency_m_per_m_s=cand_data["efficiency_m_per_m_s"],
                    fuel_cost_proxy_m_s=cand_data["fuel_cost_proxy_m_s"],
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(candidate_record)

            await self.db.commit()

        return {
            "alert_id": str(alert.id),
            "primary_satellite_name": alert.satellite_a_name,
            "primary_norad_id": alert.satellite_a_norad_id,
            "secondary_object_name": alert.satellite_b_name,
            "secondary_norad_id": alert.satellite_b_norad_id,
            "baseline_tca": alert.tca,
            "baseline_miss_distance_m": alert.miss_distance_m,
            "baseline_miss_distance_km": alert.miss_distance_km,
            "baseline_probability": alert.probability,
            "baseline_risk_level": alert.risk_level,
            "total_candidates": len(generated_candidates),
            "candidates": generated_candidates,
            "generated_at": now,
        }

    async def get_saved_candidates_for_alert(self, alert_id: uuid.UUID) -> Optional[Dict]:
        """
        Fetches previously computed maneuver candidates for an alert from the database.
        """
        stmt = select(ConjunctionAlert).where(ConjunctionAlert.id == alert_id)
        res = await self.db.execute(stmt)
        alert = res.scalars().first()

        if not alert:
            return None

        cand_stmt = (
            select(ManeuverCandidate)
            .where(ManeuverCandidate.alert_id == alert_id)
            .order_by(ManeuverCandidate.efficiency_m_per_m_s.desc())
        )
        cand_res = await self.db.execute(cand_stmt)
        records = cand_res.scalars().all()

        if not records:
            return None

        candidates = [
            {
                "id": str(r.id),
                "alert_id": str(r.alert_id),
                "direction": r.direction,
                "delta_v_m_s": r.delta_v_m_s,
                "delta_v_r_m_s": r.delta_v_r_m_s,
                "delta_v_t_m_s": r.delta_v_t_m_s,
                "delta_v_n_m_s": r.delta_v_n_m_s,
                "burn_epoch": r.burn_epoch,
                "time_before_tca_hours": r.time_before_tca_hours,
                "resulting_tca": r.resulting_tca,
                "resulting_miss_distance_m": r.resulting_miss_distance_m,
                "resulting_miss_distance_km": r.resulting_miss_distance_km,
                "resulting_relative_velocity_km_s": r.resulting_relative_velocity_km_s,
                "resulting_probability": r.resulting_probability,
                "resulting_risk_level": r.resulting_risk_level,
                "miss_distance_improvement_m": r.miss_distance_improvement_m,
                "risk_level_change": r.risk_level_change,
                "efficiency_m_per_m_s": r.efficiency_m_per_m_s,
                "fuel_cost_proxy_m_s": r.fuel_cost_proxy_m_s,
                "created_at": r.created_at,
            }
            for r in records
        ]

        return {
            "alert_id": str(alert.id),
            "primary_satellite_name": alert.satellite_a_name,
            "primary_norad_id": alert.satellite_a_norad_id,
            "secondary_object_name": alert.satellite_b_name,
            "secondary_norad_id": alert.satellite_b_norad_id,
            "baseline_tca": alert.tca,
            "baseline_miss_distance_m": alert.miss_distance_m,
            "baseline_miss_distance_km": alert.miss_distance_km,
            "baseline_probability": alert.probability,
            "baseline_risk_level": alert.risk_level,
            "total_candidates": len(candidates),
            "candidates": candidates,
            "generated_at": records[0].created_at if records else datetime.now(timezone.utc),
        }
