from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union
import uuid
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.alerts import Alert, AlertHistory, ConjunctionAlert
from app.models.conjunctions import ConjunctionEvent
from app.repositories.alerts_repository import AlertsRepository

SIMULATED_COLLISION_DATA = [
    {"a_name": "STARLINK-1007", "a_norad": 44713, "b_name": "COSMOS 1408 DEB", "b_norad": 49863, "days": 7.25, "miss_km": 8.45, "vel_kms": 13.8, "pc": 3.4e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "ISS (ZARYA)", "a_norad": 25544, "b_name": "CZ-4B DEB", "b_norad": 25942, "days": 7.60, "miss_km": 34.20, "vel_kms": 11.2, "pc": 4.1e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "NOAA-20", "a_norad": 43013, "b_name": "SL-16 R/B", "b_norad": 22285, "days": 8.15, "miss_km": 11.35, "vel_kms": 14.1, "pc": 1.9e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "ONEWEB-0120", "a_norad": 45145, "b_name": "FENGYUN 1C DEB", "b_norad": 29657, "days": 8.50, "miss_km": 41.50, "vel_kms": 12.6, "pc": 2.2e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "SENTINEL-6A", "a_norad": 46984, "b_name": "THOR ABLESTAR DEB", "b_norad": 224, "days": 8.90, "miss_km": 15.80, "vel_kms": 9.8, "pc": 8.6e-6, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "HUBBLE ST", "a_norad": 20580, "b_name": "DELTA 1 DEB", "b_norad": 14812, "days": 9.30, "miss_km": 28.40, "vel_kms": 10.4, "pc": 6.8e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "TERRA", "a_norad": 25994, "b_name": "IRIDIUM 33 DEB", "b_norad": 33750, "days": 9.75, "miss_km": 6.25, "vel_kms": 14.7, "pc": 4.6e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "TIANGONG", "a_norad": 48274, "b_name": "CZ-2C DEB", "b_norad": 40051, "days": 10.10, "miss_km": 36.80, "vel_kms": 8.9, "pc": 3.3e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "STARLINK-3011", "a_norad": 52758, "b_name": "YAOGAN-30 DEB", "b_norad": 43232, "days": 10.55, "miss_km": 13.90, "vel_kms": 12.1, "pc": 1.4e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "AQUA", "a_norad": 27424, "b_name": "ARIANE 40 DEB", "b_norad": 23561, "days": 10.95, "miss_km": 45.10, "vel_kms": 11.5, "pc": 1.6e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "LANDSAT-9", "a_norad": 49260, "b_name": "TITAN 3C DEB", "b_norad": 3433, "days": 11.35, "miss_km": 9.60, "vel_kms": 13.4, "pc": 2.8e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "SWIFT", "a_norad": 28485, "b_name": "PEGASUS DEB", "b_norad": 24027, "days": 11.70, "miss_km": 32.10, "vel_kms": 9.3, "pc": 4.9e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "ENVISAT", "a_norad": 27386, "b_name": "COSMOS 2251 DEB", "b_norad": 33591, "days": 12.10, "miss_km": 18.40, "vel_kms": 14.5, "pc": 6.7e-6, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "RADARSAT-2", "a_norad": 32382, "b_name": "ATLAS CENTAUR DEB", "b_norad": 19046, "days": 12.45, "miss_km": 26.90, "vel_kms": 10.8, "pc": 7.5e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "CRYOSAT-2", "a_norad": 36508, "b_name": "PSLV DEB", "b_norad": 44105, "days": 12.80, "miss_km": 21.70, "vel_kms": 11.9, "pc": 5.4e-6, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "METOP-C", "a_norad": 43689, "b_name": "H-2A DEB", "b_norad": 38341, "days": 13.15, "miss_km": 38.60, "vel_kms": 13.0, "pc": 2.9e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "GPM-CORE", "a_norad": 39574, "b_name": "BREEZE-M DEB", "b_norad": 38753, "days": 13.45, "miss_km": 7.80, "vel_kms": 14.2, "pc": 3.7e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "JASON-3", "a_norad": 41240, "b_name": "DELTA 2 DEB", "b_norad": 25862, "days": 13.75, "miss_km": 47.30, "vel_kms": 8.7, "pc": 1.2e-7, "risk": "low", "scope": "fleet_vs_catalog", "status": "open"},
    {"a_name": "ICESAT-2", "a_norad": 43613, "b_name": "THOR AGENA DEB", "b_norad": 1344, "days": 13.90, "miss_km": 12.40, "vel_kms": 12.3, "pc": 1.6e-5, "risk": "medium", "scope": "fleet_vs_catalog", "status": "monitoring"},
    {"a_name": "STARLINK-1007", "a_norad": 44713, "b_name": "TIANGONG", "b_norad": 48274, "days": 14.00, "miss_km": 29.50, "vel_kms": 7.8, "pc": 6.2e-7, "risk": "low", "scope": "fleet_vs_fleet", "status": "open"},
]


class AlertService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AlertsRepository(session)

    async def seed_simulated_alerts(self) -> List[ConjunctionAlert]:
        now = datetime.now(timezone.utc)
        created_alerts = []
        for item in SIMULATED_COLLISION_DATA:
            tca_time = now + timedelta(days=item["days"])
            alert = ConjunctionAlert(
                id=uuid.uuid4(),
                satellite_a_norad_id=item["a_norad"],
                satellite_a_name=item["a_name"],
                satellite_b_norad_id=item["b_norad"],
                satellite_b_name=item["b_name"],
                screening_scope=item["scope"],
                tca=tca_time,
                miss_distance_km=item["miss_km"],
                miss_distance_m=item["miss_km"] * 1000.0,
                relative_velocity_km_s=item["vel_kms"],
                probability=item["pc"],
                risk_level=item["risk"],
                status=item["status"],
                detected_by="satguard_simulated",
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

    async def update_alert_status(self, alert_id: str, new_status: str) -> Optional[Union[ConjunctionAlert, Alert]]:
        alert = await self.get_alert(alert_id)
        if not alert:
            return None

        if isinstance(alert, ConjunctionAlert):
            alert.status = new_status
            alert.updated_at = datetime.now(timezone.utc)
            self.session.add(alert)
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
