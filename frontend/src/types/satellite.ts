export type SatelliteStatus = "active" | "degraded" | "inactive" | "decayed";
export type ObjectType = "payload" | "debris" | "rocket_body" | "unknown";

export interface Satellite {
  id: string;
  noradId: number;
  name: string;
  internationalDesignator: string;
  objectType: ObjectType;
  status: SatelliteStatus;
  ownerOrg: string;
  altitudeKm: number;
  latitudeDeg: number;
  longitudeDeg: number;
  velocityKmS: number;
  inclinationDeg: number;
  periodMinutes: number;
  eccentricity: number;
  lastTleEpoch: string; // ISO timestamp
  /** Orbital elements used only to animate a simplified ground-track demo. */
  raanDeg: number;
  meanAnomalyDeg: number;
}
