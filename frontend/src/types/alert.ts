export type RiskLevel = "low" | "medium" | "high" | "critical";
export type AlertStatus = "open" | "monitoring" | "resolved" | "dismissed";

export interface ConjunctionAlert {
  id: string;
  primarySatellite: string;
  primaryNoradId: number;
  secondaryObject: string;
  secondaryNoradId: number;
  tca: string; // ISO timestamp — time of closest approach
  missDistanceM: number;
  relativeVelocityKmS: number;
  probability: number; // 0..1
  riskLevel: RiskLevel;
  status: AlertStatus;
  detectedBy: "satguard" | "cdm_upload" | "manual";
  createdAt: string;
}
