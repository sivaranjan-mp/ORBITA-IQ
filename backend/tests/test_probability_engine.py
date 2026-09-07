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


def test_hbr_resolution_and_scaling():
    """
    Verify that HBR defaults to 1.5m (CARA standard) and scales collision probability
    proportionally with collision disk area (R^2).
    """
    # 1. Default resolution for unknown object
    hbr_default, is_known_def = ProbabilityEngine.resolve_hbr(None)
    assert hbr_default == 1.5
    assert is_known_def is False

    # 2. Known ISS (NORAD 25544) resolution
    hbr_iss, is_known_iss = ProbabilityEngine.resolve_hbr(None, norad_id=25544)
    assert hbr_iss == 54.0
    assert is_known_iss is True

    # 3. Custom hard_body_radius_m on object dict
    custom_obj = {"name": "TEST_SAT", "hard_body_radius_m": 8.5}
    hbr_cust, is_known_cust = ProbabilityEngine.resolve_hbr(custom_obj)
    assert hbr_cust == 8.5
    assert is_known_cust is True

    # 4. Combination logic: Default (1.5 + 1.5 = 3.0m) vs Known ISS (54.0 + 1.5 = 55.5m)
    h_a, h_b, comb_def, k_a, k_b = ProbabilityEngine.combine_hbr()
    assert comb_def == 3.0
    assert k_a is False and k_b is False

    _, _, comb_iss, k_a_iss, _ = ProbabilityEngine.combine_hbr(norad_a=25544)
    assert comb_iss == 55.5
    assert k_a_iss is True

    # 5. Pc Scaling: Larger HBR collision disk must produce higher probability
    pc_default = ProbabilityEngine.calculate_probability(miss_distance_m=500.0, hbr_m=comb_def)["pc"]
    pc_iss = ProbabilityEngine.calculate_probability(miss_distance_m=500.0, hbr_m=comb_iss)["pc"]

    assert pc_iss > pc_default
    # Collision disk area scales as (55.5 / 3.0)^2 = 342.25x
    ratio = pc_iss / pc_default
    assert 300.0 < ratio < 400.0

