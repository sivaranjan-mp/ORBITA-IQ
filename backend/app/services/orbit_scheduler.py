import logging
import asyncio
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_maker
from app.models.satellites import Satellite, OrbitState
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
            # Fetch all active tracked satellites
            # Assuming 'status' == 'active' means we track it
            result = await db.execute(select(Satellite.id, Satellite.norad_id).where(Satellite.status == 'active'))
            satellites = result.all()

            now = datetime.now(timezone.utc)
            updates_to_broadcast = []

            for sat_id, norad_id in satellites:
                try:
                    # Respect CelesTrak rate limits: small sleep between requests
                    await asyncio.sleep(0.5)

                    tle_text = await fetch_tle_by_norad_id(norad_id)
                    lines = tle_text.strip().split("\n")
                    if len(lines) < 2:
                        continue

                    # Handle optional name line
                    if len(lines) >= 3:
                        line1, line2 = lines[1].strip(), lines[2].strip()
                    else:
                        line1, line2 = lines[0].strip(), lines[1].strip()

                    state = propagate_tle(line1, line2, now)
                    if not state:
                        logger.warning(f"Failed to propagate TLE for satellite {norad_id}")
                        continue

                    # Fetch the satellite and lock it FOR UPDATE
                    sat_result = await db.execute(
                        select(Satellite)
                        .where(Satellite.id == sat_id)
                        .with_for_update()
                        .options(selectinload(Satellite.orbit_state))
                    )
                    sat = sat_result.scalar_one_or_none()
                    if not sat:
                        continue

                    # Update database
                    if not sat.orbit_state:
                        sat.orbit_state = OrbitState(satellite_id=sat.id, **state)
                        db.add(sat.orbit_state)
                    else:
                        for key, value in state.items():
                            setattr(sat.orbit_state, key, value)

                    await db.commit()

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

                except Exception as e:
                    logger.error(f"Error processing satellite {norad_id}: {e}")
                    await db.rollback()
                    # Skip to next satellite, don't crash batch
                    continue

            # Broadcast updates if there are any connections
            if updates_to_broadcast:
                await orbit_manager.broadcast_orbit_updates(updates_to_broadcast)

            logger.info(
                f"Finished orbit state update for {len(updates_to_broadcast)} satellites.")

        except Exception as e:
            logger.error(f"Critical error in scheduled orbit update: {e}")
            await db.rollback()


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
            logger.error(f"Critical error in scheduled screening: {e}")
            await db.rollback()


def init_scheduler():
    scheduler.add_job(update_orbit_states, 'interval', minutes=5,
                      id='update_orbit_states_job', replace_existing=True)
    scheduler.add_job(run_screening_job, 'interval', minutes=30,
                      id='run_screening_job', replace_existing=True)
    scheduler.start()


def shutdown_scheduler():
    scheduler.shutdown()
