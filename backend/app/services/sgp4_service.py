import logging
import math
from datetime import datetime
from typing import Dict, Optional, Tuple
from sgp4.api import Satrec

logger = logging.getLogger(__name__)

# WGS84 Constants
EARTH_RADIUS_KM = 6378.137
FLATTENING = 1.0 / 298.257223563
ECCENTRICITY_SQ = 2 * FLATTENING - FLATTENING ** 2


def compute_gmst(dt: datetime) -> float:
    # Julian date
    jd = dt.toordinal() + 1721425.5 + dt.hour / 24.0 + dt.minute / 1440.0 + \
        dt.second / 86400.0 + dt.microsecond / 86400000000.0
    t = (jd - 2451545.0) / 36525.0
    gmst_deg = 280.46061837 + 360.98564736629 * \
        (jd - 2451545.0) + 0.000387933 * t**2 - (t**3) / 38710000.0
    return math.radians(gmst_deg % 360.0)


def eci_to_geodetic(x: float, y: float, z: float, dt: datetime) -> Tuple[float, float, float]:
    """
    Converts ECI (TEME) coordinates to Geodetic (Latitude, Longitude, Altitude)
    using WGS84 ellipsoid.
    x, y, z in km.
    Returns: (lat_deg, lon_deg, alt_km)
    """
    gmst = compute_gmst(dt)

    # Longitude
    ra = math.atan2(y, x)
    lon = (math.degrees(ra - gmst) + 180) % 360 - 180

    # Latitude & Altitude (Iterative method for WGS84)
    r = math.sqrt(x**2 + y**2)
    lat = math.atan2(z, r)  # Initial guess

    for _ in range(5):
        sin_lat = math.sin(lat)
        N = EARTH_RADIUS_KM / math.sqrt(1 - ECCENTRICITY_SQ * sin_lat**2)
        lat = math.atan2(z + N * ECCENTRICITY_SQ * sin_lat, r)

    sin_lat = math.sin(lat)
    N = EARTH_RADIUS_KM / math.sqrt(1 - ECCENTRICITY_SQ * sin_lat**2)

    if math.cos(lat) != 0:
        alt = (r / math.cos(lat)) - N
    else:
        alt = z / sin_lat - N * (1 - ECCENTRICITY_SQ)

    return math.degrees(lat), lon, alt


def propagate_tle(line1: str, line2: str, dt: datetime) -> Optional[Dict]:
    """
    Propagates a TLE to a given datetime using SGP4.
    Returns dictionary with state vector or None if error.
    """
    try:
        satrec = Satrec.twoline2rv(line1, line2)

        now_jd = dt.toordinal() + 1721425.5
        now_fr = (dt.hour * 3600 + dt.minute * 60 +
                  dt.second + dt.microsecond / 1e6) / 86400.0

        e, r, v = satrec.sgp4(now_jd, now_fr)
        if e != 0:
            logger.warning(f"SGP4 propagation error code {e} for TLE at {dt.isoformat()}")
            return None

        x, y, z = r
        vx, vy, vz = v

        lat, lon, alt = eci_to_geodetic(x, y, z, dt)
        vel = math.sqrt(vx**2 + vy**2 + vz**2)

        inclination_deg = math.degrees(satrec.inclo)
        eccentricity = satrec.ecco
        raan_deg = math.degrees(satrec.nodeo)
        mean_anomaly_deg = math.degrees(satrec.mo)
        mean_motion_rev_day = satrec.no_kozai * (1440.0 / (2.0 * math.pi))
        period_minutes = 1440.0 / mean_motion_rev_day if mean_motion_rev_day > 0 else 0

        return {
            "altitude_km": alt,
            "latitude_deg": lat,
            "longitude_deg": lon,
            "velocity_km_s": vel,
            "inclination_deg": inclination_deg,
            "eccentricity": eccentricity,
            "raan_deg": raan_deg,
            "mean_anomaly_deg": mean_anomaly_deg,
            "period_minutes": period_minutes,
            "epoch": dt,
            "x_km": x,
            "y_km": y,
            "z_km": z,
            "vx_kms": vx,
            "vy_kms": vy,
            "vz_kms": vz
        }
    except Exception as exc:
        # Catch SGP4 or math errors
        logger.warning(f"SGP4 propagation exception for TLE at {dt.isoformat()}: {exc}")
        return None
