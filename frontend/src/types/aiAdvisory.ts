import type { RiskLevel } from "./alert";

export interface AdvisoryRecommendationContent {
  qualitative_risk_summary: string;
  maneuver_strategy: string;
  burn_direction_rationale: string;
  optimal_timing_window: string;
  operational_tradeoffs: string[];
  verification_checklist: string[];
  confidence_assessment?: string;
  disclaimer: string;
}

export interface AIManeuverAdvisory {
  id: string;
  alertId: string;
  satelliteNoradId: number;
  satelliteName: string;
  secondaryName: string;
  secondaryNoradId: number;
  riskLevel: RiskLevel;
  missDistanceKm: number;
  tca: string;
  recommendation: AdvisoryRecommendationContent;
  modelUsed: string;
  isCached: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface AdvisoryRecommendationRequest {
  alert_id: string;
  force_refresh?: boolean;
}
