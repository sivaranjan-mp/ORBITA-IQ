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
  ownerName?: string | null;
  ownerEmployeeId?: string | null;
  altitudeKm: number | null;
  latitudeDeg?: number | null;
  longitudeDeg?: number | null;
  velocityKmS?: number | null;
  inclinationDeg: number | null;
  periodMinutes: number | null;
  eccentricity: number | null;
  lastTleEpoch: string | null; // ISO timestamp
  /** Orbital elements used only to animate a simplified ground-track demo. */
  raanDeg: number | null;
  meanAnomalyDeg: number | null;
}
