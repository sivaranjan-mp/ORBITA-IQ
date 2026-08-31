import logging
import asyncio
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_maker
from app.models.satellites import Satellite, OrbitState
from app.models.enums import SatelliteStatus
from app.services.celestrak_service import fetch_tle_by_norad_id
from app.services.sgp4_service import propagate_tle
from app.api.v1.endpoints.orbit_ws import orbit_manager

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def update_orbit_states():
    """
    Background job to fetch TLEs, propagate orbits, update database,
    and broadcast to WebSockets.
    """
    logger.info("Starting scheduled orbit state update.")

    async with async_session_maker() as db:
        try:
            # Fetch all active tracked satellites with their stored TLE records
            stmt = select(Satellite).where(Satellite.status == SatelliteStatus.ACTIVE).options(
                selectinload(Satellite.tle_records)
            )
            result = await db.execute(stmt)
            satellites = result.scalars().all()

            now = datetime.now(timezone.utc)
            # 1. Fetch or fallback TLE and propagate all orbits sequentially
            computed_states = {}
            for sat in satellites:
                try:
                    line1, line2 = None, None

                    # Attempt fresh fetch from CelesTrak if possible
                    try:
                        await asyncio.sleep(0.5)
                        tle_text = await fetch_tle_by_norad_id(sat.norad_id)
                        lines = [l.strip() for l in tle_text.strip().split("\n") if l.strip()]
                        if len(lines) >= 3:
                            line1, line2 = lines[1], lines[2]
                        elif len(lines) == 2:
                            line1, line2 = lines[0], lines[1]
                    except Exception as exc:
                        logger.debug(f"CelesTrak fetch unavailable for NORAD {sat.norad_id}, falling back to stored TLE: {exc}")

                    # If CelesTrak fetch was unavailable, fall back to the latest stored TLE in DB
                    if not line1 or not line2:
                        if sat.tle_records:
                            latest_tle = max(sat.tle_records, key=lambda t: t.epoch)
                            line1, line2 = latest_tle.line1, latest_tle.line2

                    if not line1 or not line2:
                        logger.warning(f"No TLE available to propagate for satellite {sat.norad_id}")
                        continue

                    state = propagate_tle(line1, line2, now)
                    if not state:
                        logger.warning(f"Failed to propagate TLE for satellite {sat.norad_id}")
                        continue

                    computed_states[sat.id] = state

                except Exception as e:
                    logger.error(f"Error processing satellite {sat.norad_id}: {e}")
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

                        # Prepare update for websocket
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
                    logger.exception(f"Error during bulk DB update in update_orbit_states: {e}")
                    await db.rollback()
                    raise

            # Broadcast updates if there are any connections
            if updates_to_broadcast:
                await orbit_manager.broadcast_orbit_updates(updates_to_broadcast)

            logger.info(
                f"Finished orbit state update for {len(updates_to_broadcast)} satellites.")

        except Exception as e:
            logger.exception(f"Critical error in scheduled orbit update: {e}")
            await db.rollback()
            raise


async def run_screening_job():
    logger.info("Starting scheduled conjunction screening.")
    from app.services.satguard_service import SatguardService
    async with async_session_maker() as db:
        try:
            service = SatguardService(db)
            events_created = await service.screen_all(lookahead_hours=72, step_size_s=60, miss_dist_threshold_km=5.0)
            logger.info(
                f"Finished conjunction screening. {events_created} events created.")
        except Exception as e:
            logger.exception(f"Critical error in scheduled screening: {e}")
            await db.rollback()
            raise


def init_scheduler():
    scheduler.add_job(update_orbit_states, 'interval', minutes=5,
                      id='update_orbit_states_job', replace_existing=True)
    scheduler.add_job(run_screening_job, 'interval', minutes=30,
                      id='run_screening_job', replace_existing=True)
    scheduler.start()


def shutdown_scheduler():
    scheduler.shutdown()
