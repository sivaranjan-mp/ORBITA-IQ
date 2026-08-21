class RiskExplanationEngine:
    """
    Deterministically generates human-readable risk explanations.
    """

    @staticmethod
    def generate_explanation(primary_name: str, secondary_name: str, risk_level: str,
                             miss_distance_km: float, relative_velocity_kms: float,
                             probability: float, trend: str) -> str:
        """
        Generates a standard risk explanation template.
        """

        # Format the probability to scientific notation and "1 in N"
        if probability > 0:
            one_in_n = int(1.0 / probability)
            prob_str = f"{probability:.2e} (1 in {one_in_n:,})"
        else:
            prob_str = "0.0 (negligible)"

        risk_caps = risk_level.upper()

        # Contributing factors text
        if miss_distance_km < 1.0:
            dist_desc = "an extremely close"
        elif miss_distance_km < 5.0:
            dist_desc = "a close"
        else:
            dist_desc = "a moderate"

        if relative_velocity_kms > 10.0:
            vel_desc = "very high"
        elif relative_velocity_kms > 5.0:
            vel_desc = "high"
        else:
            vel_desc = "moderate"

        trend_text = f" The risk trend is currently {trend}." if trend else ""

        explanation = (
            f"[{risk_caps} RISK] {primary_name} is projected to have {dist_desc} approach "
            f"with {secondary_name} at a miss distance of {miss_distance_km:.2f} km. "
            f"The encounter will occur at a {vel_desc} relative velocity of {relative_velocity_kms:.2f} km/s. "
            f"The estimated collision probability is {prob_str}.{trend_text}"
        )

        return explanation
