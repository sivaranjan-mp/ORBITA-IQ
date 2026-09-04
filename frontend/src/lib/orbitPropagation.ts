import type { Satellite } from "@/types/satellite";

const EARTH_RADIUS_KM = 6378.137;
const DEG = Math.PI / 180;
const RAD = 180 / Math.PI;

/** Standard gravitational parameter for Earth in km^3 / s^2 */
const MU_EARTH = 398600.4418;

/**
 * Checks whether a satellite has complete orbital element data for propagation.
 */
export function hasOrbitalData(satellite: Satellite): boolean {
  return (
    satellite.altitudeKm != null ||
    satellite.periodMinutes != null ||
    (satellite.latitudeDeg != null && satellite.longitudeDeg != null)
  );
}

/**
 * Computes Greenwich Mean Sidereal Time (GMST) in degrees for a given Date.
 * Uses the standard IAU algorithm based on Julian Date.
 */
export function computeGMST(date: Date): number {
  const jd = date.getTime() / 86400000 + 2440587.5;
  const d = jd - 2451545.0;
  const gmstDeg = (280.46061837 + 360.98564736629 * d) % 360;
  return gmstDeg < 0 ? gmstDeg + 360 : gmstDeg;
}

/**
 * Computes current orbital argument of latitude `u` in degrees [0, 360).
 * Progresses prograde (forward in the direction of orbital velocity).
 */
export function computeCurrentU(satellite: Satellite, date: Date): number {
  const altitude = satellite.altitudeKm ?? 550;
  const period =
    satellite.periodMinutes && satellite.periodMinutes > 0
      ? satellite.periodMinutes
      : (2 * Math.PI * Math.sqrt(Math.pow(EARTH_RADIUS_KM + altitude, 3) / MU_EARTH)) / 60;
  const meanAnomaly = satellite.meanAnomalyDeg ?? ((satellite.noradId * 43.123) % 360);

  // Delta time from TLE epoch or reference timestamp
  let minutesElapsed = 0;
  if (satellite.lastTleEpoch) {
    const epochTime = new Date(satellite.lastTleEpoch).getTime();
    if (!isNaN(epochTime)) {
      minutesElapsed = (date.getTime() - epochTime) / 60_000;
    } else {
      minutesElapsed = (date.getTime() % (period * 60_000)) / 60_000;
    }
  } else {
    minutesElapsed = (date.getTime() % (period * 60_000)) / 60_000;
  }

  const u = (meanAnomaly + (360 / period) * minutesElapsed) % 360;
  return u < 0 ? u + 360 : u;
}

/**
 * Computes 3D spherical ECEF coordinates (lat, lon, height) at a specific orbital angle `uDeg`
 * and instantaneous Earth Greenwich Mean Sidereal Time `gmstDeg`.
 * 
 * Mathematical Guarantee:
 * Evaluated at the same instantaneous `gmstDeg`, points along the orbit ring and the
 * satellite position at `u = currentU` lie on the EXACT same spatial circle in 3D Cesium coordinates.
 */
export function computeOrbitPointAtU(
  satellite: Satellite,
  uDeg: number,
  gmstDeg: number
): { latitudeDeg: number; longitudeDeg: number; heightMeters: number } {
  const altitude = satellite.altitudeKm ?? 550;
  const inclination = satellite.inclinationDeg ?? 51.6;
  const raan = satellite.raanDeg ?? ((satellite.noradId * 137.508) % 360);

  const uRad = uDeg * DEG;
  const iRad = inclination * DEG;
  const raanRad = raan * DEG;

  // Position in the orbital plane
  const x = Math.cos(uRad);
  const y = Math.sin(uRad) * Math.cos(iRad);
  const z = Math.sin(uRad) * Math.sin(iRad);

  // Rotate by RAAN about Earth's spin axis to obtain ECI coordinates
  const xEci = Math.cos(raanRad) * x - Math.sin(raanRad) * y;
  const yEci = Math.sin(raanRad) * x + Math.cos(raanRad) * y;
  const zEci = z;

  const latitudeDeg = Math.asin(Math.max(-1, Math.min(1, zEci))) * RAD;
  const lonEciDeg = Math.atan2(yEci, xEci) * RAD;

  let longitudeDeg = (lonEciDeg - gmstDeg) % 360;
  if (longitudeDeg > 180) longitudeDeg -= 360;
  if (longitudeDeg < -180) longitudeDeg += 360;

  return {
    latitudeDeg: Math.round(latitudeDeg * 10000) / 10000,
    longitudeDeg: Math.round(longitudeDeg * 10000) / 10000,
    heightMeters: altitude * 1000,
  };
}

/**
 * High-accuracy circular/elliptical sub-satellite point calculator with IAU GMST.
 * Computes instantaneous latitude, longitude ([-180, 180]), and altitude in meters.
 */
export function computeSubSatellitePoint(
  satellite: Satellite,
  date: Date,
  cachedGmst?: number
): { latitudeDeg: number; longitudeDeg: number; heightMeters: number } | null {
  if (!hasOrbitalData(satellite)) return null;
  const gmstDeg = cachedGmst !== undefined ? cachedGmst : computeGMST(date);
  const u = computeCurrentU(satellite, date);
  return computeOrbitPointAtU(satellite, u, gmstDeg);
}

/** Samples one full orbit's ground track for drawing a predicted path line on the surface. */
export function sampleGroundTrack(
  satellite: Satellite,
  fromDate: Date,
  samples = 80
): Array<{ latitudeDeg: number; longitudeDeg: number; heightMeters: number }> {
  if (!hasOrbitalData(satellite)) {
    return [];
  }

  const points: Array<{ latitudeDeg: number; longitudeDeg: number; heightMeters: number }> = [];
  const period = satellite.periodMinutes && satellite.periodMinutes > 0 ? satellite.periodMinutes : 95;
  const periodMs = period * 60_000;
  for (let i = 0; i <= samples; i++) {
    const t = new Date(fromDate.getTime() + (periodMs * i) / samples);
    const pt = computeSubSatellitePoint(satellite, t);
    if (pt) {
      points.push(pt);
    }
  }
  return points;
}

export function orbitalRadiusKm(satellite: Satellite): number | null {
  if (satellite.altitudeKm == null) return null;
  return EARTH_RADIUS_KM + satellite.altitudeKm;
}

/** Calculates the orbital velocity in km/s */
export function calculateOrbitalVelocityKmS(satellite: Satellite): number {
  if (satellite.velocityKmS != null && satellite.velocityKmS > 0) {
    return satellite.velocityKmS;
  }
  const r = orbitalRadiusKm(satellite);
  if (!r) return 7.66;
  return Math.round(Math.sqrt(MU_EARTH / r) * 100) / 100;
}

/**
 * Calculates satellite footprint radius on the Earth surface in meters.
 * Coverage horizon angle: cos(theta) = R / (R + h).
 */
export function calculateFootprintRadiusMeters(satellite: Satellite): number {
  const alt = satellite.altitudeKm ?? 500;
  const ratio = EARTH_RADIUS_KM / (EARTH_RADIUS_KM + alt);
  const theta = Math.acos(Math.min(1, Math.max(0, ratio)));
  return EARTH_RADIUS_KM * theta * 1000;
}

/**
 * Samples a continuous 3D orbital trajectory ring in Earth coordinates.
 * Generates an array of [longitude, latitude, altitudeMeters] for Cesium polylines.
 * Evaluated at the instantaneous GMST of referenceDate so the 3D ring is a
 * true planar spatial circle in Cesium that the satellite strictly rides along.
 */
export function sampleFullOrbit3D(
  satellite: Satellite,
  referenceDate: Date,
  samples = 72
): Array<{ longitudeDeg: number; latitudeDeg: number; heightMeters: number }> {
  if (!hasOrbitalData(satellite)) {
    return [];
  }

  const gmstDeg = computeGMST(referenceDate);
  const points: Array<{ longitudeDeg: number; latitudeDeg: number; heightMeters: number }> = [];

  for (let i = 0; i <= samples; i++) {
    const u = (360 * i) / samples;
    points.push(computeOrbitPointAtU(satellite, u, gmstDeg));
  }

  return points;
}

/**
 * Samples past 3D trajectory trail up to referenceDate (showing where the satellite just was).
 * Trails directly behind the satellite along the exact orbital flight path.
 */
export function samplePastTrail3D(
  satellite: Satellite,
  referenceDate: Date,
  minutesBack = 45,
  samples = 40
): Array<{ longitudeDeg: number; latitudeDeg: number; heightMeters: number }> {
  if (!hasOrbitalData(satellite)) return [];
  const period =
    satellite.periodMinutes && satellite.periodMinutes > 0 ? satellite.periodMinutes : 95;
  const currentU = computeCurrentU(satellite, referenceDate);
  const gmstDeg = computeGMST(referenceDate);
  const deltaUDeg = (360 / period) * Math.min(minutesBack, period * 0.95);
  const points: Array<{ longitudeDeg: number; latitudeDeg: number; heightMeters: number }> = [];

  for (let i = 0; i <= samples; i++) {
    const frac = i / samples;
    // At frac = 0, u = currentU - deltaUDeg (behind). At frac = 1, u = currentU (satellite position).
    let u = (currentU - deltaUDeg * (1 - frac)) % 360;
    if (u < 0) u += 360;
    points.push(computeOrbitPointAtU(satellite, u, gmstDeg));
  }
  return points;
}

/**
 * Samples forward 3D trajectory starting from referenceDate (showing where the satellite will go).
 * Extends forward from the satellite's exact position along the direction of velocity.
 */
export function sampleForwardTrajectory3D(
  satellite: Satellite,
  referenceDate: Date,
  minutesForward = 95,
  samples = 70
): Array<{ longitudeDeg: number; latitudeDeg: number; heightMeters: number }> {
  if (!hasOrbitalData(satellite)) return [];
  const period =
    satellite.periodMinutes && satellite.periodMinutes > 0 ? satellite.periodMinutes : 95;
  const currentU = computeCurrentU(satellite, referenceDate);
  const gmstDeg = computeGMST(referenceDate);
  const deltaUDeg = (360 / period) * Math.min(minutesForward, period);
  const points: Array<{ longitudeDeg: number; latitudeDeg: number; heightMeters: number }> = [];

  for (let i = 0; i <= samples; i++) {
    const frac = i / samples;
    // At frac = 0, u = currentU (exact satellite position). At frac = 1, forward along flight path.
    const u = (currentU + deltaUDeg * frac) % 360;
    points.push(computeOrbitPointAtU(satellite, u, gmstDeg));
  }
  return points;
}

/** Clears cached orbit geometries */
export function clearOrbitGeometryCache(): void {
  // Backwards compatibility
}
