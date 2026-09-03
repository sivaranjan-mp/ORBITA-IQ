import type { Satellite } from "@/types/satellite";

const EARTH_RADIUS_KM = 6371;
const DEG = Math.PI / 180;
const RAD = 180 / Math.PI;

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
 * Simplified circular-orbit ground-track model for visualization only.
 * Returns null if the satellite has no valid orbit_state data.
 */
export function computeSubSatellitePoint(
  satellite: Satellite,
  date: Date
): { latitudeDeg: number; longitudeDeg: number; heightMeters: number } | null {
  if (!hasOrbitalData(satellite)) {
    return null;
  }

  const minutesSinceEpoch = date.getTime() / 60_000;

  const meanAnomaly = satellite.meanAnomalyDeg!;
  const period = satellite.periodMinutes!;
  const inclination = satellite.inclinationDeg!;
  const raan = satellite.raanDeg!;
  const altitude = satellite.altitudeKm!;

  const u = (meanAnomaly + (360 / period) * minutesSinceEpoch) % 360;
  const uRad = u * DEG;
  const iRad = inclination * DEG;
  const raanRad = raan * DEG;

  // Position in the orbital plane, rotated by inclination about the node line.
  const x = Math.cos(uRad);
  const y = Math.sin(uRad) * Math.cos(iRad);
  const z = Math.sin(uRad) * Math.sin(iRad);

  // Rotate by RAAN about Earth's spin axis to get ECI coordinates.
  const xEci = Math.cos(raanRad) * x - Math.sin(raanRad) * y;
  const yEci = Math.sin(raanRad) * x + Math.cos(raanRad) * y;
  const zEci = z;

  const latitudeDeg = Math.asin(zEci) * RAD;
  const lonEciDeg = Math.atan2(yEci, xEci) * RAD;

  // Earth rotates ~360.9856 deg per sidereal day; subtract that rotation
  // to convert the ECI longitude into an Earth-fixed (ground track) longitude.
  const daysSinceEpoch = minutesSinceEpoch / 1440;
  const earthRotationDeg = (360.9856123 * daysSinceEpoch) % 360;

  let longitudeDeg = (lonEciDeg - earthRotationDeg) % 360;
  if (longitudeDeg > 180) longitudeDeg -= 360;
  if (longitudeDeg < -180) longitudeDeg += 360;

  return {
    latitudeDeg,
    longitudeDeg,
    heightMeters: altitude * 1000,
  };
}

/** Samples one full orbit's ground track for drawing a predicted path line. Returns empty array if no orbital data. */
export function sampleGroundTrack(satellite: Satellite, fromDate: Date, samples = 90) {
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

/** Standard gravitational parameter for Earth in km^3 / s^2 */
const MU_EARTH = 398600.4418;

/** Calculates the orbital velocity in km/s */
export function calculateOrbitalVelocityKmS(satellite: Satellite): number {
  if (satellite.velocityKmS != null && satellite.velocityKmS > 0) {
    return satellite.velocityKmS;
  }
  const r = orbitalRadiusKm(satellite);
  if (!r) return 7.6;
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
 */
export function sampleFullOrbit3D(
  satellite: Satellite,
  referenceDate: Date,
  samples = 120
): Array<{ longitudeDeg: number; latitudeDeg: number; heightMeters: number }> {
  if (!hasOrbitalData(satellite)) {
    return [];
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

  return points;
}

