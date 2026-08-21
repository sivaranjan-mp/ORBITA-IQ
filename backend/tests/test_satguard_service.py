import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.satellites import Satellite, TLERecord
from app.services.satguard_service import SatguardService


@pytest.mark.asyncio
async def test_satguard_coarse_filter_no_overlap():
    """
    Test that the coarse filter correctly ignores satellites in completely different orbital bands.
    """
    db = AsyncMock()
    service = SatguardService(db)

    # Sat 1: LEO (~400km)
    # ISS
    tle1_1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9992"
    tle1_2 = "2 25544  51.6402 180.0000 0001000   0.0000   0.0000 15.50000000000000"

    # Sat 2: GEO (~35786km)
    # Generic GEO TLE
    tle2_1 = "1 25867U 99046A   24001.50000000  .00000000  00000-0  00000-0 0  9991"
    tle2_2 = "2 25867   0.0000   0.0000 0001000   0.0000   0.0000  1.00270000000000"

    a1, p1 = service._compute_apogee_perigee(tle1_1, tle1_2)
    a2, p2 = service._compute_apogee_perigee(tle2_1, tle2_2)

    assert a1 < 1000
    assert p2 > 30000
    assert p2 > a1 + 10  # Cannot intersect


@pytest.mark.asyncio
@patch("sgp4.api.Satrec")
async def test_satguard_synthetic_screening(mock_satrec):
    db = AsyncMock()
    db.add = MagicMock()  # SQLAlchemy add is synchronous, override AsyncMock
    service = SatguardService(db)

    # Create two satellites that are mocked to be very close at step 10
    sat1 = Satellite(id="s1", status="active")
    tle1 = TLERecord(line1="1", line2="2", epoch=datetime.now(timezone.utc))
    sat1.tle_records = [tle1]

    sat2 = Satellite(id="s2", status="active")
    tle2 = TLERecord(line1="1", line2="2", epoch=datetime.now(timezone.utc))
    sat2.tle_records = [tle2]

    mock_db_result = MagicMock()
    mock_db_result.scalars().all.return_value = [sat1, sat2]
    db.execute.return_value = mock_db_result

    # Mock compute_apogee_perigee to allow them to overlap
    with patch.object(service, '_compute_apogee_perigee', return_value=(500, 400)):

        # Mock distance func to artificially dip to 2km at t=600s
        def mock_distance(s1, s2, dt):
            # Let's say dt ranges around 'now'.
            # At exactly t=600s, distance is 2.0 km.
            diff = (
                dt - datetime.now(timezone.utc).replace(microsecond=0)).total_seconds()
            dist = 500.0 if abs(diff - 600) > 60 else 2.0 + abs(diff - 600)
            # dist, r1, v1, r2, v2, rel_vel
            return dist, [0, 0, 0], [0, 0, 0], [2, 0, 0], [1, 0, 0], 1.0

        with patch.object(service, '_distance_at_time', side_effect=mock_distance):
            events = await service.screen_all(lookahead_hours=1, step_size_s=60, miss_dist_threshold_km=5.0)

            assert events == 1
            db.add.assert_called()

            # Extract the saved ConjunctionEvent (it's the first add call)
            event_args = db.add.call_args_list[0][0][0]
            assert event_args.miss_distance_m == pytest.approx(
                2000.0, rel=1e-3)  # 2km in meters
            assert event_args.primary_satellite_id == "s1"
