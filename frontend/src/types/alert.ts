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

export interface AlertStatusHistoryItem {
  id: string;
  alertId: string;
  primarySatellite: string;
  primaryNoradId: number;
  secondaryObject: string;
  secondaryNoradId: number;
  riskLevel: RiskLevel;
  previousStatus: AlertStatus;
  newStatus: AlertStatus;
  actionTaken: string;
  changedBy?: string | null;
  operatorName?: string | null;
  changedAt: string;
  notes?: string | null;
}

export interface AlertStatusHistoryListResponse {
  items: AlertStatusHistoryItem[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

