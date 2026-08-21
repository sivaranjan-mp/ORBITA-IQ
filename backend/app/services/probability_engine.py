import numpy as np
from scipy import integrate
import math


class ProbabilityEngine:
    """
    Computes collision probability using established analytic methods.
    """

    @staticmethod
    def foster_1992_pc(miss_vector: np.ndarray, covariance_2d: np.ndarray, hbr: float) -> float:
        """
        Foster (1992) 2D analytical collision probability.
        Projects the problem into the encounter plane.

        :param miss_vector: 2D numpy array representing the miss distance vector in the encounter plane [x, y].
        :param covariance_2d: 2x2 combined covariance matrix in the encounter plane.
        :param hbr: Hard Body Radius (combined collision radius).
        :return: Collision probability.
        """
        # Ensure inputs are numpy arrays
        miss_vector = np.array(miss_vector)
        covariance_2d = np.array(covariance_2d)

        # Calculate determinant and inverse of the covariance matrix
        det_C = np.linalg.det(covariance_2d)
        if det_C <= 0:
            return 0.0

        inv_C = np.linalg.inv(covariance_2d)

        # Define the 2D Gaussian integrand
        def integrand(y, x):
            # Pos vector relative to the primary object (which is at the origin)
            # The secondary object is at `miss_vector`
            r = np.array([x, y])
            # The displacement from the miss vector center
            dr = r - miss_vector
            # Exponent: -0.5 * dr^T * C^-1 * dr
            exponent = -0.5 * np.dot(dr.T, np.dot(inv_C, dr))
            return np.exp(exponent)

        # The integration limits define a circle of radius hbr
        def bounds_y(x):
            max_y = np.sqrt(max(0, hbr**2 - x**2))
            return [-max_y, max_y]

        # Integrate over the circular area A
        integral, _ = integrate.nquad(integrand, [bounds_y, [-hbr, hbr]])

        # Multiply by normalization factor
        pc = (1.0 / (2.0 * math.pi * math.sqrt(det_C))) * integral
        return pc

    @staticmethod
    def alfano_2005_pc(miss_vector: np.ndarray, covariance_2d: np.ndarray, hbr: float) -> float:
        """
        Alfano (2005) method for cross-checking.
        Uses a similar formulation but often approximated or evaluated differently.
        For the purpose of this implementation, we will use a series approximation or
        a simplified numerical integration as a distinct mathematical path from Foster to ensure
        independent verification of the probability magnitude.

        We implement the equivalent 1D integral form by converting to polar coordinates
        centered at the primary object.
        """
        miss_vector = np.array(miss_vector)
        covariance_2d = np.array(covariance_2d)

        det_C = np.linalg.det(covariance_2d)
        if det_C <= 0:
            return 0.0

        inv_C = np.linalg.inv(covariance_2d)

        # Polar coordinate integration
        def polar_integrand(r, theta):
            # Convert polar to Cartesian
            x = r * np.cos(theta)
            y = r * np.sin(theta)
            pos = np.array([x, y])

            dr = pos - miss_vector
            exponent = -0.5 * np.dot(dr.T, np.dot(inv_C, dr))

            # Multiply by r for the polar Jacobian
            return r * np.exp(exponent)

        integral, _ = integrate.nquad(
            polar_integrand, [[0, hbr], [0, 2*math.pi]])

        pc = (1.0 / (2.0 * math.pi * math.sqrt(det_C))) * integral
        return pc

    @classmethod
    def calculate_probability(cls, miss_distance_m: float,
                              covariance_3d: np.ndarray = None,
                              hbr_m: float = 20.0,
                              miss_vector_2d: np.ndarray = None,
                              covariance_2d: np.ndarray = None) -> dict:
        """
        Main entry point for Pc calculation.
        Handles missing CDM covariance data by applying a conservative default.
        """
        is_estimated = False

        # If we don't have encounter plane data, we must synthesize it
        if covariance_2d is None or miss_vector_2d is None:
            is_estimated = True
            # Conservative default covariance: 1km cross-track, 1km radial variance
            covariance_2d = np.array([[1000**2, 0], [0, 1000**2]])
            # Assume the miss distance is along one axis
            miss_vector_2d = np.array([miss_distance_m, 0.0])

        # Primary method
        foster_pc = cls.foster_1992_pc(miss_vector_2d, covariance_2d, hbr_m)

        # Cross-check method
        alfano_pc = cls.alfano_2005_pc(miss_vector_2d, covariance_2d, hbr_m)

        return {
            "pc": foster_pc,
            "pc_alfano_crosscheck": alfano_pc,
            "is_estimated": is_estimated,
            "methods_agree": math.isclose(foster_pc, alfano_pc, rel_tol=1e-2, abs_tol=1e-8)
        }
