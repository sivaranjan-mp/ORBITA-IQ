import { useEffect, useState } from "react";
import { apiClient } from "@/lib/apiClient";

export interface DashboardSummary {
  tracked_satellites: number;
  active_alerts: number;
  high_risk_alerts: number;
  next_conjunction: {
    primarySatellite: string;
    secondaryObject: string;
    tca: string;
    riskLevel: string;
    missDistanceM: number;
  } | null;
  altitude_trend?: Array<{ day: string; altitudeKm: number }>;
}

export function useDashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchDashboard = async () => {
      try {
        const { data } = await apiClient.get<DashboardSummary>("/dashboard");
        if (!cancelled) {
          setSummary(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to fetch dashboard summary");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchDashboard();
    return () => { cancelled = true; };
  }, []);

  return { summary, isLoading, error };
}
