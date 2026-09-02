import json
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.satellites import Satellite, OrbitState, TLERecord, OMMRecord
from app.services.celestrak_service import fetch_tle_by_norad_id
from app.services.tle_parser import parse_tle
from app.services.omm_parser import parse_omm_json
from app.schemas.satellites import SatelliteAddRequest, SatelliteUpdateRequest, TLEUploadRequest, OMMUploadRequest

logger = logging.getLogger(__name__)

class SatelliteService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_satellites(self, owner_org: Optional[str] = None) -> List[Satellite]:
        stmt = select(Satellite).options(
            selectinload(Satellite.orbit_state),
            selectinload(Satellite.tle_records)
        )
        if owner_org:
            stmt = stmt.where(Satellite.owner_org == owner_org)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_satellite_by_id(self, sat_id: str) -> Optional[Satellite]:
        stmt = select(Satellite).where(Satellite.id == sat_id).options(
            selectinload(Satellite.orbit_state),
            selectinload(Satellite.tle_records)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_satellite_by_norad(self, norad_id: int) -> Optional[Satellite]:
        stmt = select(Satellite).where(Satellite.norad_id == norad_id).options(
            selectinload(Satellite.orbit_state),
            selectinload(Satellite.tle_records)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_satellite_by_norad(self, norad_id: int, owner_org: str = "Unknown") -> Satellite:
        existing = await self.get_satellite_by_norad(norad_id)
        if existing:
            return existing

        raw_tle = await fetch_tle_by_norad_id(norad_id)
        parsed = parse_tle(raw_tle)

        sat_name = parsed.get("name") or "Unknown"

        sat = Satellite(
            norad_id=norad_id,
            name=sat_name,
            international_designator=parsed["international_designator"],
            object_type="payload",
            status="active",
            owner_org=owner_org
        )

        orbit = OrbitState(
            altitude_km=parsed["altitudeKm"],
            latitude_deg=parsed.get("latitudeDeg"),
            longitude_deg=parsed.get("longitudeDeg"),
            velocity_km_s=parsed.get("velocityKmS"),
            inclination_deg=parsed["inclinationDeg"],
            period_minutes=parsed["periodMinutes"],
            eccentricity=parsed["eccentricity"],
            raan_deg=parsed["raanDeg"],
            mean_anomaly_deg=parsed["meanAnomalyDeg"],
            epoch=parsed["epoch"]
        )
        sat.orbit_state = orbit

        tle = TLERecord(
            line1=parsed["line1"],
            line2=parsed["line2"],
            source="celestrak",
            epoch=parsed["epoch"]
        )
        sat.tle_records.append(tle)

        self.session.add(sat)
        await self.session.commit()
        result = await self.session.execute(
            select(Satellite)
            .where(Satellite.id == sat.id)
            .options(selectinload(Satellite.orbit_state), selectinload(Satellite.tle_records))
        )
        return result.scalar_one()

    async def add_satellite_from_tle(self, raw_tle: str, owner_org: str = "Unknown") -> Satellite:
        parsed = parse_tle(raw_tle)
        norad_id = parsed["norad_id"]

        existing = await self.get_satellite_by_norad(norad_id)
        if existing:
            return existing

        sat_name = parsed.get("name")
        if not sat_name:
            # Fall back to CelesTrak name lookup by NORAD ID parsed from line 1
            try:
                celestrak_tle = await fetch_tle_by_norad_id(norad_id)
                celestrak_parsed = parse_tle(celestrak_tle)
                sat_name = celestrak_parsed.get("name")
            except Exception as exc:
                logger.warning(
                    f"Could not resolve satellite name for NORAD {norad_id} from CelesTrak: {exc}"
                )
                sat_name = None

        if not sat_name:
            sat_name = "Unknown"

        sat = Satellite(
            norad_id=norad_id,
            name=sat_name,
            international_designator=parsed["international_designator"],
            object_type="payload",
            status="active",
            owner_org=owner_org
        )

        orbit = OrbitState(
            altitude_km=parsed["altitudeKm"],
            latitude_deg=parsed.get("latitudeDeg"),
            longitude_deg=parsed.get("longitudeDeg"),
            velocity_km_s=parsed.get("velocityKmS"),
            inclination_deg=parsed["inclinationDeg"],
            period_minutes=parsed["periodMinutes"],
            eccentricity=parsed["eccentricity"],
            raan_deg=parsed["raanDeg"],
            mean_anomaly_deg=parsed["meanAnomalyDeg"],
            epoch=parsed["epoch"]
        )
        sat.orbit_state = orbit

        tle = TLERecord(
            line1=parsed["line1"],
            line2=parsed["line2"],
            source="manual_upload",
            epoch=parsed["epoch"]
        )
        sat.tle_records.append(tle)

        self.session.add(sat)
        await self.session.commit()
        result = await self.session.execute(
            select(Satellite)
            .where(Satellite.id == sat.id)
            .options(selectinload(Satellite.orbit_state), selectinload(Satellite.tle_records))
        )
        return result.scalar_one()

    async def update_satellite(self, sat_id: str, updates: SatelliteUpdateRequest) -> Satellite:
        sat = await self.get_satellite_by_id(sat_id)
        if not sat:
            raise ValueError("Satellite not found")

        if updates.name is not None:
            sat.name = updates.name
        if updates.ownerOrg is not None:
            sat.owner_org = updates.ownerOrg
        if updates.status is not None:
            sat.status = updates.status

        await self.session.commit()
        result = await self.session.execute(
            select(Satellite)
            .where(Satellite.id == sat.id)
            .options(selectinload(Satellite.orbit_state), selectinload(Satellite.tle_records))
        )
        return result.scalar_one()

    async def delete_satellite(self, sat_id: str) -> bool:
        sat = await self.get_satellite_by_id(sat_id)
        if not sat:
            return False

        await self.session.delete(sat)
        await self.session.commit()
        return True

    async def upload_tle(self, norad_id: int, raw_tle: str) -> Satellite:
        sat = await self.get_satellite_by_norad(norad_id)
        if not sat:
            raise ValueError(f"Satellite with NORAD ID {norad_id} not found")

        parsed = parse_tle(raw_tle)

        if sat.name in ("Unknown", "", "Unknown Object") and parsed.get("name"):
            sat.name = parsed["name"]

        tle = TLERecord(
            line1=parsed["line1"],
            line2=parsed["line2"],
            source="manual_upload",
            epoch=parsed["epoch"]
        )
        sat.tle_records.append(tle)

        if sat.orbit_state:
            sat.orbit_state.altitude_km = parsed["altitudeKm"]
            sat.orbit_state.latitude_deg = parsed.get("latitudeDeg")
            sat.orbit_state.longitude_deg = parsed.get("longitudeDeg")
            sat.orbit_state.velocity_km_s = parsed.get("velocityKmS")
            sat.orbit_state.inclination_deg = parsed["inclinationDeg"]
            sat.orbit_state.period_minutes = parsed["periodMinutes"]
            sat.orbit_state.eccentricity = parsed["eccentricity"]
            sat.orbit_state.raan_deg = parsed["raanDeg"]
            sat.orbit_state.mean_anomaly_deg = parsed["meanAnomalyDeg"]
            sat.orbit_state.epoch = parsed["epoch"]

        await self.session.commit()
        result = await self.session.execute(
            select(Satellite)
            .where(Satellite.id == sat.id)
            .options(selectinload(Satellite.orbit_state), selectinload(Satellite.tle_records))
        )
        return result.scalar_one()

    async def upload_omm(self, payload: dict) -> Satellite:
        parsed = parse_omm_json(payload)
        norad_id = parsed.get("norad_id")

        if not norad_id:
            raise ValueError("Missing NORAD_CAT_ID in OMM payload")

        sat = await self.get_satellite_by_norad(norad_id)
        if not sat:
            raise ValueError(f"Satellite with NORAD ID {norad_id} not found")

        omm = OMMRecord(
            epoch=parsed["epoch"],
            payload=payload
        )
        sat.omm_records.append(omm)

        # In a real app we'd also parse the OMM state to update orbit_state
        await self.session.commit()
        result = await self.session.execute(
            select(Satellite)
            .where(Satellite.id == sat.id)
            .options(
                selectinload(Satellite.orbit_state),
                selectinload(Satellite.tle_records),
                selectinload(Satellite.omm_records)
            )
        )
        return result.scalar_one()
