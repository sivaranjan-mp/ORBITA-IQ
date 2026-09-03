export type RiskLevel = "low" | "medium" | "high" | "critical";
export type AlertStatus = "open" | "monitoring" | "resolved" | "dismissed" | "active" | "acknowledged";
export type ScreeningScope = "fleet_vs_fleet" | "fleet_vs_catalog";

export interface ConjunctionAlert {
  id: string;
  primarySatellite: string;
  primaryNoradId: number;
  secondaryObject: string;
  secondaryNoradId: number;
  tca: string; // ISO timestamp — time of closest approach
  missDistanceM: number;
  missDistanceKm?: number;
  relativeVelocityKmS?: number;
  probability: number; // 0..1
  riskLevel: RiskLevel;
  status: AlertStatus;
  screeningScope?: ScreeningScope | string;
  detectedBy: "satguard" | "cdm_upload" | "manual" | string;
  createdAt: string;
  computedAt?: string;
}
