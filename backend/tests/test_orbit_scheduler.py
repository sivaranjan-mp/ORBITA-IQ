import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.orbit_scheduler import update_orbit_states
from app.models.satellites import Satellite


@pytest.mark.asyncio
async def test_scheduler_survives_malformed_tle():
    sat1 = Satellite(id="uuid-1", norad_id=11111,
                     status="active", orbit_state=None, tle_records=[])
    sat2 = Satellite(id="uuid-2", norad_id=22222,
                     status="active", orbit_state=None, tle_records=[])

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    
    def mock_execute(*args, **kwargs):
        mock_res = MagicMock()
        query_str = str(args[0])
        mock_scalars = MagicMock()
        if "FOR UPDATE" not in query_str:
            mock_scalars.all.return_value = [sat1, sat2]
        else:
            mock_scalars.all.return_value = [sat2]
        mock_res.scalars.return_value = mock_scalars
        return mock_res
        
    mock_db.execute.side_effect = mock_execute

    with patch("app.services.orbit_scheduler.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__.return_value = mock_db

        with patch("app.services.orbit_scheduler.fetch_tle_by_norad_id", new_callable=AsyncMock) as mock_fetch:
            async def side_effect(norad_id):
                if norad_id == 11111:
                    return "MALFORMED DATA"
                return "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9992\n2 25544  51.6402 180.0000 0001000   0.0000   0.0000 15.50000000000000"

            mock_fetch.side_effect = side_effect

            with patch("app.services.orbit_scheduler.propagate_tle") as mock_propagate:
                mock_propagate.return_value = {
                    "altitude_km": 400.0,
                    "latitude_deg": 12.34,
                    "longitude_deg": 56.78,
                    "velocity_km_s": 7.66,
                    "inclination_deg": 51.6,
                    "eccentricity": 0.0001,
                    "raan_deg": 0.0,
                    "mean_anomaly_deg": 0.0,
                    "period_minutes": 92.0,
                    "epoch": datetime(2024, 1, 1, tzinfo=timezone.utc),
                    "x_km": 6778.0,
                    "y_km": 0.0,
                    "z_km": 0.0,
                    "vx_kms": 0.0,
                    "vy_kms": 7.6,
                    "vz_kms": 0.0
                }
                
                with patch("app.services.orbit_scheduler.orbit_manager.broadcast_orbit_updates", new_callable=AsyncMock) as mock_broadcast:
                    with patch("app.services.orbit_scheduler.asyncio.sleep", new_callable=AsyncMock):  
                        await update_orbit_states()

                        mock_db.commit.assert_called_once()
                        mock_broadcast.assert_called_once()
                        broadcast_args = mock_broadcast.call_args[0][0]
                        assert len(broadcast_args) == 1
                        assert broadcast_args[0]["noradId"] == 22222
                        assert broadcast_args[0]["latitudeDeg"] == 12.34
                        assert broadcast_args[0]["longitudeDeg"] == 56.78
                        assert broadcast_args[0]["velocityKmS"] == 7.66


@pytest.mark.asyncio
async def test_scheduler_propagates_critical_exception():
    mock_db = AsyncMock()
    mock_db.execute.side_effect = Exception("DB connection timeout")

    with patch("app.services.orbit_scheduler.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__.return_value = mock_db

        with pytest.raises(Exception, match="DB connection timeout"):
            await update_orbit_states()
        mock_db.rollback.assert_called_once()
