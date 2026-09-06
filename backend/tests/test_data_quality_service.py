import math
from datetime import datetime, timedelta, timezone
import pytest

from app.services.data_quality_service import (
    DEFAULT_SCORING_PARAMETERS,
    DataQualityService,
)
from app.schemas.astrodynamics import OrbitDataQualityBundle


def test_source_normalization():
    # 1. CelesTrak variants
    code, name, is_auth, score = DataQualityService.normalize_source("celestrak")
    assert code == "CELESTRAK"
    assert is_auth is True
    assert score == 100

    code, name, is_auth, score = DataQualityService.normalize_source("CELESTRAK_ACTIVE")
    assert code == "CELESTRAK"
    assert is_auth is True

    # 2. Space-Track variants
    code, name, is_auth, score = DataQualityService.normalize_source("space-track.org")
    assert code == "SPACE_TRACK"
    assert is_auth is True
    assert score == 100

    code, name, is_auth, score = DataQualityService.normalize_source("18th_sds")
    assert code == "SPACE_TRACK"
    assert is_auth is True

    # 3. LeoLabs
    code, name, is_auth, score = DataQualityService.normalize_source("LEOLABS_RADAR")
    assert code == "LEOLABS"
    assert is_auth is True
    assert score == 95

    # 4. Manual / User Upload
    code, name, is_auth, score = DataQualityService.normalize_source("manual_upload")
    assert code == "USER_UPLOAD"
    assert is_auth is False
    assert score == 60

    code, name, is_auth, score = DataQualityService.normalize_source("paste")
    assert code == "USER_UPLOAD"
    assert is_auth is False

    # 5. Internal Propagations
    code, name, is_auth, score = DataQualityService.normalize_source("SATGUARD")
    assert code == "INTERNAL_SGP4"
    assert is_auth is False
    assert score == 80

    code, name, is_auth, score = DataQualityService.normalize_source("INTERNAL_OD")
    assert code == "INTERNAL_OD"
    assert is_auth is True
    assert score == 90

    # 6. Unknown fallback
    code, name, is_auth, score = DataQualityService.normalize_source("non_existent_feed_123")
    assert code == "UNKNOWN"
    assert is_auth is False
    assert score == 30

    code, name, is_auth, score = DataQualityService.normalize_source(None)
    assert code == "UNKNOWN"
    assert score == 30


def test_derive_orbit_regime():
    # 1. LEO
    assert DataQualityService.derive_orbit_regime(apogee_km=550.0, perigee_km=500.0, eccentricity=0.001) == "LEO"
    assert DataQualityService.derive_orbit_regime(altitude_km=400.0, eccentricity=0.0005) == "LEO"

    # 2. MEO (e.g. GPS altitude ~20,200 km)
    assert DataQualityService.derive_orbit_regime(apogee_km=20200.0, perigee_km=20200.0, eccentricity=0.001) == "MEO"

    # 3. GEO (~35,786 km circular)
    assert DataQualityService.derive_orbit_regime(apogee_km=35790.0, perigee_km=35780.0, eccentricity=0.0002) == "GEO"

    # 4. HEO (Molniya / high eccentricity)
    assert DataQualityService.derive_orbit_regime(apogee_km=39000.0, perigee_km=500.0, eccentricity=0.72) == "HEO"
    assert DataQualityService.derive_orbit_regime(apogee_km=1000.0, perigee_km=400.0, eccentricity=0.30) == "HEO"


def test_freshness_subscore_decay():
    params = DEFAULT_SCORING_PARAMETERS

    # 1. LEO Freshness Curve (<18h Fresh, 18-48h Aging, 48-96h Stale, >96h Critical)
    score_0h, tier_0h = DataQualityService.compute_freshness_subscore(0.0, "LEO", params)
    assert score_0h == 100.0
    assert tier_0h == "FRESH"

    score_9h, tier_9h = DataQualityService.compute_freshness_subscore(9.0, "LEO", params)
    assert score_9h == 90.0
    assert tier_9h == "FRESH"

    score_18h, tier_18h = DataQualityService.compute_freshness_subscore(18.0, "LEO", params)
    assert score_18h == 80.0
    assert tier_18h == "FRESH"

    score_33h, tier_33h = DataQualityService.compute_freshness_subscore(33.0, "LEO", params)
    assert tier_33h == "AGING"
    assert 55.0 < score_33h < 80.0

    score_48h, tier_48h = DataQualityService.compute_freshness_subscore(48.0, "LEO", params)
    assert score_48h == 55.0
    assert tier_48h == "AGING"

    score_72h, tier_72h = DataQualityService.compute_freshness_subscore(72.0, "LEO", params)
    assert tier_72h == "STALE"
    assert 35.0 < score_72h < 55.0

    score_96h, tier_96h = DataQualityService.compute_freshness_subscore(96.0, "LEO", params)
    assert score_96h == 35.0
    assert tier_96h == "STALE"

    score_150h, tier_150h = DataQualityService.compute_freshness_subscore(150.0, "LEO", params)
    assert tier_150h == "CRITICAL"
    assert score_150h < 35.0


def test_confidence_and_quality_bands_alignment():
    params = DEFAULT_SCORING_PARAMETERS

    # Test Case 1: Fresh LEO TLE (93.3 freshness, 100 source, 20 covariance)
    # Expected: 0.50*93.33 + 0.25*100 + 0.25*20 = 46.67 + 25.0 + 5.0 = 76.67 -> 76.7%
    conf1, qual1 = DataQualityService.compute_confidence_and_quality(
        freshness_score=93.33,
        source_score=100,
        covariance_score=20,
        eccentricity=0.001,
        params=params,
    )
    assert conf1 == 76.7
    assert qual1 == "HIGH"

    # Test Case 2: Aging LEO TLE (70.0 freshness, 100 source, 20 covariance)
    # Expected: 0.50*70 + 0.25*100 + 0.25*20 = 35.0 + 25.0 + 5.0 = 65.0%
    conf2, qual2 = DataQualityService.compute_confidence_and_quality(
        freshness_score=70.0,
        source_score=100,
        covariance_score=20,
        eccentricity=0.001,
        params=params,
    )
    assert conf2 == 65.0
    assert qual2 == "MEDIUM"

    # Test Case 3: Stale LEO TLE (48.8 freshness, 100 source, 20 covariance)
    # Expected: 0.50*48.8 + 30.0 = 24.4 + 30.0 = 54.4%
    conf3, qual3 = DataQualityService.compute_confidence_and_quality(
        freshness_score=48.8,
        source_score=100,
        covariance_score=20,
        eccentricity=0.001,
        params=params,
    )
    assert conf3 == 54.4
    assert qual3 == "LOW"

    # Test Case 4: Degraded Unverified Source (15.0 freshness, 30 source, 20 covariance)
    # Expected: 0.50*15.0 + 0.25*30 + 0.25*20 = 7.5 + 7.5 + 5.0 = 20.0%
    conf4, qual4 = DataQualityService.compute_confidence_and_quality(
        freshness_score=15.0,
        source_score=30,
        covariance_score=20,
        eccentricity=0.001,
        params=params,
    )
    assert conf4 == 20.0
    assert qual4 == "UNRELIABLE"

    # Test monotonic band compliance across 0..100
    for score in range(0, 101):
        c, q = DataQualityService.compute_confidence_and_quality(
            freshness_score=float(score),
            source_score=score,
            covariance_score=score,
            eccentricity=0.0,
            params=params,
        )
        if c >= 75.0:
            assert q == "HIGH"
        elif c >= 60.0:
            assert q == "MEDIUM"
        elif c >= 35.0:
            assert q == "LOW"
        else:
            assert q == "UNRELIABLE"
