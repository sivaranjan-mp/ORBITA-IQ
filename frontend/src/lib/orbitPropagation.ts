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
    satellite.altitudeKm != null &&
    satellite.periodMinutes != null &&
    satellite.periodMinutes > 0 &&
    satellite.inclinationDeg != null &&
    satellite.raanDeg != null &&
    satellite.meanAnomalyDeg != null
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
 * High-accuracy circular/elliptical sub-satellite point calculator with IAU GMST.
 * Computes instantaneous latitude, longitude ([-180, 180]), and altitude in meters.
 * If lastTleEpoch is provided, propagates delta from epoch to prevent floating-point drift.
 */
export function computeSubSatellitePoint(
  satellite: Satellite,
  date: Date
): { latitudeDeg: number; longitudeDeg: number; heightMeters: number } | null {
  if (!hasOrbitalData(satellite)) {
    return null;
  }

  const meanAnomaly = satellite.meanAnomalyDeg!;
  const period = satellite.periodMinutes!;
  const inclination = satellite.inclinationDeg!;
  const raan = satellite.raanDeg!;
  const altitude = satellite.altitudeKm!;

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
    // Wrap to one orbit period to preserve numerical precision
    minutesElapsed = (date.getTime() % (period * 60_000)) / 60_000;
  }

  // Mean anomaly progression (argument of latitude for near-circular orbit)
  const u = (meanAnomaly + (360 / period) * minutesElapsed) % 360;
  const uRad = u * DEG;
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

  // Accurate Greenwich Mean Sidereal Time rotation
  const gmstDeg = computeGMST(date);

  let longitudeDeg = (lonEciDeg - gmstDeg) % 360;
  if (longitudeDeg > 180) longitudeDeg -= 360;
  if (longitudeDeg < -180) longitudeDeg += 360;

  return {
    latitudeDeg: Math.round(latitudeDeg * 10000) / 10000,
    longitudeDeg: Math.round(longitudeDeg * 10000) / 10000,
    heightMeters: altitude * 1000,
  };
}

/** Samples one full orbit's ground track for drawing a predicted path line. Returns empty array if no orbital data. */
export function sampleGroundTrack(
  satellite: Satellite,
  fromDate: Date,
  samples = 80
): Array<{ latitudeDeg: number; longitudeDeg: number; heightMeters: number }> {
  if (!hasOrbitalData(satellite)) {
    return [];
  }

  const points: Array<{ latitudeDeg: number; longitudeDeg: number; heightMeters: number }> = [];
  const periodMs = satellite.periodMinutes! * 60_000;
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

// In-memory geometry cache for 3D full orbit polylines to prevent redundant CPU recalculation
const orbitGeometryCache = new Map<
  string,
  Array<{ longitudeDeg: number; latitudeDeg: number; heightMeters: number }>
>();

/**
 * Samples a continuous 3D orbital trajectory ring in Earth coordinates.
 * Generates an array of [longitude, latitude, altitudeMeters] for Cesium polylines.
 * Uses LRU/Map memoization keyed by satellite ID and orbital elements.
 */
export function sampleFullOrbit3D(
  satellite: Satellite,
  referenceDate: Date,
  samples = 72
): Array<{ longitudeDeg: number; latitudeDeg: number; heightMeters: number }> {
  if (!hasOrbitalData(satellite)) {
    return [];
  }

  // Cache key based on orbit state properties that dictate orbit shape
  const cacheKey = `${satellite.id}_${satellite.altitudeKm}_${satellite.inclinationDeg}_${satellite.raanDeg}_${samples}`;
  const cached = orbitGeometryCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  const periodMinutes = satellite.periodMinutes!;
  const periodMs = periodMinutes * 60_000;
  const points: Array<{ longitudeDeg: number; latitudeDeg: number; heightMeters: number }> = [];

  for (let i = 0; i <= samples; i++) {
    const fraction = i / samples;
    const t = new Date(referenceDate.getTime() + fraction * periodMs);
    const pos = computeSubSatellitePoint(satellite, t);
    if (pos) {
      points.push(pos);
    }
  }

  // Keep cache bounded
  if (orbitGeometryCache.size > 800) {
    const firstKey = orbitGeometryCache.keys().next().value;
    if (firstKey) orbitGeometryCache.delete(firstKey);
  }
  orbitGeometryCache.set(cacheKey, points);

  return points;
}

/** Clears cached orbit geometries */
export function clearOrbitGeometryCache(): void {
  orbitGeometryCache.clear();
}
