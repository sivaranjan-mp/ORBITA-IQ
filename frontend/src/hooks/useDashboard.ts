import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/apiClient";
import { supabase } from "@/lib/supabaseClient";

export interface DashboardSummary {
  tracked_satellites: number;
  active_alerts: number;
  high_risk_alerts: number;
  next_conjunction: {
    id?: string;
    primarySatellite: string;
    primaryNoradId?: number;
    secondaryObject: string;
    secondaryNoradId?: number;
    tca: string;
    riskLevel: string;
    missDistanceM: number;
    missDistanceKm?: number;
    relativeVelocityKmS?: number;
    probability?: number;
    screeningScope?: string;
  } | null;
  altitude_trend?: Array<{ day: string; altitudeKm: number }>;
}

export function useDashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async (showLoading = true) => {
    if (showLoading) setIsLoading(true);
    try {
      const { data } = await apiClient.get<DashboardSummary>("/dashboard");
      setSummary(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch dashboard summary");
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard(true);

    // Auto-refresh polling every 20 seconds
    const interval = setInterval(() => {
      fetchDashboard(false);
    }, 20000);

    // Supabase Realtime Subscription
    let channel: ReturnType<typeof supabase.channel> | null = null;
    try {
      channel = supabase
        .channel("dashboard_conjunctions_realtime")
        .on(
          "postgres_changes",
          { event: "*", schema: "public", table: "conjunction_alerts" },
          () => {
            fetchDashboard(false);
          }
        )
        .subscribe();
    } catch {
      // Fallback to polling
    }

    return () => {
      clearInterval(interval);
      if (channel) {
        supabase.removeChannel(channel);
      }
    };
  }, [fetchDashboard]);

  return { summary, isLoading, error, refetch: fetchDashboard };
}
