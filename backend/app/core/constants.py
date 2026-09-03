"""
Core constants and configurable thresholds for ORBITA-IQ Conjunction Assessment Engine.
"""

# Earth and Astrodynamics Constants
MU_EARTH_KM3_S2 = 398600.4418   # Standard gravitational parameter (km^3/s^2)
WGS84_EARTH_RADIUS_KM = 6378.137 # Earth equatorial radius (km)

# Conjunction Screening Configuration
DEFAULT_LOOKAHEAD_HOURS = 120.0  # 5-day rolling screening window (120 hours)
COARSE_STEP_SECONDS = 60         # Step size for Stage 2 coarse propagation scan
STAGE1_ALTITUDE_MARGIN_KM = 50.0 # Perigee/Apogee overlap threshold margin (Stage 1 coarse filter)
MAX_SCREEN_MISS_DISTANCE_KM = 50.0 # Upper limit to record close approaches

# Conjunction Risk Level Thresholds (Miss Distance in km)
# | Miss Distance | Risk Level |
# | < 1 km        | Critical   |
# | 1 - 5 km      | High       |
# | 5 - 25 km     | Medium     |
# | 25 - 50 km    | Low        |
# | > 50 km       | Discarded  |
CRITICAL_MISS_DISTANCE_KM = 1.0
HIGH_MISS_DISTANCE_KM = 5.0
MEDIUM_MISS_DISTANCE_KM = 25.0
LOW_MISS_DISTANCE_KM = 50.0

# Probability Thresholds (Collision Probability Pc)
CRITICAL_PROBABILITY = 1e-4      # 1 in 10,000
HIGH_PROBABILITY = 1e-5          # 1 in 100,000
MEDIUM_PROBABILITY = 1e-6        # 1 in 1,000,000

# Retention / Cleanup Window
STALE_ALERT_CLEANUP_HOURS = 2.0  # Conjunctions whose TCA has passed by >2 hours are marked resolved/purged
