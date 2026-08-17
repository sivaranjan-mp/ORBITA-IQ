import type { Satellite } from "@/types/satellite";

const EARTH_RADIUS_KM = 6371;
const DEG = Math.PI / 180;
const RAD = 180 / Math.PI;

/**
 * Simplified circular-orbit ground-track model for visualization only.
 *
 * This is intentionally NOT SGP4 — real propagation belongs server-side
 * (see the `sgp4_service` in the backend architecture, driven by TLE/OMM
 * data from CelesTrak). This client-side model just needs to look and
 * move like a real satellite: it rotates the orbital plane by
 * inclination + RAAN, advances the argument of latitude over time by the
 * orbital period, and accounts for Earth's rotation underneath the orbit
 * so ground tracks drift westward the way real ones do.
 */
export function computeSubSatellitePoint(
  satellite: Satellite,
  date: Date
): { latitudeDeg: number; longitudeDeg: number; heightMeters: number } {
  const minutesSinceEpoch = date.getTime() / 60_000;

  const u =
    (satellite.meanAnomalyDeg + (360 / satellite.periodMinutes) * minutesSinceEpoch) % 360;
  const uRad = u * DEG;
  const iRad = satellite.inclinationDeg * DEG;
  const raanRad = satellite.raanDeg * DEG;

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
    heightMeters: satellite.altitudeKm * 1000,
  };
}

/** Samples one full orbit's ground track for drawing a predicted path line. */
export function sampleGroundTrack(satellite: Satellite, fromDate: Date, samples = 90) {
  const points: Array<{ latitudeDeg: number; longitudeDeg: number; heightMeters: number }> = [];
  const periodMs = satellite.periodMinutes * 60_000;
  for (let i = 0; i <= samples; i++) {
    const t = new Date(fromDate.getTime() + (periodMs * i) / samples);
    points.push(computeSubSatellitePoint(satellite, t));
  }
  return points;
}

export function orbitalRadiusKm(satellite: Satellite): number {
  return EARTH_RADIUS_KM + satellite.altitudeKm;
}
