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
