import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.orbit_scheduler import update_orbit_states
from app.models.satellites import Satellite


@pytest.mark.asyncio
async def test_scheduler_survives_malformed_tle():
    sat1 = Satellite(id="uuid-1", norad_id=11111,
                     status="active", orbit_state=None)
    sat2 = Satellite(id="uuid-2", norad_id=22222,
                     status="active", orbit_state=None)

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_result = MagicMock()
    async def mock_scalar_one_or_none():
        # returns whatever is next, but if we continue, we need to make sure we don't return sat1 for sat2
        pass
    
    # Actually, a better way to mock this is to check the arguments or just provide a dict
    def mock_execute(*args, **kwargs):
        mock_res = MagicMock()
        # if this is the initial fetch:
        if "Satellite.status == 'active'" in str(args[0]):
            mock_res.all.return_value = [(sat1.id, sat1.norad_id), (sat2.id, sat2.norad_id)]
        else:
            # this is the single fetch
            if str(sat1.id) in str(args[0]):
                mock_res.scalar_one_or_none.return_value = sat1
            else:
                mock_res.scalar_one_or_none.return_value = sat2
        return mock_res
        
    mock_db.execute.side_effect = mock_execute

    with patch("app.services.orbit_scheduler.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__.return_value = mock_db

        with patch("app.services.orbit_scheduler.fetch_tle_by_norad_id", new_callable=AsyncMock) as mock_fetch:
            # Sat 1 gets malformed TLE
            # Sat 2 gets valid TLE
            async def side_effect(norad_id):
                if norad_id == 11111:
                    return "MALFORMED DATA"
                return "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9992\n2 25544  51.6402 180.0000 0001000   0.0000   0.0000 15.50000000000000"

            mock_fetch.side_effect = side_effect

            with patch("app.services.orbit_scheduler.orbit_manager.broadcast_orbit_updates", new_callable=AsyncMock) as mock_broadcast:
                with patch("app.services.orbit_scheduler.asyncio.sleep", new_callable=AsyncMock):  # Skip sleeps
                    await update_orbit_states()

                    # db.commit() should be called despite the first satellite failing
                    mock_db.commit.assert_called_once()

                    # broadcast should be called with only the successful satellite
                    mock_broadcast.assert_called_once()
                    broadcast_args = mock_broadcast.call_args[0][0]
                    assert len(broadcast_args) == 1
                    assert broadcast_args[0]["noradId"] == 22222
