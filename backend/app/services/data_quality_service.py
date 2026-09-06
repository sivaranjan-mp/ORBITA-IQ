import logging
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.astrodynamics import AlgorithmVersion
from app.models.catalog import CatalogSatellite
from app.models.satellites import Satellite
from app.schemas.astrodynamics import OrbitDataQualityBundle

logger = logging.getLogger(__name__)

MU_EARTH = 398600.4418  # km^3/s^2
R_EARTH = 6378.137  # km

ALGORITHM_NAME = "DATA_QUALITY_SCORING"
ALGORITHM_VERSION = "1.0.0"

DEFAULT_SCORING_PARAMETERS: Dict[str, Any] = {
    "weights": {
        "freshness": 0.50,
        "source": 0.25,
        "covariance": 0.25,
    },
    "regime_thresholds_hours": {
        "LEO": {"fresh": 18.0, "aging": 48.0, "stale": 96.0},
        "HEO": {"fresh": 24.0, "aging": 72.0, "stale": 144.0},
        "MEO": {"fresh": 36.0, "aging": 96.0, "stale": 168.0},
        "GEO": {"fresh": 48.0, "aging": 120.0, "stale": 240.0},
        "OTHER": {"fresh": 24.0, "aging": 48.0, "stale": 96.0},
    },
    "source_scores": {
        "SPACE_TRACK": 100,
        "CELESTRAK": 100,
        "LEOLABS": 95,
        "INTERNAL_OD": 90,
        "OPERATOR_EPHEMERIS": 90,
        "INTERNAL_SGP4": 80,
        "USER_UPLOAD": 60,
        "UNKNOWN": 30,
    },
    "covariance_scores": {
        "FULL_6X6": 100,
        "POSITION_DIAGONAL": 60,
        "NONE": 20,
    },
    "quality_bands": {
        "HIGH": 75.0,
        "MEDIUM": 60.0,
        "LOW": 35.0,
    },
}

# Raw string mapping table to canonical source codes, display names, and trust
SOURCE_NORMALIZATION_MAP: Dict[str, Tuple[str, str, bool, int]] = {
    "CELESTRAK": ("CELESTRAK", "CelesTrak (GP)", True, 100),
    "CELESTRAK_ACTIVE": ("CELESTRAK", "CelesTrak (GP)", True, 100),
    "SPACE_TRACK": ("SPACE_TRACK", "Space-Track.org (18th SDS)", True, 100),
    "SPACETRACK": ("SPACE_TRACK", "Space-Track.org (18th SDS)", True, 100),
    "18TH_SDS": ("SPACE_TRACK", "Space-Track.org (18th SDS)", True, 100),
    "18_SDS": ("SPACE_TRACK", "Space-Track.org (18th SDS)", True, 100),
    "LEOLABS": ("LEOLABS", "LeoLabs Radar Network", True, 95),
    "LEOLABS_RADAR": ("LEOLABS", "LeoLabs Radar Network", True, 95),
    "INTERNAL_OD": ("INTERNAL_OD", "Orbita-IQ Numerical OD", True, 90),
    "NUMERICAL_OD": ("INTERNAL_OD", "Orbita-IQ Numerical OD", True, 90),
    "OPERATOR_EPHEMERIS": ("OPERATOR_EPHEMERIS", "Operator Ephemeris (OEM)", True, 90),
    "OEM": ("OPERATOR_EPHEMERIS", "Operator Ephemeris (OEM)", True, 90),
    "INTERNAL_SGP4": ("INTERNAL_SGP4", "Orbita-IQ SatGuard SGP4", False, 80),
    "SATGUARD": ("INTERNAL_SGP4", "Orbita-IQ SatGuard SGP4", False, 80),
    "MANUAL_UPLOAD": ("USER_UPLOAD", "Manual Operator Upload", False, 60),
    "USER_UPLOAD": ("USER_UPLOAD", "Manual Operator Upload", False, 60),
    "MANUAL": ("USER_UPLOAD", "Manual Operator Upload", False, 60),
    "PASTE": ("USER_UPLOAD", "Manual Operator Upload", False, 60),
    "UPLOAD": ("USER_UPLOAD", "Manual Operator Upload", False, 60),
}


class DataQualityService:
    @staticmethod
    def normalize_source(raw_source: Optional[str]) -> Tuple[str, str, bool, int]:
        """
        Normalizes any arbitrary source string to a canonical tuple:
        (canonical_code, display_name, is_authoritative, score)
        """
        if not raw_source or not str(raw_source).strip():
            return ("UNKNOWN", "Unknown Source", False, 30)

        clean = re.sub(r"[^A-Za-z0-9]+", "_", str(raw_source).strip()).strip("_").upper()

        if clean in SOURCE_NORMALIZATION_MAP:
            return SOURCE_NORMALIZATION_MAP[clean]

        # Check partial prefix / substring matches
        if "CELESTRAK" in clean or clean == "GP":
            return ("CELESTRAK", "CelesTrak (GP)", True, 100)
        if "SPACE_TRACK" in clean or "SPACETRACK" in clean or "18TH" in clean:
            return ("SPACE_TRACK", "Space-Track.org (18th SDS)", True, 100)
        if "LEOLABS" in clean:
            return ("LEOLABS", "LeoLabs Radar Network", True, 95)
        if "MANUAL" in clean or "UPLOAD" in clean or "PASTE" in clean:
            return ("USER_UPLOAD", "Manual Operator Upload", False, 60)
        if "INTERNAL" in clean or "SATGUARD" in clean:
            return ("INTERNAL_SGP4", "Orbita-IQ SatGuard SGP4", False, 80)

        # Fallback for unrecognized custom sources
        logger.debug(f"Unrecognized data source code '{raw_source}'. Classifying as UNKNOWN.")
        return ("UNKNOWN", f"Unverified Source ({raw_source})", False, 30)

    @staticmethod
    def derive_orbit_regime(
        apogee_km: Optional[float] = None,
        perigee_km: Optional[float] = None,
        eccentricity: Optional[float] = None,
        altitude_km: Optional[float] = None,
        line1: Optional[str] = None,
        line2: Optional[str] = None,
    ) -> str:
        """
        Derives orbit regime (LEO, MEO, GEO, HEO, OTHER) deterministically from
        available orbital elements or TLE lines.
        """
        e = eccentricity if eccentricity is not None else 0.001
        ap = apogee_km
        per = perigee_km

        # If TLE lines provided and apogee/perigee missing, compute via mean motion
        if (ap is None or per is None) and line1 and line2:
            try:
                from sgp4.api import Satrec
                sat = Satrec.twoline2rv(line1, line2)
                e = sat.ecco
                n_rad_min = sat.no_kozai
                if n_rad_min > 0:
                    n_rad_s = n_rad_min / 60.0
                    a = (MU_EARTH / (n_rad_s ** 2)) ** (1.0 / 3.0)
                    ap = a * (1.0 + e) - R_EARTH
                    per = a * (1.0 - e) - R_EARTH
            except Exception:
                pass

        # If still missing, estimate from altitude_km
        if ap is None or per is None:
            alt = altitude_km if altitude_km is not None else 500.0
            r_mean = R_EARTH + alt
            ap = r_mean * (1.0 + e) - R_EARTH
            per = r_mean * (1.0 - e) - R_EARTH

        # Boundary checks
        if e >= 0.25 or (ap > 35500.0 and per < 35500.0):
            return "HEO"
        if per <= 2000.0:
            return "LEO"
        if 35500.0 <= per <= 36500.0 and 35500.0 <= ap <= 36500.0 and e < 0.10:
            return "GEO"
        if per > 2000.0 and ap < 35500.0:
            return "MEO"
        return "OTHER"

    @classmethod
    def compute_freshness_subscore(
        cls, age_hours: float, regime: str, params: Dict[str, Any]
    ) -> Tuple[float, str]:
        """
        Computes the freshness sub-score (0-100) and freshness tier (FRESH, AGING, STALE, CRITICAL)
        using the regime-specific threshold parameters.
        """
        thresholds_map = params.get("regime_thresholds_hours", DEFAULT_SCORING_PARAMETERS["regime_thresholds_hours"])
        regime_key = regime if regime in thresholds_map else "OTHER"
        t_cfg = thresholds_map[regime_key]

        t_fresh = float(t_cfg["fresh"])
        t_aging = float(t_cfg["aging"])
        t_stale = float(t_cfg["stale"])

        age = max(0.0, float(age_hours))

        if age <= t_fresh:
            # Score linearly decays from 100.0 down to 80.0
            score = 100.0 - 20.0 * (age / max(0.1, t_fresh))
            tier = "FRESH"
        elif age <= t_aging:
            # Score decays from 80.0 down to 55.0
            fraction = (age - t_fresh) / max(0.1, (t_aging - t_fresh))
            score = 80.0 - 25.0 * fraction
            tier = "AGING"
        elif age <= t_stale:
            # Score decays from 55.0 down to 35.0
            fraction = (age - t_aging) / max(0.1, (t_stale - t_aging))
            score = 55.0 - 20.0 * fraction
            tier = "STALE"
        else:
            # Exponential decay beyond stale threshold down to minimum 5.0
            excess = age - t_stale
            score = max(5.0, 35.0 * math.exp(-excess / max(1.0, t_stale)))
            tier = "CRITICAL"

        return round(score, 2), tier

    @classmethod
    def compute_confidence_and_quality(
        cls,
        freshness_score: float,
        source_score: int,
        covariance_score: int,
        eccentricity: Optional[float],
        params: Dict[str, Any],
    ) -> Tuple[float, str]:
        """
        Calculates unified numeric confidence score (0-100) and assigns the categorical
        quality label using clean, non-overlapping threshold bands.
        """
        weights = params.get("weights", DEFAULT_SCORING_PARAMETERS["weights"])
        w_fresh = float(weights.get("freshness", 0.50))
        w_source = float(weights.get("source", 0.25))
        w_cov = float(weights.get("covariance", 0.25))

        # Eccentricity penalty for extreme orbits where analytical SGP4 error is magnified
        ecc_penalty = 10.0 if (eccentricity is not None and eccentricity > 0.60) else 0.0

        raw_score = (
            (w_fresh * freshness_score)
            + (w_source * float(source_score))
            + (w_cov * float(covariance_score))
            - ecc_penalty
        )
        clamped_score = max(5.0, min(100.0, raw_score))
        confidence = round(clamped_score, 1)

        bands = params.get("quality_bands", DEFAULT_SCORING_PARAMETERS["quality_bands"])
        high_thresh = float(bands.get("HIGH", 75.0))
        med_thresh = float(bands.get("MEDIUM", 60.0))
        low_thresh = float(bands.get("LOW", 35.0))

        if confidence >= high_thresh:
            quality = "HIGH"
        elif confidence >= med_thresh:
            quality = "MEDIUM"
        elif confidence >= low_thresh:
            quality = "LOW"
        else:
            quality = "UNRELIABLE"

        return confidence, quality

    @classmethod
    async def get_active_parameters(cls, db: AsyncSession) -> Tuple[str, Dict[str, Any]]:
        """
        Retrieves active scoring parameters from algorithm_versions table or registers
        the baseline version if absent.
        """
        try:
            stmt = (
                select(AlgorithmVersion)
                .where(AlgorithmVersion.name == ALGORITHM_NAME)
                .where(AlgorithmVersion.is_active.is_(True))
                .order_by(AlgorithmVersion.created_at.desc())
            )
            res = await db.execute(stmt)
            alg = res.scalars().first()
            if alg and alg.parameters:
                return alg.version, alg.parameters
        except Exception as exc:
            logger.debug(f"Could not read algorithm_versions for {ALGORITHM_NAME}: {exc}")

        return ALGORITHM_VERSION, DEFAULT_SCORING_PARAMETERS

    @classmethod
    async def evaluate_orbit_quality(
        cls,
        db: AsyncSession,
        norad_id: int,
        satellite_id: Optional[uuid.UUID] = None,
        explicit_now: Optional[datetime] = None,
    ) -> OrbitDataQualityBundle:
        """
        Primary evaluation entry point: queries database state for the given satellite or
        catalog object, computes real-time age, subscores, and produces the complete
        8-field OrbitDataQualityBundle.
        """
        now = explicit_now or datetime.now(timezone.utc)
        alg_version, params = await cls.get_active_parameters(db)

        raw_source: Optional[str] = None
        epoch: Optional[datetime] = None
        ingestion_time: Optional[datetime] = None
        orbit_regime: Optional[str] = None
        eccentricity: Optional[float] = None
        apogee_km: Optional[float] = None
        perigee_km: Optional[float] = None
        altitude_km: Optional[float] = None
        line1: Optional[str] = None
        line2: Optional[str] = None

        # 1. Attempt lookup as Fleet Satellite
        primary_sat: Optional[Satellite] = None
        if satellite_id:
            sat_stmt = (
                select(Satellite)
                .where(Satellite.id == satellite_id)
                .options(selectinload(Satellite.tle_records), selectinload(Satellite.orbit_state))
            )
            sat_res = await db.execute(sat_stmt)
            primary_sat = sat_res.scalars().first()

        if not primary_sat and norad_id:
            sat_stmt = (
                select(Satellite)
                .where(Satellite.norad_id == norad_id)
                .options(selectinload(Satellite.tle_records), selectinload(Satellite.orbit_state))
            )
            sat_res = await db.execute(sat_stmt)
            primary_sat = sat_res.scalars().first()

        if primary_sat:
            if primary_sat.tle_records:
                latest_tle = max(primary_sat.tle_records, key=lambda t: t.epoch or t.created_at)
                raw_source = latest_tle.source or "celestrak"
                epoch = latest_tle.epoch
                ingestion_time = latest_tle.created_at
                line1 = latest_tle.line1
                line2 = latest_tle.line2

            if primary_sat.orbit_state:
                eccentricity = primary_sat.orbit_state.eccentricity
                altitude_km = primary_sat.orbit_state.altitude_km
                if not epoch:
                    epoch = primary_sat.orbit_state.epoch
                if not ingestion_time:
                    ingestion_time = primary_sat.orbit_state.created_at

        # 2. Attempt lookup in Catalog Satellite if epoch or source still missing
        if not epoch or not line1:
            cat_stmt = select(CatalogSatellite).where(CatalogSatellite.norad_id == norad_id)
            cat_res = await db.execute(cat_stmt)
            cat_sat = cat_res.scalars().first()
            if cat_sat:
                raw_source = raw_source or "CELESTRAK"
                epoch = epoch or cat_sat.epoch
                ingestion_time = ingestion_time or (cat_sat.updated_at or cat_sat.created_at)
                orbit_regime = cat_sat.orbit_regime
                apogee_km = cat_sat.apogee_km
                perigee_km = cat_sat.perigee_km
                eccentricity = eccentricity if eccentricity is not None else cat_sat.eccentricity
                line1 = line1 or cat_sat.line1
                line2 = line2 or cat_sat.line2

        # 3. Fallbacks if record is completely new or untracked
        if not epoch:
            epoch = now
        if not ingestion_time:
            ingestion_time = now

        # Ensure UTC timezone awareness
        if epoch.tzinfo is None:
            epoch = epoch.replace(tzinfo=timezone.utc)
        if ingestion_time.tzinfo is None:
            ingestion_time = ingestion_time.replace(tzinfo=timezone.utc)

        # Compute age in hours
        age_hours = max(0.0, (now - epoch).total_seconds() / 3600.0)

        # Derive regime if not already explicitly set
        if not orbit_regime or orbit_regime.upper() == "UNKNOWN":
            orbit_regime = cls.derive_orbit_regime(
                apogee_km=apogee_km,
                perigee_km=perigee_km,
                eccentricity=eccentricity,
                altitude_km=altitude_km,
                line1=line1,
                line2=line2,
            )

        # Normalize source string
        source_code, source_display, is_authoritative, source_score = cls.normalize_source(raw_source)

        # Check covariance availability in database (currently unpopulated/false in live flow)
        has_covariance = False
        cov_score_val = params.get("covariance_scores", DEFAULT_SCORING_PARAMETERS["covariance_scores"])
        covariance_score = int(cov_score_val.get("FULL_6X6", 100)) if has_covariance else int(cov_score_val.get("NONE", 20))
        cov_status_text = (
            "Available (6x6 Full Covariance)"
            if has_covariance
            else "Not Available (Analytical TLE / SGP4)"
        )

        # Calculate freshness sub-score and tier
        freshness_score, freshness_tier = cls.compute_freshness_subscore(
            age_hours=age_hours, regime=orbit_regime, params=params
        )

        # Calculate confidence score and quality category
        confidence_score, data_quality = cls.compute_confidence_and_quality(
            freshness_score=freshness_score,
            source_score=source_score,
            covariance_score=covariance_score,
            eccentricity=eccentricity,
            params=params,
        )

        return OrbitDataQualityBundle(
            source=source_display,
            source_code=source_code,
            is_authoritative=is_authoritative,
            epoch=epoch,
            ingestion_time=ingestion_time,
            age_hours=round(age_hours, 1),
            freshness_tier=freshness_tier,
            propagation_model="SGP4 (WGS84 General Perturbations)",
            orbit_regime=orbit_regime,
            data_quality=data_quality,
            covariance_available=has_covariance,
            covariance_status=cov_status_text,
            confidence_score=confidence_score,
            scoring_algorithm_version=alg_version,
        )
