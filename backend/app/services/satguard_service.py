import logging
import math
from datetime import datetime, timedelta, timezone
from scipy.optimize import minimize_scalar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.satellites import Satellite, TLERecord
from app.models.enums import SatelliteStatus
from app.models.conjunctions import ConjunctionEvent
from app.services.probability_engine import ProbabilityEngine
from app.services.conjunction_engine import ConjunctionEngine
from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)

# Constants
MU = 398600.4418  # Earth's standard gravitational parameter in km^3/s^2
R_EARTH = 6378.137  # Earth radius in km


from app.models.catalog import CatalogSatellite


class SatguardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.alert_service = AlertService(db)

    @staticmethod
    def _compute_apogee_perigee(tle_line1: str, tle_line2: str):
        try:
            from sgp4.api import Satrec
            satrec = Satrec.twoline2rv(tle_line1, tle_line2)
            n_rad_min = satrec.no_kozai
            if n_rad_min <= 0:
                return 0, 0
            n_rad_s = n_rad_min / 60.0
            a = (MU / (n_rad_s ** 2)) ** (1/3)
            e = satrec.ecco
            apogee = a * (1 + e) - R_EARTH
            perigee = a * (1 - e) - R_EARTH
            return apogee, perigee
        except Exception:
            return 0, 0

    @staticmethod
    def _distance_at_time(satrec1, satrec2, dt: datetime):
        now_jd = dt.toordinal() + 1721425.5
        now_fr = (dt.hour * 3600 + dt.minute * 60 +
                  dt.second + dt.microsecond / 1e6) / 86400.0

        e1, r1, v1 = satrec1.sgp4(now_jd, now_fr)
        e2, r2, v2 = satrec2.sgp4(now_jd, now_fr)

        if e1 != 0 or e2 != 0:
            return float('inf'), None, None

        dx = r1[0] - r2[0]
        dy = r1[1] - r2[1]
        dz = r1[2] - r2[2]

        dvx = v1[0] - v2[0]
        dvy = v1[1] - v2[1]
        dvz = v1[2] - v2[2]

        dist = math.sqrt(dx**2 + dy**2 + dz**2)
        rel_vel = math.sqrt(dvx**2 + dvy**2 + dvz**2)

        return dist, r1, v1, r2, v2, rel_vel

    async def screen_all(self, lookahead_hours=72, step_size_s=60, miss_dist_threshold_km=5.0):
        # 1. Fetch active primary satellites (the operator fleet) with their latest TLE
        stmt = select(Satellite).where(Satellite.status == SatelliteStatus.ACTIVE).options(
            selectinload(Satellite.tle_records))
        result = await self.db.execute(stmt)
        satellites = result.scalars().all()

        # Filter those that have a TLE
        valid_primaries = []
        for s in satellites:
            if s.tle_records:
                latest_tle = max(s.tle_records, key=lambda t: t.epoch)
                apogee, perigee = self._compute_apogee_perigee(
                    latest_tle.line1, latest_tle.line2)
                valid_primaries.append({
                    "name": getattr(s, "name", "Unknown") or "Unknown",
                    "norad_id": getattr(s, "norad_id", None),
                    "id": getattr(s, "id", None),
                    "line1": latest_tle.line1,
                    "line2": latest_tle.line2,
                    "apogee": apogee,
                    "perigee": perigee,
                })

        if not valid_primaries:
            logger.info("No active fleet satellites with TLEs found for screening.")
            return 0

        # 2. Fetch catalog objects to screen against
        cat_stmt = select(CatalogSatellite)
        cat_result = await self.db.execute(cat_stmt)
        catalog_sats = cat_result.scalars().all()

        secondaries = []
        if catalog_sats:
            for cs in catalog_sats:
                if hasattr(cs, "apogee_km") and cs.apogee_km is not None:
                    apogee = cs.apogee_km
                    perigee = cs.perigee_km if cs.perigee_km is not None else 0
                    line1 = getattr(cs, "line1", "")
                    line2 = getattr(cs, "line2", "")
                elif hasattr(cs, "tle_records") and cs.tle_records:
                    latest = max(cs.tle_records, key=lambda t: t.epoch)
                    apogee, perigee = self._compute_apogee_perigee(latest.line1, latest.line2)
                    line1 = latest.line1
                    line2 = latest.line2
                else:
                    continue

                secondaries.append({
                    "name": getattr(cs, "name", "Unknown") or "Unknown",
                    "norad_id": getattr(cs, "norad_id", None),
                    "id": getattr(cs, "id", None),
                    "line1": line1,
                    "line2": line2,
                    "apogee": apogee,
                    "perigee": perigee,
                })
        else:
            # Fallback to screening primary fleet satellites against each other if catalog is empty
            secondaries = valid_primaries

        logger.info(
            f"Starting screening for {len(valid_primaries)} fleet satellites against {len(secondaries)} catalog objects over {lookahead_hours}h."
        )

        from sgp4.api import Satrec

        now = datetime.now(timezone.utc)
        steps = int((lookahead_hours * 3600) / step_size_s)
        events_created = 0
        seen_pairs = set()

        for sat1_data in valid_primaries:
            p_ident = str(sat1_data["id"] or sat1_data["norad_id"])

            for sat2_data in secondaries:
                s_ident = str(sat2_data["id"] or sat2_data["norad_id"])
                if p_ident == s_ident:
                    continue

                pair_key = (min(p_ident, s_ident), max(p_ident, s_ident))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Coarse Altitude Filter with 25km buffer
                if sat1_data["perigee"] > sat2_data["apogee"] + 25 or sat2_data["perigee"] > sat1_data["apogee"] + 25:
                    continue

                # Fine Screening using SGP4
                try:
                    satrec1 = Satrec.twoline2rv(
                        sat1_data["line1"], sat1_data["line2"])
                    satrec2 = Satrec.twoline2rv(
                        sat2_data["line1"], sat2_data["line2"])
                except Exception:
                    continue

                min_dist = float('inf')
                min_t_offset = 0

                # Coarse time stepping
                for step in range(steps):
                    dt = now + timedelta(seconds=step * step_size_s)
                    dist, *_ = self._distance_at_time(satrec1, satrec2, dt)

                    if dist < min_dist:
                        min_dist = dist
                        min_t_offset = step * step_size_s

                # Refine if within 50km
                if min_dist < 50.0:
                    def distance_func(t_offset_s):
                        dt = now + timedelta(seconds=t_offset_s)
                        dist, *_ = self._distance_at_time(satrec1, satrec2, dt)
                        return dist

                    bounds = (max(0, min_t_offset - step_size_s),
                              min_t_offset + step_size_s)
                    res = minimize_scalar(
                        distance_func, bounds=bounds, method='bounded')

                    if res.success:
                        refined_t_offset = res.x
                        refined_dist, r1, v1, r2, v2, rel_vel = self._distance_at_time(
                            satrec1, satrec2, now + timedelta(seconds=refined_t_offset))

                        if refined_dist <= miss_dist_threshold_km:
                            tca = now + timedelta(seconds=refined_t_offset)

                            prob_result = ProbabilityEngine.calculate_probability(
                                miss_distance_m=refined_dist * 1000,
                                hbr_m=20.0
                            )
                            pc = prob_result["pc"]
                            risk_level = ConjunctionEngine.classify_risk(
                                pc, refined_dist * 1000)

                            event = ConjunctionEvent(
                                primary_satellite=sat1_data["name"],
                                primary_norad_id=sat1_data["norad_id"],
                                secondary_object=sat2_data["name"],
                                secondary_norad_id=sat2_data["norad_id"],
                                tca=tca,
                                miss_distance_m=refined_dist * 1000,
                                relative_velocity_km_s=rel_vel,
                                probability=pc,
                                risk_level=risk_level,
                                detected_by="Satguard SGP4",
                                status="open"
                            )
                            self.db.add(event)
                            await self.db.flush()

                            if risk_level in ["medium", "high", "critical"]:
                                await self.alert_service.create_alert_from_conjunction(event)

                            events_created += 1

        await self.db.commit()
        return events_created
