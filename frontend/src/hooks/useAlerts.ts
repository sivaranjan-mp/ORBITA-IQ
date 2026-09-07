import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/apiClient";
import { generateSimulatedAlerts } from "@/lib/simulatedAlerts";
import { supabase } from "@/lib/supabaseClient";
import type { AlertStatus, ConjunctionAlert } from "@/types/alert";

// Global cache, in-flight request deduplication, and backoff state
let cachedAlerts: ConjunctionAlert[] | null = null;
let inFlightRequest: Promise<ConjunctionAlert[]> | null = null;
let lastErrorTimestamp = 0;
let failureCount = 0;

// Set of listeners for multi-hook instances across components
const alertListeners = new Set<(alerts: ConjunctionAlert[]) => void>();

function notifyListeners(alerts: ConjunctionAlert[]) {
  cachedAlerts = alerts;
  alertListeners.forEach((listener) => listener(alerts));
}

// Compute exponential backoff cooldown in milliseconds (3s -> 6s -> 12s -> 24s -> 30s max)
function getBackoffCooldownMs(): number {
  if (failureCount === 0) return 0;
  return Math.min(30000, 3000 * Math.pow(2, failureCount - 1));
}

async function executeFetchAlerts(force = false): Promise<ConjunctionAlert[]> {
  const now = Date.now();

  // Deduplicate concurrent requests across all mounting components
  if (inFlightRequest) {
    return inFlightRequest;
  }

  // Backoff check: if within cooldown from previous failure and not a manual force, skip request
  const cooldown = getBackoffCooldownMs();
  if (!force && failureCount > 0 && now - lastErrorTimestamp < cooldown) {
    if (cachedAlerts && cachedAlerts.length > 0) {
      return cachedAlerts;
    }
    const simulated = generateSimulatedAlerts();
    notifyListeners(simulated);
    return simulated;
  }

  inFlightRequest = (async () => {
    try {
      const { data } = await apiClient.get<ConjunctionAlert[]>("/alerts", { timeout: 10000 });
      failureCount = 0; // Reset error count on successful response

      let resultAlerts: ConjunctionAlert[];
      if (Array.isArray(data) && data.length > 0) {
        resultAlerts = data;
      } else {
        resultAlerts = generateSimulatedAlerts();
      }
      notifyListeners(resultAlerts);
      return resultAlerts;
    } catch (err) {
      failureCount++;
      lastErrorTimestamp = Date.now();
      const currentCooldownSec = Math.round(getBackoffCooldownMs() / 1000);
      console.warn(
        `[useAlerts] Fetch /alerts failed (attempt ${failureCount}). Backing off for ${currentCooldownSec}s:`,
        err instanceof Error ? err.message : err
      );

      // Return existing cached alerts or fallback simulation without throwing to caller
      const fallback = cachedAlerts && cachedAlerts.length > 0 ? cachedAlerts : generateSimulatedAlerts();
      notifyListeners(fallback);
      return fallback;
    } finally {
      inFlightRequest = null;
    }
  })();

  return inFlightRequest;
}

export function useAlerts() {
  const [alerts, setAlerts] = useState<ConjunctionAlert[]>(() => cachedAlerts || generateSimulatedAlerts());
  const [isLoading, setIsLoading] = useState(false);
  const [isScreening, setIsScreening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleUpdate = (updatedAlerts: ConjunctionAlert[]) => {
      setAlerts(updatedAlerts);
    };
    alertListeners.add(handleUpdate);
    return () => {
      alertListeners.delete(handleUpdate);
    };
  }, []);

  const fetchAlerts = useCallback(async (showLoading = false, force = false) => {
    if (showLoading && (!cachedAlerts || cachedAlerts.length === 0)) {
      setIsLoading(true);
    }
    try {
      const data = await executeFetchAlerts(force);
      setAlerts(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch alerts");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const triggerScreening = useCallback(async (lookaheadHours: number = 120.0) => {
    setIsScreening(true);
    try {
      await apiClient.post(`/alerts/screen?lookahead_hours=${lookaheadHours}`);
      await fetchAlerts(false, true); // Force immediate refresh on user trigger
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger screening");
    } finally {
      setIsScreening(false);
    }
  }, [fetchAlerts]);

  const updateAlertStatus = useCallback(async (alertId: string, status: AlertStatus) => {
    try {
      const { data } = await apiClient.put<ConjunctionAlert>(`/alerts/${alertId}/status`, { status });
      const updated = alerts.map((a) => (a.id === alertId ? data : a));
      notifyListeners(updated);
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update alert status");
      throw err;
    }
  }, [alerts]);

  useEffect(() => {
    // Initial fetch (honors deduplication if sibling components mount concurrently)
    fetchAlerts(true, false);

    // Single interval polling fallback every 20s (honoring backoff if failures occur)
    const interval = setInterval(() => {
      fetchAlerts(false, false);
    }, 20000);

    // Supabase Realtime Subscription
    let channel: ReturnType<typeof supabase.channel> | null = null;
    try {
      channel = supabase
        .channel("conjunction_alerts_realtime")
        .on(
          "postgres_changes",
          { event: "*", schema: "public", table: "conjunction_alerts" },
          () => {
            fetchAlerts(false, true);
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
    refetch: (showLoading: boolean = true) => fetchAlerts(showLoading, true),
    triggerScreening,
    updateAlertStatus,
  };
}
