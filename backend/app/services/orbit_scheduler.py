import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.orbit_ws import orbit_manager
from app.core.constants import DEFAULT_LOOKAHEAD_HOURS, COARSE_STEP_SECONDS, MAX_SCREEN_MISS_DISTANCE_KM
from app.db.session import async_session_maker
from app.models.catalog import CatalogSatellite
from app.models.enums import SatelliteStatus
from app.models.satellites import OrbitState, Satellite
from app.services.celestrak_service import fetch_tle_by_norad_id
from app.services.sgp4_service import propagate_tle

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def update_orbit_states():
    """
    Background job triggered on scheduler interval.
    Propagates all active fleet satellites using SGP4 and updates database and WebSockets.
    """
    logger.info("Starting scheduled fleet orbit state propagation.")

    async with async_session_maker() as db:
        try:
            # 1. Fetch active satellites with their stored TLE records
            try:
                stmt = select(Satellite).where(Satellite.status == SatelliteStatus.ACTIVE).options(
                    selectinload(Satellite.tle_records)
                )
                result = await db.execute(stmt)
                satellites = result.scalars().all()
            except Exception as query_err:
                logger.warning(
                    f"Direct ENUM query on Satellite.status failed ({query_err}), falling back to text cast query."
                )
                raw_stmt = select(Satellite).where(text("satellites.status::text = 'active'")).options(
                    selectinload(Satellite.tle_records)
                )
                result = await db.execute(raw_stmt)
                satellites = result.scalars().all()

            # Pre-load catalog satellites mapping as fallback
            cat_tle_map = {}
            try:
                cat_stmt = select(CatalogSatellite.norad_id, CatalogSatellite.line1, CatalogSatellite.line2)
                cat_res = await db.execute(cat_stmt)
                cat_tle_map = {row[0]: (row[1], row[2]) for row in cat_res.all()}
            except Exception:
                pass

            now = datetime.now(timezone.utc)
            computed_states = {}

            for sat in satellites:
                try:
                    line1, line2 = None, None

                    # Primary: latest stored TLE in tle_records
                    if sat.tle_records:
                        latest_tle = max(sat.tle_records, key=lambda t: t.epoch)
                        line1, line2 = latest_tle.line1, latest_tle.line2

                    # Fallback 1: catalog_satellites
                    if (not line1 or not line2) and sat.norad_id in cat_tle_map:
                        line1, line2 = cat_tle_map[sat.norad_id]

                    # Fallback 2: fetch_tle_by_norad_id
                    if not line1 or not line2:
                        try:
                            tle_text = await fetch_tle_by_norad_id(sat.norad_id)
                            lines = [l.strip() for l in tle_text.strip().split("\n") if l.strip()]
                            if len(lines) >= 3:
                                line1, line2 = lines[1], lines[2]
                            elif len(lines) == 2:
                                line1, line2 = lines[0], lines[1]
                        except Exception as exc:
                            logger.debug(f"TLE fetch unavailable for NORAD {sat.norad_id}: {exc}")

                    if not line1 or not line2:
                        continue

                    state = propagate_tle(line1, line2, now)
                    if state:
                        computed_states[sat.id] = state

                except Exception as e:
                    logger.debug(f"Error propagating satellite {sat.norad_id}: {e}")
                    continue

            # 2. Bulk Database Update
            updates_to_broadcast = []
            if computed_states:
                try:
                    sat_results = await db.execute(
                        select(Satellite)
                        .where(Satellite.id.in_(computed_states.keys()))
                        .with_for_update()
                        .options(selectinload(Satellite.orbit_state))
                    )
                    sats_to_update = sat_results.scalars().all()

                    for sat in sats_to_update:
                        state = computed_states[sat.id]
                        if not sat.orbit_state:
                            sat.orbit_state = OrbitState(satellite_id=sat.id, **state)
                            db.add(sat.orbit_state)
                        else:
                            for key, value in state.items():
                                setattr(sat.orbit_state, key, value)

                        updates_to_broadcast.append({
                            "satelliteId": str(sat.id),
                            "noradId": sat.norad_id,
                            "altitudeKm": state["altitude_km"],
                            "latitudeDeg": state["latitude_deg"],
                            "longitudeDeg": state["longitude_deg"],
                            "velocityKmS": state["velocity_km_s"],
                            "epoch": state["epoch"].isoformat(),
                            "inclinationDeg": state["inclination_deg"],
                            "periodMinutes": state["period_minutes"]
                        })

                    await db.commit()
                except Exception as e:
                    logger.exception(f"Error during DB update in update_orbit_states: {e}")
                    await db.rollback()
                    raise

            if updates_to_broadcast:
                await orbit_manager.broadcast_orbit_updates(updates_to_broadcast)

            logger.info(f"Finished orbit state update for {len(updates_to_broadcast)} satellites.")

        except Exception as e:
            logger.exception(f"Critical error in scheduled orbit update: {e}")
            await db.rollback()
            raise


propagate_fleet_job = update_orbit_states


async def run_screening_job():
    """
    Scheduled 5-day (120-hour) conjunction assessment run.
    """
    logger.info("Starting scheduled 5-day conjunction screening job.")
    from app.services.satguard_service import SatguardService
    async with async_session_maker() as db:
        try:
            service = SatguardService(db)
            metrics = await service.screen_all(
                lookahead_hours=DEFAULT_LOOKAHEAD_HOURS,
                step_size_s=COARSE_STEP_SECONDS,
                miss_dist_threshold_km=MAX_SCREEN_MISS_DISTANCE_KM
            )
            logger.info(
                f"Finished conjunction screening in {metrics.get('duration_seconds')}s. "
                f"Events created: {metrics.get('events_created')}, Stage 1 survivors: {metrics.get('stage1_survivors')}"
            )
        except Exception as e:
            logger.exception(f"Critical error in scheduled screening: {e}")
            await db.rollback()
            raise


async def run_catalog_sync_job():
    logger.info("Starting scheduled periodic catalog synchronization with CelesTrak.")
    from app.services.catalog_service import CatalogService
    try:
        await CatalogService.run_sync_background_job()
    except Exception as e:
        logger.exception(f"Critical error in scheduled catalog sync: {e}")


def init_scheduler():
    scheduler.add_job(
        update_orbit_states, 'interval', minutes=5,
        id='update_orbit_states_job', replace_existing=True
    )
    scheduler.add_job(
        run_screening_job, 'interval', minutes=20,
        id='run_screening_job', replace_existing=True
    )
    scheduler.add_job(
        run_catalog_sync_job, 'interval', hours=12,
        id='catalog_sync_job', replace_existing=True
    )
    scheduler.start()


def shutdown_scheduler():
    scheduler.shutdown()
