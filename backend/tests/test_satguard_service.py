import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.satellites import Satellite, TLERecord
from app.models.alerts import ConjunctionAlert
from app.services.satguard_service import SatguardService


@pytest.mark.asyncio
async def test_satguard_compute_apogee_perigee():
    """
    Test that SatguardService computes accurate apogee and perigee from TLEs.
    """
    # ISS TLE (~418km circular LEO)
    tle1 = "1 25544U 98067A   24080.52843444  .00015525  00000-0  27827-3 0  9993"
    tle2 = "2 25544  51.6416 261.2435 0005436 127.3562 334.8519 15.49887756444585"

    apogee, perigee = SatguardService.compute_apogee_perigee(tle1, tle2)
    assert 400.0 < apogee < 440.0
    assert 400.0 < perigee < 440.0
    assert perigee <= apogee


@pytest.mark.asyncio
async def test_satguard_coarse_filter_no_overlap():
    """
    Test that the coarse filter correctly ignores satellites in completely different orbital bands.
    """
    db = AsyncMock()
    service = SatguardService(db)

    # Sat 1: LEO (~400km)
    tle1_1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  30000-3 0  9992"
    tle1_2 = "2 25544  51.6402 180.0000 0001000   0.0000   0.0000 15.50000000000000"

    # Sat 2: GEO (~35786km)
    tle2_1 = "1 25867U 99046A   24001.50000000  .00000000  00000-0  00000-0 0  9991"
    tle2_2 = "2 25867   0.0000   0.0000 0001000   0.0000   0.0000  1.00270000000000"

    a1, p1 = SatguardService.compute_apogee_perigee(tle1_1, tle1_2)
    a2, p2 = SatguardService.compute_apogee_perigee(tle2_1, tle2_2)

    assert a1 < 1000
    assert p2 > 30000
    assert p2 > a1 + 50.0  # Cannot intersect


@pytest.mark.asyncio
async def test_satguard_synthetic_screening():
    db = AsyncMock()
    db.add = MagicMock()
    service = SatguardService(db)

    # ISS and synthetic companion with valid full TLE lines
    tle1_1 = "1 25544U 98067A   26245.50000000  .00004070  00000+0  82080-4 0  9996"
    tle1_2 = "2 25544  51.6313 277.6073 0005029  99.7358 260.4199 15.48970443583732"
    sat1 = Satellite(id="s1", norad_id=25544, name="ISS (ZARYA)", status="active")
    sat1.tle_records = [TLERecord(line1=tle1_1, line2=tle1_2, epoch=datetime.now(timezone.utc))]

    tle2_1 = "1 99001U 26001A   26245.50000000  .00004070  00000+0  82080-4 0  9999"
    tle2_2 = "2 99001  51.6313 277.6085 0005029  99.7358 260.4208 15.48970443583732"
    sat2 = Satellite(id="s2", norad_id=99001, name="SYNTHETIC-DEB-ALPHA", status="active")
    sat2.tle_records = [TLERecord(line1=tle2_1, line2=tle2_2, epoch=datetime.now(timezone.utc))]

    def mock_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt).lower()
        mock_res = MagicMock()
        mock_scalars = MagicMock()

        if "from satellites" in stmt_str:
            mock_scalars.all.return_value = [sat1, sat2]
        elif "from catalog_satellites" in stmt_str:
            mock_scalars.all.return_value = []
        elif "from conjunction_alerts" in stmt_str:
            mock_scalars.first.return_value = None
            mock_scalars.all.return_value = []
        else:
            mock_scalars.all.return_value = []
            mock_scalars.first.return_value = None

        mock_res.scalars.return_value = mock_scalars
        return mock_res

    db.execute.side_effect = mock_execute

    metrics = await service.screen_all(lookahead_hours=120.0, step_size_s=60, miss_dist_threshold_km=50.0)

    assert metrics["events_created"] == 1
    assert db.add.called

    added_items = [call[0][0] for call in db.add.call_args_list]
    alert_item = next(item for item in added_items if isinstance(item, ConjunctionAlert))
    assert alert_item.risk_level == "critical"
    assert alert_item.miss_distance_km < 1.0
    assert alert_item.satellite_a_norad_id == 25544
