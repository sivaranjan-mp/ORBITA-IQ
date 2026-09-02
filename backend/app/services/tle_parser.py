import math
import re
from datetime import datetime, timedelta, timezone
from sgp4.api import Satrec
from app.services.sgp4_service import propagate_tle


def parse_tle(raw_tle: str) -> dict:
    """
    Parses a raw 2-line or 3-line TLE string into a structured dictionary
    containing both the raw lines and derived orbital elements.
    """
    lines = [line.strip() for line in raw_tle.split("\n") if line.strip()]
    if len(lines) == 2:
        name = None
        line1, line2 = lines
    elif len(lines) >= 3:
        line0 = lines[0].strip()
        # In 3LE format, line 0 may start with '0 ' (or '0' followed by spaces)
        name = re.sub(r"^0\s+", "", line0).strip() or None
        line1 = lines[1]
        line2 = lines[2]
    else:
        raise ValueError("Invalid TLE string: must contain at least 2 lines.")

    # Parse using SGP4
    sat = Satrec.twoline2rv(line1, line2)

    # Calculate Epoch timestamp
    year = sat.epochyr
    full_year = year + 2000 if year < 57 else year + 1900
    epoch_start = datetime(full_year, 1, 1, tzinfo=timezone.utc)
    epoch_ts = epoch_start + timedelta(days=sat.epochdays - 1)

    # Calculate Period in minutes (sat.no_kozai is radians/minute)
    no_kozai = sat.no_kozai
    period_minutes = (2 * math.pi / no_kozai) if no_kozai > 0 else 0

    # Calculate Approximate Altitude (Assuming circular orbit for the dashboard's average altitude)
    n_rad_s = no_kozai / 60.0
    mu = 398600.4418  # Earth's standard gravitational parameter in km^3/s^2
    earth_radius = 6371.0

    if n_rad_s > 0:
        a = (mu / (n_rad_s ** 2)) ** (1/3)
        altitude_km = a - earth_radius
    else:
        altitude_km = 0

    # Compute geodetic position (lat, lon, vel) at current time (or epoch fallback)
    now_utc = datetime.now(timezone.utc)
    prop_state = propagate_tle(line1, line2, now_utc) or propagate_tle(line1, line2, epoch_ts)
    if not prop_state:
        raise ValueError(
            "TLE could not be propagated — it may be corrupted, malformed, or "
            "critically stale. Please verify the TLE and try again with a fresh one."
        )

    lat_deg = prop_state["latitude_deg"] if prop_state else None
    lon_deg = prop_state["longitude_deg"] if prop_state else None
    vel_km_s = prop_state["velocity_km_s"] if prop_state else None
    if prop_state and prop_state.get("altitude_km") is not None:
        altitude_km = prop_state["altitude_km"]

    return {
        "name": name,
        "line1": line1,
        "line2": line2,
        "norad_id": int(line1[2:7]),
        "international_designator": line1[9:17].strip(),
        "epoch": epoch_ts,
        "inclinationDeg": math.degrees(sat.inclo),
        "raanDeg": math.degrees(sat.nodeo),
        "eccentricity": sat.ecco,
        "periodMinutes": period_minutes,
        "meanAnomalyDeg": math.degrees(sat.mo),
        "altitudeKm": altitude_km,
        "latitudeDeg": lat_deg,
        "longitudeDeg": lon_deg,
        "velocityKmS": vel_km_s
    }
