from typing import List, Dict


class ConjunctionEngine:
    """
    Evaluates conjunction risks, applies thresholds, and deduplicates alerts.
    """

    # Thresholds
    CRITICAL_PROBABILITY = 1e-4  # 1 in 10,000
    HIGH_PROBABILITY = 1e-5      # 1 in 100,000
    MEDIUM_PROBABILITY = 1e-6    # 1 in 1,000,000

    @classmethod
    def classify_risk(cls, probability: float, miss_distance_m: float) -> str:
        """
        Calculates the risk level based on collision probability and miss distance.
        Fixed logic to handle edge cases like very small miss distances with lower probabilities.
        """
        if probability >= cls.CRITICAL_PROBABILITY or (probability >= cls.HIGH_PROBABILITY and miss_distance_m < 500):
            return "critical"
        elif probability >= cls.HIGH_PROBABILITY or (probability >= cls.MEDIUM_PROBABILITY and miss_distance_m < 1000):
            return "high"
        elif probability >= cls.MEDIUM_PROBABILITY:
            return "medium"
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
                # Check if it's the same pair of objects
                same_pair = (
                    (new_alert["primary_norad_id"] == existing["primary_norad_id"] and
                     new_alert["secondary_norad_id"] == existing["secondary_norad_id"]) or
                    (new_alert["primary_norad_id"] == existing["secondary_norad_id"] and
                     new_alert["secondary_norad_id"] == existing["primary_norad_id"])
                )

                if same_pair:
                    # Check if TCA is within 1 hour
                    time_diff = abs(
                        (new_alert["tca"] - existing["tca"]).total_seconds())
                    if time_diff < 3600:
                        is_duplicate = True
                        break

            if not is_duplicate:
                unique_new_alerts.append(new_alert)
                # Add to existing list for subsequent checks in the same batch
                existing_alerts.append(new_alert)

        return unique_new_alerts
