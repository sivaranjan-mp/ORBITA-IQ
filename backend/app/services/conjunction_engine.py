from typing import Dict, List, Optional

from app.core.constants import (
    CRITICAL_MISS_DISTANCE_KM,
    CRITICAL_PROBABILITY,
    HIGH_MISS_DISTANCE_KM,
    HIGH_PROBABILITY,
    LOW_MISS_DISTANCE_KM,
    MAX_SCREEN_MISS_DISTANCE_KM,
    MEDIUM_MISS_DISTANCE_KM,
    MEDIUM_PROBABILITY,
    STAGE1_ALTITUDE_MARGIN_KM,
)


class ConjunctionEngine:
    """
    Evaluates conjunction risks, applies Stage 1 coarse orbital filtering,
    classifies risk thresholds, and deduplicates alerts.
    """

    CRITICAL_PROBABILITY = CRITICAL_PROBABILITY
    HIGH_PROBABILITY = HIGH_PROBABILITY
    MEDIUM_PROBABILITY = MEDIUM_PROBABILITY

    @classmethod
    def passes_stage1_coarse_filter(
        cls,
        perigee_a: float,
        apogee_a: float,
        perigee_b: float,
        apogee_b: float,
        margin_km: float = STAGE1_ALTITUDE_MARGIN_KM,
    ) -> bool:
        """
        Stage 1 — Coarse orbital altitude filter.
        Compares perigee/apogee ranges. If [perigee_a, apogee_a] and [perigee_b, apogee_b]
        do not overlap with margin_km buffer (default 50 km), the two orbits cannot
        intersect and are discarded without SGP4 propagation.
        """
        if perigee_a > apogee_b + margin_km or perigee_b > apogee_a + margin_km:
            return False
        return True

    @classmethod
    def classify_risk_by_miss_distance(cls, miss_distance_km: float) -> Optional[str]:
        """
        Standardized Miss-Distance Risk Classification Table:
        | Miss distance | Risk      |
        | < 1 km        | Critical  |
        | 1–5 km        | High      |
        | 5–25 km       | Medium    |
        | 25–50 km      | Low       |
        | > 50 km       | None / Discarded |
        """
        if miss_distance_km < CRITICAL_MISS_DISTANCE_KM:
            return "critical"
        elif miss_distance_km <= HIGH_MISS_DISTANCE_KM:
            return "high"
        elif miss_distance_km <= MEDIUM_MISS_DISTANCE_KM:
            return "medium"
        elif miss_distance_km <= LOW_MISS_DISTANCE_KM:
            return "low"
        return None

    @classmethod
    def classify_risk(cls, probability: float, miss_distance_m: float) -> str:
        """
        Calculates the overall risk level combining miss distance and collision probability.
        Guarantees strict adherence to distance thresholds while accounting for high probability events.
        """
        miss_dist_km = miss_distance_m / 1000.0

        if miss_dist_km < CRITICAL_MISS_DISTANCE_KM or probability >= cls.CRITICAL_PROBABILITY:
            return "critical"
        elif miss_dist_km <= HIGH_MISS_DISTANCE_KM or probability >= cls.HIGH_PROBABILITY:
            return "high"
        elif miss_dist_km <= MEDIUM_MISS_DISTANCE_KM or probability >= cls.MEDIUM_PROBABILITY:
            return "medium"
        elif miss_dist_km <= LOW_MISS_DISTANCE_KM:
            return "low"
        return "low"

    @classmethod
    def deduplicate_alerts(cls, new_alerts: List[Dict], existing_alerts: List[Dict]) -> List[Dict]:
        """
        Removes duplicate alerts based on same primary/secondary object pairs within a 1-hour TCA window.
        """
        unique_new_alerts = []

        for new_alert in new_alerts:
            is_duplicate = False
            for existing in existing_alerts:
                same_pair = (
                    (new_alert["primary_norad_id"] == existing["primary_norad_id"] and
                     new_alert["secondary_norad_id"] == existing["secondary_norad_id"]) or
                    (new_alert["primary_norad_id"] == existing["secondary_norad_id"] and
                     new_alert["secondary_norad_id"] == existing["primary_norad_id"])
                )

                if same_pair:
                    time_diff = abs((new_alert["tca"] - existing["tca"]).total_seconds())
                    if time_diff < 3600:
                        is_duplicate = True
                        break

            if not is_duplicate:
                unique_new_alerts.append(new_alert)
                existing_alerts.append(new_alert)

        return unique_new_alerts
