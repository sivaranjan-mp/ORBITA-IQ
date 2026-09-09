import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import minimize_scalar
from sgp4.api import Satrec
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import (
    COARSE_STEP_SECONDS,
    DEFAULT_LOOKAHEAD_HOURS,
    MAX_SCREEN_MISS_DISTANCE_KM,
    MU_EARTH_KM3_S2,
    STAGE1_ALTITUDE_MARGIN_KM,
    STALE_ALERT_CLEANUP_HOURS,
    WGS84_EARTH_RADIUS_KM,
)
from app.models.alerts import Alert, ConjunctionAlert
from app.models.catalog import CatalogSatellite
from app.models.conjunctions import ConjunctionEvent
from app.models.enums import AlertState, ConjunctionStatus, RiskLevel, SatelliteStatus
from app.models.satellites import Satellite
from app.services.conjunction_engine import ConjunctionEngine
from app.services.probability_engine import ProbabilityEngine
from app.services.relative_geometry import compute_relative_geometry
from app.services.risk_explanation_engine import RiskExplanationEngine

logger = logging.getLogger(__name__)


class SatguardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def compute_apogee_perigee(line1: str, line2: str) -> Tuple[float, float]:
        """
        Computes perigee and apogee altitudes (km) above Earth's mean radius from TLE lines.
        """
        satrec = Satrec.twoline2rv(line1, line2)
        n_rad_s = satrec.no_kozai / 60.0
        a = (MU_EARTH_KM3_S2 / (n_rad_s ** 2)) ** (1.0 / 3.0)
        e = satrec.ecco
        r_perigee = a * (1.0 - e)
        r_apogee = a * (1.0 + e)
        perigee_alt = max(0.0, r_perigee - WGS84_EARTH_RADIUS_KM)
        apogee_alt = max(0.0, r_apogee - WGS84_EARTH_RADIUS_KM)
        return (apogee_alt, perigee_alt)

    @staticmethod
    def _distance_at_time(
        sat1: Satrec,
        sat2: Satrec,
        dt: datetime,
    ) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
        """
        Calculates 3D Euclidean distance (km) and relative velocity (km/s) between two satellites at a specific datetime.
        """
        jd = dt.toordinal() + 1721425.5
        fr = (dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6) / 86400.0

        e1, r1, v1 = sat1.sgp4(jd, fr)
        e2, r2, v2 = sat2.sgp4(jd, fr)

        if e1 != 0 or e2 != 0:
            return (1e9, np.zeros(3), np.zeros(3), np.zeros(3), np.zeros(3), 0.0)

        r1_arr = np.array(r1, dtype=np.float64)
        r2_arr = np.array(r2, dtype=np.float64)
        v1_arr = np.array(v1, dtype=np.float64)
        v2_arr = np.array(v2, dtype=np.float64)

        diff = r1_arr - r2_arr
        dist_km = float(np.linalg.norm(diff))
        rel_vel = float(np.linalg.norm(v1_arr - v2_arr))

        return (dist_km, r1_arr, v1_arr, r2_arr, v2_arr, rel_vel)

    async def screen_all(
        self,
        lookahead_hours: float = DEFAULT_LOOKAHEAD_HOURS,
        step_size_s: int = COARSE_STEP_SECONDS,
        miss_dist_threshold_km: float = MAX_SCREEN_MISS_DISTANCE_KM,
    ) -> Dict:
        """
        Executes complete 2-stage conjunction screening across:
        1. Fleet vs Fleet (My Satellites screened against each other)
        2. Fleet vs Catalog (My Satellites screened against Global Catalog)

        Stage 1: Coarse perigee/apogee filter (eliminates non-overlapping orbits).
        Stage 2: Vectorized 5-day SGP4 propagation scan on ALL Stage 1 survivors (no truncation)
                 + scipy scalar refinement near local minima.
        """
        start_time = time.time()
        now = datetime.now(timezone.utc)

        # 1. Fetch active primary satellites (the fleet) with their latest TLEs
        try:
            stmt = (
                select(Satellite)
                .where(Satellite.status == SatelliteStatus.ACTIVE)
                .options(selectinload(Satellite.tle_records))
            )
            result = await self.db.execute(stmt)
            satellites = result.scalars().all()
        except Exception as query_err:
            logger.warning(
                f"Direct ENUM query on Satellite.status failed ({query_err}), falling back to text cast query."
            )
            raw_stmt = (
                select(Satellite)
                .where(text("satellites.status::text = 'active'"))
                .options(selectinload(Satellite.tle_records))
            )
            result = await self.db.execute(raw_stmt)
            satellites = result.scalars().all()

        fleet_objects: List[Dict] = []
        for s in satellites:
            line1, line2 = None, None
            if s.tle_records:
                latest_tle = max(s.tle_records, key=lambda t: t.epoch)
                line1, line2 = latest_tle.line1, latest_tle.line2
            else:
                cat_match = await self.db.execute(
                    select(CatalogSatellite).where(CatalogSatellite.norad_id == s.norad_id)
                )
                cat_sat = cat_match.scalars().first()
                if cat_sat and cat_sat.line1 and cat_sat.line2:
                    line1, line2 = cat_sat.line1, cat_sat.line2

            if not line1 or not line2:
                continue

            try:
                satrec = Satrec.twoline2rv(line1, line2)
                apogee, perigee = self.compute_apogee_perigee(line1, line2)
                fleet_objects.append({
                    "id": str(s.id),
                    "norad_id": s.norad_id,
                    "name": s.name or f"SAT-{s.norad_id}",
                    "line1": line1,
                    "line2": line2,
                    "apogee": apogee,
                    "perigee": perigee,
                    "satrec": satrec,
                })
            except Exception:
                continue

        # Resolve past alerts whose TCA has passed
        try:
            stmt_active = select(ConjunctionAlert).where(
                ConjunctionAlert.status.in_([ConjunctionStatus.OPEN, ConjunctionStatus.MONITORING])
            )
            res_active = await self.db.execute(stmt_active)
            for alert in res_active.scalars().all():
                alert_tca = alert.tca if alert.tca.tzinfo else alert.tca.replace(tzinfo=timezone.utc)
                if alert_tca < (now - timedelta(minutes=2)):
                    alert.status = "resolved"
                    alert.updated_at = now
            await self.db.commit()
        except Exception as exc:
            logger.debug(f"Could not update past alert statuses: {exc}")

        if not fleet_objects:
            logger.info("No fleet satellites with valid TLEs found for screening.")
            return {
                "events_created": 0,
                "fleet_vs_fleet_pairs": 0,
                "fleet_vs_catalog_pairs": 0,
                "stage1_survivors": 0,
                "stage2_scanned_pairs": 0,
                "duration_seconds": round(time.time() - start_time, 3),
            }

        # 2. Fetch full catalog objects to screen against
        cat_stmt = select(CatalogSatellite)
        cat_result = await self.db.execute(cat_stmt)
        catalog_sats = cat_result.scalars().all()

        catalog_objects: List[Dict] = []
        for cs in catalog_sats:
            if not cs.line1 or not cs.line2:
                continue
            apogee = cs.apogee_km if cs.apogee_km is not None else 0.0
            perigee = cs.perigee_km if cs.perigee_km is not None else 0.0
            if apogee == 0.0 and perigee == 0.0:
                apogee, perigee = self.compute_apogee_perigee(cs.line1, cs.line2)

            try:
                satrec = Satrec.twoline2rv(cs.line1, cs.line2)
                catalog_objects.append({
                    "id": None,
                    "norad_id": cs.norad_id,
                    "name": cs.name or f"OBJECT {cs.norad_id}",
                    "line1": cs.line1,
                    "line2": cs.line2,
                    "apogee": apogee,
                    "perigee": perigee,
                    "satrec": satrec,
                })
            except Exception:
                continue

        total_fleet = len(fleet_objects)
        total_catalog = len(catalog_objects)
        raw_fvf = (total_fleet * (total_fleet - 1)) // 2
        raw_fvc = total_fleet * total_catalog

        logger.info(
            f"Screening starting: {total_fleet} fleet vs {total_fleet} fleet ({raw_fvf} pairs) "
            f"+ {total_fleet} fleet vs {total_catalog} catalog ({raw_fvc} pairs) over {lookahead_hours}h lookahead."
        )

        # 3. Clean up stale past conjunctions (TCA older than STALE_ALERT_CLEANUP_HOURS)
        cutoff_time = now - timedelta(hours=STALE_ALERT_CLEANUP_HOURS)
        try:
            await self.db.execute(
                delete(ConjunctionAlert).where(ConjunctionAlert.tca < cutoff_time)
            )
            await self.db.execute(
                delete(ConjunctionEvent).where(ConjunctionEvent.tca < cutoff_time)
            )
        except Exception as exc:
            logger.debug(f"Could not purge past alerts: {exc}")

        # 4. Prepare Screening Pair Tasks
        screening_pairs = []
        seen_pairs = set()

        # Scope 1: Fleet vs Fleet
        for i in range(len(fleet_objects)):
            sat_a = fleet_objects[i]
            for j in range(i + 1, len(fleet_objects)):
                sat_b = fleet_objects[j]
                if sat_a["norad_id"] == sat_b["norad_id"]:
                    continue
                pair_key = (min(sat_a["norad_id"], sat_b["norad_id"]), max(sat_a["norad_id"], sat_b["norad_id"]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                screening_pairs.append((sat_a, sat_b, "fleet_vs_fleet"))

        # Scope 2: Fleet vs Catalog
        for sat_a in fleet_objects:
            for sat_b in catalog_objects:
                if sat_a["norad_id"] == sat_b["norad_id"]:
                    continue
                pair_key = (min(sat_a["norad_id"], sat_b["norad_id"]), max(sat_a["norad_id"], sat_b["norad_id"]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                screening_pairs.append((sat_a, sat_b, "fleet_vs_catalog"))

        # Stage 1: Coarse Filter
        stage1_survivors = []
        needed_sat_recs = set()
        for sat_a, sat_b, scope in screening_pairs:
            if ConjunctionEngine.passes_stage1_coarse_filter(
                sat_a["perigee"], sat_a["apogee"], sat_b["perigee"], sat_b["apogee"], STAGE1_ALTITUDE_MARGIN_KM
            ):
                stage1_survivors.append((sat_a, sat_b, scope))
                needed_sat_recs.add(sat_a["norad_id"])
                needed_sat_recs.add(sat_b["norad_id"])

        logger.info(
            f"Stage 1 filter complete: {len(stage1_survivors):,} candidate pairs survived out of {len(screening_pairs):,} raw pairs "
            f"({(1.0 - len(stage1_survivors) / max(1, len(screening_pairs))) * 100:.1f}% rejected)."
        )

        # Stage 2: Precompute 5-day ephemerides array once per unique satellite in survivors
        steps = int((lookahead_hours * 3600.0) / step_size_s)
        jd_base = now.toordinal() + 1721425.5
        fr_base = (now.hour * 3600.0 + now.minute * 60.0 + now.second + now.microsecond / 1e6) / 86400.0
        dt_secs = np.arange(0, lookahead_hours * 3600.0, step_size_s, dtype=np.float64)
        fr_array = fr_base + dt_secs / 86400.0
        jd_array = np.full_like(fr_array, jd_base)

        all_candidate_sats = {s["norad_id"]: s for s in fleet_objects + catalog_objects if s["norad_id"] in needed_sat_recs}
        ephemeris_cache = {}
        for nid, s in all_candidate_sats.items():
            try:
                e, r, v = s["satrec"].sgp4_array(jd_array, fr_array)
                if not (e != 0).any():
                    ephemeris_cache[nid] = r
            except Exception:
                pass

        # Vectorized Scan across all Stage 1 survivors (100% evaluated, zero truncation)
        detected_alerts: List[Dict] = []

        for sat_a, sat_b, scope in stage1_survivors:
            r1 = ephemeris_cache.get(sat_a["norad_id"])
            r2 = ephemeris_cache.get(sat_b["norad_id"])

            if r1 is None or r2 is None:
                # Fallback to scalar distance loop if array had non-zero error codes
                continue

            diff = r1 - r2
            dists_sq = np.sum(diff * diff, axis=1)
            min_idx = int(np.argmin(dists_sq))
            min_dist = float(np.sqrt(dists_sq[min_idx]))

            # If close approach within threshold (e.g. 50 km), refine near the minimum
            if min_dist <= miss_dist_threshold_km:
                satrec1 = sat_a["satrec"]
                satrec2 = sat_b["satrec"]
                min_t_offset = float(min_idx * step_size_s)

                def dist_func(t_offset_s):
                    dt = now + timedelta(seconds=t_offset_s)
                    d, *_ = self._distance_at_time(satrec1, satrec2, dt)
                    return d

                bounds = (
                    max(0.0, min_t_offset - step_size_s),
                    min(lookahead_hours * 3600.0, min_t_offset + step_size_s),
                )
                res = minimize_scalar(dist_func, bounds=bounds, method='bounded')

                if res.success:
                    refined_t_offset = float(res.x)
                    tca = now + timedelta(seconds=refined_t_offset)
                    refined_dist, r1_vec, v1_vec, r2_vec, v2_vec, rel_vel = self._distance_at_time(
                        satrec1, satrec2, tca
                    )

                    if refined_dist <= miss_dist_threshold_km:
                        risk_level = ConjunctionEngine.classify_risk_by_miss_distance(refined_dist)
                        if not risk_level:
                            continue

                        hbr_a, hbr_b, combined_hbr, a_is_known, b_is_known = (
                            ProbabilityEngine.combine_hbr(sat_a, sat_b)
                        )
                        prob_res = ProbabilityEngine.calculate_probability(
                            miss_distance_m=refined_dist * 1000.0,
                            hbr_m=combined_hbr,
                        )
                        pc = prob_res.get("pc", 0.0)

                        # Compute authoritative relative state, RIC decomposition, and encounter geometry
                        geom = compute_relative_geometry(r1_vec, v1_vec, r2_vec, v2_vec)

                        detected_alerts.append({
                            "sat_a": sat_a,
                            "sat_b": sat_b,
                            "scope": scope,
                            "tca": tca,
                            "miss_distance_km": refined_dist,
                            "miss_distance_m": refined_dist * 1000.0,
                            "relative_velocity_km_s": geom.relative_speed_km_s,
                            "probability": pc,
                            "risk_level": risk_level,
                            "relative_position_x": float(geom.relative_position_km[0]),
                            "relative_position_y": float(geom.relative_position_km[1]),
                            "relative_position_z": float(geom.relative_position_km[2]),
                            "relative_velocity_x": float(geom.relative_velocity_km_s[0]),
                            "relative_velocity_y": float(geom.relative_velocity_km_s[1]),
                            "relative_velocity_z": float(geom.relative_velocity_km_s[2]),
                            "radial_separation_km": geom.radial_separation_km,
                            "along_track_separation_km": geom.along_track_separation_km,
                            "cross_track_separation_km": geom.cross_track_separation_km,
                            "relative_velocity_angle_deg": geom.relative_velocity_angle_deg,
                            "relative_inclination_deg": geom.relative_inclination_deg,
                            "encounter_geometry": geom.encounter_geometry,
                        })

        # Fetch existing active alerts to perform event-aware matching and automatic resolution
        existing_stmt = select(ConjunctionAlert).where(
            ConjunctionAlert.status.in_([ConjunctionStatus.OPEN, ConjunctionStatus.MONITORING]),
        )
        existing_res = await self.db.execute(existing_stmt)
        existing_alerts = existing_res.scalars().all()

        # 1. Resolve past alerts whose TCA has passed
        for ea in existing_alerts:
            ea_tca = ea.tca if ea.tca.tzinfo else ea.tca.replace(tzinfo=timezone.utc)
            if ea_tca < (now - timedelta(minutes=2)):
                ea.status = "resolved"
                ea.updated_at = now

        # Build lookup of active future alerts: (norad_a, norad_b) -> ConjunctionAlert
        active_alerts_map: Dict[Tuple[int, int], ConjunctionAlert] = {}
        for ea in existing_alerts:
            if ea.status in ("open", "monitoring"):
                pair_key = (min(ea.satellite_a_norad_id, ea.satellite_b_norad_id), max(ea.satellite_a_norad_id, ea.satellite_b_norad_id))
                active_alerts_map[pair_key] = ea

        matched_alerts_set = set()
        events_created = 0

        # 2. Match detected encounters against existing active alerts
        # If an alert already tracks this pair, refine the existing event's parameters
        # and preserve its fixed epoch rather than sliding days forward
        for alert_data in detected_alerts:
            sat_a = alert_data["sat_a"]
            sat_b = alert_data["sat_b"]
            pair_key = (min(sat_a["norad_id"], sat_b["norad_id"]), max(sat_a["norad_id"], sat_b["norad_id"]))

            matched_existing = active_alerts_map.get(pair_key)

            if matched_existing:
                cand_tca = matched_existing.tca if matched_existing.tca.tzinfo else matched_existing.tca.replace(tzinfo=timezone.utc)
                # If detected encounter is within 2 hours of tracked event, refine directly
                if abs((alert_data["tca"] - cand_tca).total_seconds()) <= 7200.0:
                    matched_existing.tca = alert_data["tca"]
                    matched_existing.miss_distance_km = alert_data["miss_distance_km"]
                    matched_existing.miss_distance_m = alert_data["miss_distance_m"]
                    matched_existing.relative_velocity_km_s = alert_data["relative_velocity_km_s"]
                    matched_existing.probability = alert_data["probability"]
                    matched_existing.risk_level = alert_data["risk_level"]
                    matched_existing.screening_scope = alert_data["scope"]
                    matched_existing.relative_position_x = alert_data["relative_position_x"]
                    matched_existing.relative_position_y = alert_data["relative_position_y"]
                    matched_existing.relative_position_z = alert_data["relative_position_z"]
                    matched_existing.relative_velocity_x = alert_data["relative_velocity_x"]
                    matched_existing.relative_velocity_y = alert_data["relative_velocity_y"]
                    matched_existing.relative_velocity_z = alert_data["relative_velocity_z"]
                    matched_existing.radial_separation_km = alert_data["radial_separation_km"]
                    matched_existing.along_track_separation_km = alert_data["along_track_separation_km"]
                    matched_existing.cross_track_separation_km = alert_data["cross_track_separation_km"]
                    matched_existing.relative_velocity_angle_deg = alert_data["relative_velocity_angle_deg"]
                    matched_existing.relative_inclination_deg = alert_data["relative_inclination_deg"]
                    matched_existing.encounter_geometry = alert_data["encounter_geometry"]
                    matched_existing.computed_at = now
                    matched_alerts_set.add(matched_existing.id)
            else:
                # Genuinely new conjunction event
                sat_a_uuid = sat_a.get("id") if sat_a.get("id") else None
                new_alert = ConjunctionAlert(
                    satellite_a_norad_id=sat_a["norad_id"],
                    satellite_a_name=sat_a["name"],
                    satellite_b_norad_id=sat_b["norad_id"],
                    satellite_b_name=sat_b["name"],
                    satellite_a_id=sat_a_uuid,
                    screening_scope=alert_data["scope"],
                    tca=alert_data["tca"],
                    miss_distance_km=alert_data["miss_distance_km"],
                    miss_distance_m=alert_data["miss_distance_m"],
                    relative_velocity_km_s=alert_data["relative_velocity_km_s"],
                    probability=alert_data["probability"],
                    risk_level=alert_data["risk_level"],
                    status="open",
                    detected_by="satguard",
                    relative_position_x=alert_data["relative_position_x"],
                    relative_position_y=alert_data["relative_position_y"],
                    relative_position_z=alert_data["relative_position_z"],
                    relative_velocity_x=alert_data["relative_velocity_x"],
                    relative_velocity_y=alert_data["relative_velocity_y"],
                    relative_velocity_z=alert_data["relative_velocity_z"],
                    radial_separation_km=alert_data["radial_separation_km"],
                    along_track_separation_km=alert_data["along_track_separation_km"],
                    cross_track_separation_km=alert_data["cross_track_separation_km"],
                    relative_velocity_angle_deg=alert_data["relative_velocity_angle_deg"],
                    relative_inclination_deg=alert_data["relative_inclination_deg"],
                    encounter_geometry=alert_data["encounter_geometry"],
                    computed_at=now,
                )
                self.db.add(new_alert)

                legacy_event = ConjunctionEvent(
                    primary_satellite=sat_a["name"],
                    primary_norad_id=sat_a["norad_id"],
                    secondary_object=sat_b["name"],
                    secondary_norad_id=sat_b["norad_id"],
                    tca=alert_data["tca"],
                    miss_distance_m=alert_data["miss_distance_m"],
                    relative_velocity_km_s=alert_data["relative_velocity_km_s"],
                    probability=alert_data["probability"],
                    risk_level=alert_data["risk_level"],
                    status="open",
                    detected_by="satguard",
                )
                self.db.add(legacy_event)
                events_created += 1

        # 3. For any active future alerts not matched in the broad scan, refine specifically around their fixed TCA
        # This keeps miss distance & geometry updated as orbital data refreshes without changing the event epoch
        for ea in existing_alerts:
            if ea.status in ("open", "monitoring") and ea.id not in matched_alerts_set:
                ea_tca = ea.tca if ea.tca.tzinfo else ea.tca.replace(tzinfo=timezone.utc)
                if ea_tca > now:
                    sat_a_obj = all_candidate_sats.get(ea.satellite_a_norad_id)
                    sat_b_obj = all_candidate_sats.get(ea.satellite_b_norad_id)
                    if sat_a_obj and sat_b_obj:
                        satrec1 = sat_a_obj["satrec"]
                        satrec2 = sat_b_obj["satrec"]

                        def local_dist_func(t_offset_s):
                            dt = ea_tca + timedelta(seconds=t_offset_s)
                            d, *_ = self._distance_at_time(satrec1, satrec2, dt)
                            return d

                        res = minimize_scalar(local_dist_func, bounds=(-1800.0, 1800.0), method='bounded')
                        if res.success:
                            refined_tca = ea_tca + timedelta(seconds=float(res.x))
                            refined_dist, r1_vec, v1_vec, r2_vec, v2_vec, rel_vel = self._distance_at_time(
                                satrec1, satrec2, refined_tca
                            )
                            if refined_dist <= miss_dist_threshold_km:
                                geom = compute_relative_geometry(r1_vec, v1_vec, r2_vec, v2_vec)
                                ea.tca = refined_tca
                                ea.miss_distance_km = refined_dist
                                ea.miss_distance_m = refined_dist * 1000.0
                                ea.relative_velocity_km_s = geom.relative_speed_km_s
                                ea.computed_at = now

        await self.db.commit()

        duration = round(time.time() - start_time, 3)
        logger.info(
            f"Conjunction screening completed in {duration}s. "
            f"{len(detected_alerts)} alerts detected ({events_created} new)."
        )

        return {
            "events_created": events_created,
            "total_detected": len(detected_alerts),
            "fleet_vs_fleet_pairs": raw_fvf,
            "fleet_vs_catalog_pairs": raw_fvc,
            "stage1_survivors": len(stage1_survivors),
            "stage2_scanned_pairs": len(stage1_survivors),
            "duration_seconds": duration,
        }
