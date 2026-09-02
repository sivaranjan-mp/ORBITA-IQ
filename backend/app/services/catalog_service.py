import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import httpx
from sgp4.api import Satrec
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CatalogSatellite
from app.models.satellites import Satellite
from app.schemas.catalog import CatalogItemResponse, CatalogListResponse
from app.services.celestrak_service import CELESTRAK_HEADERS

logger = logging.getLogger(__name__)

MU = 398600.4418  # km^3/s^2
R_EARTH = 6378.137  # km
CELESTRAK_ACTIVE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"

# Fallback starter satellites if CelesTrak is unavailable on initial cold start
STARTER_CATALOG_TLES = [
    (
        "ISS (ZARYA)",
        "1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993",
        "2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585",
    ),
    (
        "HUBBLE SPACE TELESCOPE",
        "1 20580U 90037B   24080.45000000  .00001200  00000-0  54000-4 0  9990",
        "2 20580  28.4690 150.2300 0002800  95.4000 265.1000 15.09340000850001",
    ),
    (
        "TIANGONG",
        "1 48274U 21035A   24080.50000000  .00021000  00000-0  12000-3 0  9991",
        "2 48274  41.4720 120.4500 0002100  45.3000 315.1000 15.61000000150002",
    ),
    (
        "STARLINK-1007",
        "1 44713U 19074A   24080.50000000  .00001500  00000-0  85000-4 0  9992",
        "2 44713  53.0540 280.1200 0001400  60.2000 300.1000 15.06000000230003",
    ),
    (
        "SENTINEL-6A",
        "1 46984U 20086A   24080.50000000  .00000150  00000-0  15000-4 0  9994",
        "2 46984  66.0420 180.2500 0008000  85.1000 275.3000 12.81000000160004",
    ),
    (
        "LANDSAT 9",
        "1 49260U 21088A   24080.50000000  .00000220  00000-0  21000-4 0  9995",
        "2 49260  98.2100 145.6000 0001200 110.4000 250.1000 14.57000000130005",
    ),
    (
        "NOAA 20 (JPSS-1)",
        "1 43013U 17073A   24080.50000000  .00000180  00000-0  18000-4 0  9996",
        "2 43013  98.7400 210.3500 0001500 130.2000 230.5000 14.19000000330006",
    ),
    (
        "TERRA",
        "1 25994U 99068A   24080.50000000  .00000310  00000-0  31000-4 0  9997",
        "2 25994  98.2000 170.4000 0001300 100.1000 260.3000 14.57000000120007",
    ),
    (
        "AQUA",
        "1 27424U 02022A   24080.50000000  .00000290  00000-0  29000-4 0  9998",
        "2 27424  98.2000 160.1000 0001400  95.3000 265.2000 14.57000000110008",
    ),
    (
        "SUOMI NPP",
        "1 37849U 11061A   24080.50000000  .00000190  00000-0  19000-4 0  9999",
        "2 37849  98.7400 205.1000 0001100 125.4000 235.1000 14.19000000630009",
    ),
    (
        "GOES 16",
        "1 41866U 16071A   24080.50000000  .00000050  00000-0  00000-0 0  9991",
        "2 41866   0.0500  45.1000 0003000  50.1000 310.2000  1.00270000270001",
    ),
    (
        "GOES 18",
        "1 51850U 22021A   24080.50000000  .00000050  00000-0  00000-0 0  9992",
        "2 51850   0.0400  55.2000 0002500  60.3000 300.4000  1.00270000120002",
    ),
    (
        "METEOSAT-11 (MSG-4)",
        "1 40732U 15034A   24080.50000000  .00000060  00000-0  00000-0 0  9993",
        "2 40732   0.8500  35.4000 0002000  75.1000 285.2000  1.00270000320003",
    ),
    (
        "GPS BIIF-12 (PRN 32)",
        "1 41328U 16007A   24080.50000000  .00000020  00000-0  00000-0 0  9994",
        "2 41328  55.3000  90.2000 0050000 150.2000 210.1000  2.00560000600004",
    ),
    (
        "GALILEO 26 (GSAT0219)",
        "1 43564U 18060A   24080.50000000  .00000015  00000-0  00000-0 0  9995",
        "2 43564  56.0000  75.4000 0003500 120.1000 240.3000  1.70720000350005",
    ),
]


class CatalogService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def parse_tle_elements(
        name: str, line1: str, line2: str
    ) -> Optional[dict]:
        try:
            line0_clean = re.sub(r"^0\s+", "", name).strip()
            sat = Satrec.twoline2rv(line1, line2)
            norad_id = int(line1[2:7])
            intl_des = line1[9:17].strip()

            # Calculate Epoch
            year = sat.epochyr
            full_year = year + 2000 if year < 57 else year + 1900
            epoch_start = datetime(full_year, 1, 1, tzinfo=timezone.utc)
            epoch_ts = epoch_start + timedelta(days=sat.epochdays - 1)

            # Orbit math from mean motion (rad/min)
            n_rad_min = sat.no_kozai
            if n_rad_min <= 0:
                return None

            period_minutes = (2 * math.pi) / n_rad_min
            n_rad_s = n_rad_min / 60.0
            a = (MU / (n_rad_s**2)) ** (1 / 3)
            e = sat.ecco
            apogee = a * (1 + e) - R_EARTH
            perigee = a * (1 - e) - R_EARTH
            inclination = math.degrees(sat.inclo)

            # Determine regime
            if perigee <= 2000.0:
                regime = "LEO"
            elif perigee > 2000.0 and apogee < 35500.0:
                regime = "MEO"
            elif 35500.0 <= apogee <= 36500.0 and e < 0.1:
                regime = "GEO"
            elif apogee > 35500.0 or e >= 0.25:
                regime = "HEO"
            else:
                regime = "OTHER"

            # Determine object type
            name_upper = line0_clean.upper()
            if "DEB" in name_upper or "DEBRIS" in name_upper:
                obj_type = "debris"
            elif "R/B" in name_upper or "ROCKET" in name_upper or "STAGE" in name_upper:
                obj_type = "rocket_body"
            else:
                obj_type = "payload"

            return {
                "norad_id": norad_id,
                "name": line0_clean or f"OBJECT {norad_id}",
                "international_designator": intl_des,
                "object_type": obj_type,
                "orbit_regime": regime,
                "apogee_km": round(apogee, 2),
                "perigee_km": round(perigee, 2),
                "inclination_deg": round(inclination, 2),
                "period_minutes": round(period_minutes, 2),
                "eccentricity": round(e, 6),
                "line1": line1,
                "line2": line2,
                "epoch": epoch_ts,
            }
        except Exception as exc:
            logger.debug(f"Failed to parse TLE for {name}: {exc}")
            return None

    async def seed_starter_catalog_if_empty(self) -> int:
        count_res = await self.session.execute(
            select(func.count(CatalogSatellite.norad_id))
        )
        existing_count = count_res.scalar() or 0
        if existing_count > 0:
            return 0

        logger.info("Catalog is empty. Seeding initial baseline space catalog...")
        added = 0
        for name, l1, l2 in STARTER_CATALOG_TLES:
            parsed = self.parse_tle_elements(name, l1, l2)
            if parsed:
                cat_sat = CatalogSatellite(**parsed)
                await self.session.merge(cat_sat)
                added += 1

        await self.session.commit()
        logger.info(f"Seeded {added} baseline satellites into catalog_satellites.")
        return added

    async def sync_celestrak_active_catalog(self) -> Tuple[int, str]:
        """
        Fetches active satellites from CelesTrak in bulk and upserts into catalog_satellites.
        """
        logger.info("Starting CelesTrak active satellite catalog synchronization...")
        try:
            async with httpx.AsyncClient(
                headers=CELESTRAK_HEADERS, timeout=30.0
            ) as client:
                response = await client.get(CELESTRAK_ACTIVE_URL)
                response.raise_for_status()
                tle_text = response.text
        except Exception as exc:
            logger.warning(
                f"Could not reach CelesTrak bulk endpoint ({exc}). Checking if starter seed needed..."
            )
            seeded = await self.seed_starter_catalog_if_empty()
            if seeded > 0:
                return (
                    seeded,
                    f"CelesTrak unavailable ({exc}); initialized baseline catalog with {seeded} satellites.",
                )
            return (
                0,
                f"Failed to synchronize with CelesTrak: {str(exc)}",
            )

        lines = [l.strip() for l in tle_text.split("\n") if l.strip()]
        if len(lines) < 3:
            return 0, "No satellite data returned from CelesTrak."

        synced_count = 0
        batch = []
        now = datetime.now(timezone.utc)

        idx = 0
        while idx < len(lines):
            # Check if 3-line format (line 0 is name, line 1 starts with 1, line 2 starts with 2)
            if idx + 2 < len(lines) and lines[idx + 1].startswith("1 ") and lines[idx + 2].startswith("2 "):
                name = lines[idx]
                l1 = lines[idx + 1]
                l2 = lines[idx + 2]
                idx += 3
            elif idx + 1 < len(lines) and lines[idx].startswith("1 ") and lines[idx + 1].startswith("2 "):
                name = f"OBJECT {lines[idx][2:7]}"
                l1 = lines[idx]
                l2 = lines[idx + 1]
                idx += 2
            else:
                idx += 1
                continue

            parsed = self.parse_tle_elements(name, l1, l2)
            if not parsed:
                continue

            cat_sat = CatalogSatellite(
                norad_id=parsed["norad_id"],
                name=parsed["name"],
                international_designator=parsed["international_designator"],
                object_type=parsed["object_type"],
                orbit_regime=parsed["orbit_regime"],
                apogee_km=parsed["apogee_km"],
                perigee_km=parsed["perigee_km"],
                inclination_deg=parsed["inclination_deg"],
                period_minutes=parsed["period_minutes"],
                eccentricity=parsed["eccentricity"],
                line1=parsed["line1"],
                line2=parsed["line2"],
                epoch=parsed["epoch"],
                updated_at=now,
            )
            batch.append(cat_sat)
            synced_count += 1

            if len(batch) >= 500:
                for item in batch:
                    await self.session.merge(item)
                await self.session.commit()
                batch = []

        if batch:
            for item in batch:
                await self.session.merge(item)
            await self.session.commit()

        logger.info(f"Successfully synchronized {synced_count} satellites from CelesTrak.")
        return synced_count, f"Successfully synchronized {synced_count} satellites from CelesTrak."

    async def search_catalog(
        self,
        query: Optional[str] = None,
        regime: Optional[str] = None,
        object_type: Optional[str] = None,
        page: int = 1,
        limit: int = 25,
        user_employee_id: Optional[str] = None,
    ) -> CatalogListResponse:
        # Check if table is empty and seed starter if needed
        await self.seed_starter_catalog_if_empty()

        stmt = select(CatalogSatellite)
        count_stmt = select(func.count(CatalogSatellite.norad_id))

        filters = []
        if query and query.strip():
            q = query.strip()
            if q.isdigit():
                filters.append(
                    or_(
                        CatalogSatellite.norad_id == int(q),
                        CatalogSatellite.name.ilike(f"%{q}%"),
                        CatalogSatellite.international_designator.ilike(f"%{q}%"),
                    )
                )
            else:
                filters.append(
                    or_(
                        CatalogSatellite.name.ilike(f"%{q}%"),
                        CatalogSatellite.international_designator.ilike(f"%{q}%"),
                    )
                )

        if regime and regime.upper() != "ALL":
            filters.append(CatalogSatellite.orbit_regime == regime.upper())

        if object_type and object_type.lower() != "all":
            filters.append(CatalogSatellite.object_type == object_type.lower())

        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar() or 0

        # Pagination bounds
        page = max(1, page)
        limit = min(max(1, limit), 100)
        offset = (page - 1) * limit
        total_pages = math.ceil(total / limit) if total > 0 else 1

        stmt = stmt.order_by(CatalogSatellite.name.asc()).offset(offset).limit(limit)
        results = await self.session.execute(stmt)
        catalog_rows = results.scalars().all()

        # Fetch current user's tracked satellites to annotate isTracked
        tracked_map = {}
        if user_employee_id:
            user_sats_stmt = select(Satellite).where(Satellite.owner_org == user_employee_id)
            user_sats_res = await self.session.execute(user_sats_stmt)
            for sat in user_sats_res.scalars().all():
                tracked_map[sat.norad_id] = str(sat.id)

        items = [
            CatalogItemResponse(
                noradId=row.norad_id,
                name=row.name,
                internationalDesignator=row.international_designator,
                objectType=row.object_type or "payload",
                orbitRegime=row.orbit_regime or "LEO",
                apogeeKm=row.apogee_km,
                perigeeKm=row.perigee_km,
                inclinationDeg=row.inclination_deg,
                periodMinutes=row.period_minutes,
                isTracked=(row.norad_id in tracked_map),
                trackedSatelliteId=tracked_map.get(row.norad_id),
                epoch=row.epoch,
            )
            for row in catalog_rows
        ]

        return CatalogListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            totalPages=total_pages,
        )
