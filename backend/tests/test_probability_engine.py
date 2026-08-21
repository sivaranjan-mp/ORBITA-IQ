import numpy as np
import math
from app.services.probability_engine import ProbabilityEngine


def test_foster_1992_pc_reference_case():
    """
    Test Foster 1992 implementation against a known analytical case.
    For a spherical covariance matrix (sigma_x = sigma_y = sigma) and zero miss distance,
    the 2D Gaussian integral over a circle of radius R is analytically:
    Pc = 1 - exp(-R^2 / (2 * sigma^2))
    """
    sigma = 10.0
    hbr = 10.0

    covariance_2d = np.array([
        [sigma**2, 0],
        [0, sigma**2]
    ])
    miss_vector = np.array([0.0, 0.0])

    # 1 - exp(-0.5) ≈ 0.393469
    expected_pc = 1.0 - math.exp(- (hbr**2) / (2 * sigma**2))

    calculated_pc = ProbabilityEngine.foster_1992_pc(
        miss_vector, covariance_2d, hbr)

    assert math.isclose(calculated_pc, expected_pc, rel_tol=1e-4)


def test_calculate_probability_estimates():
    """
    Test the main entry point to ensure it falls back to estimated covariance properly.
    """
    result = ProbabilityEngine.calculate_probability(miss_distance_m=500.0)

    assert result["is_estimated"] is True
    assert "pc" in result
    assert "pc_alfano_crosscheck" in result
    assert result["methods_agree"] is True
