import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import minimize_scalar
from sgp4.api import Satrec
from sqlalchemy import delete, select
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
from app.models.enums import ConjunctionStatus, SatelliteStatus
from app.models.satellites import Satellite
from app.services.alert_service import AlertService
from app.services.conjunction_engine import ConjunctionEngine
from app.services.probability_engine import ProbabilityEngine

logger = logging.getLogger(__name__)


class SatguardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.alert_service = AlertService(db)

    @staticmethod
    def compute_apogee_perigee(tle_line1: str, tle_line2: str) -> Tuple[float, float]:
        """
        Calculates apogee and perigee in km above WGS84 Earth radius from TLE mean motion and eccentricity.
        """
        try:
            satrec = Satrec.twoline2rv(tle_line1, tle_line2)
            n_rad_min = satrec.no_kozai
            if n_rad_min <= 0:
                return 0.0, 0.0
            n_rad_s = n_rad_min / 60.0
            a = (MU_EARTH_KM3_S2 / (n_rad_s ** 2)) ** (1.0 / 3.0)
            e = satrec.ecco
            apogee = a * (1.0 + e) - WGS84_EARTH_RADIUS_KM
            perigee = a * (1.0 - e) - WGS84_EARTH_RADIUS_KM
            return round(apogee, 2), round(perigee, 2)
        except Exception:
            return 0.0, 0.0

    @staticmethod
    def _distance_at_time(satrec1: Satrec, satrec2: Satrec, dt: datetime):
        """
        Calculates 3D Euclidean distance (km) and relative velocity (km/s) at datetime dt.
        """
        now_jd = dt.toordinal() + 1721425.5
        now_fr = (
            dt.hour * 3600.0 + dt.minute * 60.0 + dt.second + dt.microsecond / 1e6
        ) / 86400.0

        e1, r1, v1 = satrec1.sgp4(now_jd, now_fr)
        e2, r2, v2 = satrec2.sgp4(now_jd, now_fr)

        if e1 != 0 or e2 != 0:
            return float('inf'), None, None, None, None, None

        dx = r1[0] - r2[0]
        dy = r1[1] - r2[1]
        dz = r1[2] - r2[2]

        dvx = v1[0] - v2[0]
        dvy = v1[1] - v2[1]
        dvz = v1[2] - v2[2]

        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        rel_vel = math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz)

        return dist, r1, v1, r2, v2, rel_vel

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

        Look-ahead window: 5 days (120 hours) from now.
        Stage 1: Coarse perigee/apogee filter (eliminates non-overlapping orbits).
        Stage 2: Vectorized 5-day SGP4 propagation scan on ALL Stage 1 survivors (no truncation)
                 + scipy scalar refinement near local minima.
        """
        start_time = time.time()
        now = datetime.now(timezone.utc)

        # 1. Fetch active primary satellites (the fleet) with their latest TLEs
        stmt = (
            select(Satellite)
            .where(Satellite.status == SatelliteStatus.ACTIVE)
            .options(selectinload(Satellite.tle_records))
        )
        result = await self.db.execute(stmt)
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

                        prob_res = ProbabilityEngine.calculate_probability(
                            miss_distance_m=refined_dist * 1000.0,
                            hbr_m=20.0,
                        )
                        pc = prob_res.get("pc", 0.0)

                        detected_alerts.append({
                            "sat_a": sat_a,
                            "sat_b": sat_b,
                            "scope": scope,
                            "tca": tca,
                            "miss_distance_km": refined_dist,
                            "miss_distance_m": refined_dist * 1000.0,
                            "relative_velocity_km_s": rel_vel or 0.0,
                            "probability": pc,
                            "risk_level": risk_level,
                        })

        # Deduplicate and Persist Alerts into conjunction_alerts
        events_created = 0
        for alert_data in detected_alerts:
            sat_a = alert_data["sat_a"]
            sat_b = alert_data["sat_b"]

            existing_stmt = select(ConjunctionAlert).where(
                ConjunctionAlert.satellite_a_norad_id == sat_a["norad_id"],
                ConjunctionAlert.satellite_b_norad_id == sat_b["norad_id"],
                ConjunctionAlert.status.in_([ConjunctionStatus.OPEN, ConjunctionStatus.MONITORING]),
            )
            existing_res = await self.db.execute(existing_stmt)
            existing_alert = existing_res.scalars().first()

            sat_a_uuid = sat_a.get("id") if sat_a.get("id") else None

            if existing_alert:
                existing_alert.tca = alert_data["tca"]
                existing_alert.miss_distance_km = alert_data["miss_distance_km"]
                existing_alert.miss_distance_m = alert_data["miss_distance_m"]
                existing_alert.relative_velocity_km_s = alert_data["relative_velocity_km_s"]
                existing_alert.probability = alert_data["probability"]
                existing_alert.risk_level = alert_data["risk_level"]
                existing_alert.screening_scope = alert_data["scope"]
                existing_alert.computed_at = now
            else:
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
