import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/apiClient";
import { supabase } from "@/lib/supabaseClient";
import type { AlertStatus, ConjunctionAlert } from "@/types/alert";

export function useAlerts() {
  const [alerts, setAlerts] = useState<ConjunctionAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isScreening, setIsScreening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAlerts = useCallback(async (showLoading = true) => {
    if (showLoading) setIsLoading(true);
    try {
      const { data } = await apiClient.get<ConjunctionAlert[]>("/alerts");
      if (Array.isArray(data)) {
        setAlerts(data);
      } else {
        setAlerts([]);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch alerts");
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, []);

  const triggerScreening = useCallback(async () => {
    setIsScreening(true);
    try {
      await apiClient.post("/alerts/screen");
      await fetchAlerts(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger screening");
    } finally {
      setIsScreening(false);
    }
  }, [fetchAlerts]);

  const updateAlertStatus = useCallback(async (alertId: string, status: AlertStatus) => {
    try {
      const { data } = await apiClient.put<ConjunctionAlert>(`/alerts/${alertId}/status`, { status });
      setAlerts((prev) => prev.map((a) => (a.id === alertId ? data : a)));
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update alert status");
      throw err;
    }
  }, []);

  useEffect(() => {
    fetchAlerts(true);

    // 1. Polling fallback every 20 seconds
    const interval = setInterval(() => {
      fetchAlerts(false);
    }, 20000);

    // 2. Supabase Realtime Subscription
    let channel: ReturnType<typeof supabase.channel> | null = null;
    try {
      channel = supabase
        .channel("conjunction_alerts_realtime")
        .on(
          "postgres_changes",
          { event: "*", schema: "public", table: "conjunction_alerts" },
          () => {
            fetchAlerts(false);
          }
        )
        .subscribe();
    } catch {
      // If realtime not enabled or offline, fallback to polling
    }

    return () => {
      clearInterval(interval);
      if (channel) {
        supabase.removeChannel(channel);
      }
    };
  }, [fetchAlerts]);

  return {
    alerts,
    isLoading,
    isScreening,
    error,
    refetch: fetchAlerts,
    triggerScreening,
    updateAlertStatus,
  };
}
