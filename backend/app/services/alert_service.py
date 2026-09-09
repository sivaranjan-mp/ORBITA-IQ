from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Union
import uuid
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.alerts import Alert, AlertHistory, AlertStatusHistory, ConjunctionAlert
from app.models.conjunctions import ConjunctionEvent
from app.repositories.alerts_repository import AlertsRepository

SIMULATED_COLLISION_DATA = [
    {"a_name": "STARLETTE", "a_norad": 7646, "b_name": "COSMOS 1408 DEB", "b_norad": 49863, "days": 7.20, "miss_km": 8.45, "vel_kms": 13.8, "pc": 3.4e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "ISS (ZARYA)", "a_norad": 25544, "b_name": "CZ-4B DEB", "b_norad": 25942, "days": 7.55, "miss_km": 34.20, "vel_kms": 11.2, "pc": 4.1e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "AJISAI (EGS)", "a_norad": 16908, "b_name": "SL-16 R/B", "b_norad": 22285, "days": 7.90, "miss_km": 11.35, "vel_kms": 14.1, "pc": 1.9e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "CALSPHERE 1", "a_norad": 900, "b_name": "FENGYUN 1C DEB", "b_norad": 29657, "days": 8.30, "miss_km": 41.50, "vel_kms": 12.6, "pc": 2.2e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "CALSPHERE 2", "a_norad": 902, "b_name": "THOR ABLESTAR DEB", "b_norad": 224, "days": 8.75, "miss_km": 15.80, "vel_kms": 9.8, "pc": 8.6e-6, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "LCS 1", "a_norad": 1361, "b_name": "DELTA 1 DEB", "b_norad": 14812, "days": 9.15, "miss_km": 28.40, "vel_kms": 10.4, "pc": 6.8e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "STARLINK-1007", "a_norad": 44713, "b_name": "IRIDIUM 33 DEB", "b_norad": 33750, "days": 9.55, "miss_km": 6.25, "vel_kms": 14.7, "pc": 4.6e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "TIANGONG", "a_norad": 48274, "b_name": "CZ-2C DEB", "b_norad": 40051, "days": 9.90, "miss_km": 36.80, "vel_kms": 8.9, "pc": 3.3e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "NOAA-20", "a_norad": 43013, "b_name": "YAOGAN-30 DEB", "b_norad": 43232, "days": 10.30, "miss_km": 13.90, "vel_kms": 12.1, "pc": 1.4e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "SENTINEL-6A", "a_norad": 46984, "b_name": "ARIANE 40 DEB", "b_norad": 23561, "days": 10.70, "miss_km": 45.10, "vel_kms": 11.5, "pc": 1.6e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "HUBBLE SPACE TELESCOPE", "a_norad": 20580, "b_name": "TITAN 3C DEB", "b_norad": 3433, "days": 11.10, "miss_km": 9.60, "vel_kms": 13.4, "pc": 2.8e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "TERRA", "a_norad": 25994, "b_name": "PEGASUS DEB", "b_norad": 24027, "days": 11.50, "miss_km": 32.10, "vel_kms": 9.3, "pc": 4.9e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "AQUA", "a_norad": 27424, "b_name": "COSMOS 2251 DEB", "b_norad": 33591, "days": 11.90, "miss_km": 18.40, "vel_kms": 14.5, "pc": 6.7e-6, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "LANDSAT 9", "a_norad": 49260, "b_name": "ATLAS CENTAUR DEB", "b_norad": 19046, "days": 12.30, "miss_km": 26.90, "vel_kms": 10.8, "pc": 7.5e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "SUOMI NPP", "a_norad": 37849, "b_name": "PSLV DEB", "b_norad": 44105, "days": 12.70, "miss_km": 21.70, "vel_kms": 11.9, "pc": 5.4e-6, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "ABS-4 (MOBISAT-1)", "a_norad": 28184, "b_name": "H-2A DEB", "b_norad": 38341, "days": 13.10, "miss_km": 38.60, "vel_kms": 13.0, "pc": 2.9e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "ABS-6", "a_norad": 25924, "b_name": "BREEZE-M DEB", "b_norad": 38753, "days": 13.45, "miss_km": 7.80, "vel_kms": 14.2, "pc": 3.7e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "GOES 16", "a_norad": 41866, "b_name": "DELTA 2 DEB", "b_norad": 25862, "days": 13.75, "miss_km": 47.30, "vel_kms": 8.7, "pc": 1.2e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "GOES 18", "a_norad": 51850, "b_name": "THOR AGENA DEB", "b_norad": 1344, "days": 13.90, "miss_km": 12.40, "vel_kms": 12.3, "pc": 1.6e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "METEOSAT-11 (MSG-4)", "a_norad": 40732, "b_name": "TIANGONG", "b_norad": 48274, "days": 14.00, "miss_km": 29.50, "vel_kms": 7.8, "pc": 6.2e-7, "risk": "low", "scope": "fleet_vs_fleet", "status": "open"},
]


class AlertService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AlertsRepository(session)

    async def seed_simulated_alerts(self) -> List[ConjunctionAlert]:
        # If alerts already exist in the database, return them to maintain fixed historical TCAs
        existing = await self.repository.get_all_conjunction_alerts()
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        created_alerts = []
        for idx, item in enumerate(SIMULATED_COLLISION_DATA):
            per_pair_sec_offset = ((item["a_norad"] * 73 + item["b_norad"] * 31 + idx * 137) % 86400) / 100.0
            tca_time = now + timedelta(days=item["days"], seconds=per_pair_sec_offset)
            miss_km = item["miss_km"]
            vel_kms = item["vel_kms"]

            # Compute physically consistent RIC decomposition: miss_km^2 = R^2 + I^2 + C^2
            radial_km = round(miss_km * 0.22, 3)
            along_track_km = round(miss_km * 0.88, 3)
            cross_sq = max(0.0, miss_km ** 2 - radial_km ** 2 - along_track_km ** 2)
            cross_track_km = round(cross_sq ** 0.5, 3)

            vel_angle = round(min(179.0, max(2.0, vel_kms * 6.8)), 1)
            inc_angle = round(min(90.0, max(0.5, vel_kms * 4.5)), 1)
            enc_geom = (
                "co-orbital"
                if (vel_kms < 2.0 and inc_angle < 5.0)
                else ("head-on" if vel_angle >= 135.0 else "crossing")
            )

            alert = ConjunctionAlert(
                id=uuid.uuid4(),
                satellite_a_norad_id=item["a_norad"],
                satellite_a_name=item["a_name"],
                satellite_b_norad_id=item["b_norad"],
                satellite_b_name=item["b_name"],
                screening_scope=item["scope"],
                tca=tca_time,
                miss_distance_km=miss_km,
                miss_distance_m=miss_km * 1000.0,
                relative_velocity_km_s=vel_kms,
                probability=item["pc"],
                risk_level=item["risk"],
                status=item["status"],
                detected_by="satguard_simulated",
                relative_position_x=radial_km,
                relative_position_y=along_track_km,
                relative_position_z=cross_track_km,
                relative_velocity_x=round(vel_kms * 0.15, 2),
                relative_velocity_y=round(vel_kms * 0.75, 2),
                relative_velocity_z=round(vel_kms * 0.64, 2),
                radial_separation_km=radial_km,
                along_track_separation_km=along_track_km,
                cross_track_separation_km=cross_track_km,
                relative_velocity_angle_deg=vel_angle,
                relative_inclination_deg=inc_angle,
                encounter_geometry=enc_geom,
                computed_at=now,
                created_at=now,
            )
            self.session.add(alert)
            created_alerts.append(alert)

        await self.session.commit()
        return created_alerts

    async def get_all_conjunction_alerts(self) -> List[ConjunctionAlert]:
        return await self.repository.get_all_conjunction_alerts()

    async def get_all_alerts(self) -> List[Union[ConjunctionAlert, Alert]]:
        try:
            alerts = await self.repository.get_all_conjunction_alerts()
            if alerts:
                return alerts
        except Exception:
            pass

        legacy_alerts = await self.repository.get_all_alerts()
        if legacy_alerts:
            return legacy_alerts

        # Automatically seed and return simulated 7-14 day alerts
        try:
            return await self.seed_simulated_alerts()
        except Exception:
            return []

    async def get_alert(self, alert_id: str) -> Optional[Union[ConjunctionAlert, Alert]]:
        try:
            conj_alert = await self.repository.get_conjunction_alert_by_id(alert_id)
            if conj_alert:
                return conj_alert
        except Exception:
            pass
        return await self.repository.get_alert_by_id(alert_id)

    async def update_alert_status(
        self,
        alert_id: str,
        new_status: str,
        changed_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Union[ConjunctionAlert, Alert]]:
        alert = await self.get_alert(alert_id)
        if not alert:
            return None

        if isinstance(alert, ConjunctionAlert):
            prev_status = alert.status
            alert.status = new_status
            alert.updated_at = datetime.now(timezone.utc)
            self.session.add(alert)

            user_uuid = None
            if changed_by:
                try:
                    user_uuid = uuid.UUID(str(changed_by))
                except (ValueError, TypeError):
                    user_uuid = None

            status_history = AlertStatusHistory(
                id=uuid.uuid4(),
                alert_id=alert.id,
                previous_status=prev_status,
                new_status=new_status,
                changed_by=user_uuid,
                changed_at=datetime.now(timezone.utc),
                notes=notes,
            )
            self.session.add(status_history)
            await self.session.commit()
            await self.session.refresh(alert)
            return alert

        # Legacy Alert
        history = AlertHistory(
            alert_id=alert.id,
            risk_level=alert.risk_level,
            miss_distance=alert.miss_distance,
            relative_velocity=alert.relative_velocity,
            timestamp=datetime.now(timezone.utc)
        )

        alert.status = new_status
        self.session.add(history)
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)

        return alert

    async def get_alert_history(
        self,
        page: int = 1,
        limit: int = 20,
        alert_id: Optional[str] = None
    ) -> Tuple[List[AlertStatusHistory], int]:
        return await self.repository.get_alert_status_history(page=page, limit=limit, alert_id=alert_id)


    async def create_alert_from_conjunction(self, event: ConjunctionEvent) -> Alert:
        existing = await self.session.execute(
            select(Alert).where(Alert.conjunction_event_id == event.id)
        )
        alert = existing.scalars().first()

        if alert:
            alert.risk_level = event.risk_level
            alert.miss_distance = event.miss_distance_m
            alert.relative_velocity = event.relative_velocity_km_s
            alert.time_of_closest_approach = event.tca

            history = AlertHistory(
                alert_id=alert.id,
                risk_level=alert.risk_level,
                miss_distance=alert.miss_distance,
                relative_velocity=alert.relative_velocity,
                timestamp=datetime.now(timezone.utc)
            )
            self.session.add(history)
            self.session.add(alert)
        else:
            from app.models.satellites import Satellite
            sat_a = (await self.session.execute(select(Satellite).where(Satellite.norad_id == event.primary_norad_id))).scalars().first()
            sat_b = (await self.session.execute(select(Satellite).where(Satellite.norad_id == event.secondary_norad_id))).scalars().first()

            if not sat_a:
                raise ValueError(f"Primary satellite with NORAD ID {event.primary_norad_id} not found")

            alert = Alert(
                conjunction_event_id=event.id,
                satellite_a_id=sat_a.id,
                satellite_b_id=sat_b.id if sat_b else None,
                miss_distance=event.miss_distance_m,
                relative_velocity=event.relative_velocity_km_s,
                time_of_closest_approach=event.tca,
                risk_level=event.risk_level,
                status='active'
            )
            self.session.add(alert)
            await self.session.flush()

            history = AlertHistory(
                alert_id=alert.id,
                risk_level=alert.risk_level,
                miss_distance=alert.miss_distance,
                relative_velocity=alert.relative_velocity,
                timestamp=datetime.now(timezone.utc)
            )
            self.session.add(history)

        await self.session.commit()
        await self.session.refresh(alert)
        return alert
