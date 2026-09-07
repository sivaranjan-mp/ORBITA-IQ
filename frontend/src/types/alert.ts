export type RiskLevel = "low" | "medium" | "high" | "critical";
export type AlertStatus = "open" | "monitoring" | "resolved" | "dismissed" | "active" | "acknowledged";
export type ScreeningScope = "fleet_vs_fleet" | "fleet_vs_catalog";
export type DataQualityCategory = "HIGH" | "MEDIUM" | "LOW" | "UNRELIABLE";
export type FreshnessTier = "FRESH" | "AGING" | "STALE" | "CRITICAL";

export interface OrbitDataQualityBundle {
  source: string;
  source_code: string;
  is_authoritative: boolean;
  epoch: string;
  ingestion_time: string;
  age_hours: number;
  freshness_tier: FreshnessTier | string;
  propagation_model: string;
  orbit_regime: string;
  data_quality: DataQualityCategory | string;
  covariance_available: boolean;
  covariance_status: string;
  confidence_score: number; // 0..100
  scoring_algorithm_version: string;
}

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
  hbrA?: number;
  hbrAIsKnown?: boolean;
  hbrB?: number;
  hbrBIsKnown?: boolean;
  combinedHbr?: number;
  primaryDataQuality?: OrbitDataQualityBundle;
  secondaryDataQuality?: OrbitDataQualityBundle;
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

