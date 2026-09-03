import { useEffect, useState, useRef, useCallback } from "react";

import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/apiClient";
import { DEFAULT_SATELLITES } from "@/data/defaultSatellites";
import type { Satellite } from "@/types/satellite";

const MOCK_SATELLITES: Satellite[] = DEFAULT_SATELLITES;


const SYNC_CYCLE_SECONDS = 10;

function areSatellitesEqual(a: Satellite[], b: Satellite[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    const s1 = a[i];
    const s2 = b[i];
    if (
      s1.id !== s2.id ||
      s1.status !== s2.status ||
      s1.altitudeKm !== s2.altitudeKm ||
      s1.latitudeDeg !== s2.latitudeDeg ||
      s1.longitudeDeg !== s2.longitudeDeg ||
      s1.velocityKmS !== s2.velocityKmS
    ) {
      return false;
    }
  }
  return true;
}

export function useSatellites(scope: "mine" | "all" = "mine") {
  const { profile, session } = useAuth();
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const satellitesRef = useRef<Satellite[]>([]);
  satellitesRef.current = satellites;

  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [secondsUntilNextSync, setSecondsUntilNextSync] = useState(SYNC_CYCLE_SECONDS);

  const fetchSatellites = useCallback(
    async (silent = false) => {
      if (!silent) setIsLoading(true);
      else setIsSyncing(true);

      try {
        const { data } = await apiClient.get<Satellite[]>(`/satellites?scope=${scope}`);
        if (Array.isArray(data)) {
          // Avoid triggering unnecessary React re-renders if content is functionally identical
          if (!areSatellitesEqual(satellitesRef.current, data)) {
            setSatellites(data);
          }
        } else {
          setSatellites([]);
        }
        setError(null);
        setLastUpdated(new Date());
        setSecondsUntilNextSync(SYNC_CYCLE_SECONDS);
      } catch {
        const currentEmployee = profile?.employee_id || "EMP-979392CE";
        const mockWithCurrent = MOCK_SATELLITES.map((s, idx) =>
          idx === 0 ? { ...s, ownerOrg: currentEmployee } : s
        );
        const fallback =
          scope === "mine"
            ? mockWithCurrent.filter((s) => s.ownerOrg === currentEmployee)
            : mockWithCurrent;
        if (satellitesRef.current.length === 0) {
          setSatellites(fallback);
        }
        setError("Connecting to satellite telemetry stream...");
      } finally {
        if (!silent) setIsLoading(false);
        setIsSyncing(false);
      }
    },
    [scope, profile?.employee_id]
  );

  // Manual Instant Refresh trigger
  const instantSync = useCallback(() => {
    setSecondsUntilNextSync(SYNC_CYCLE_SECONDS);
    return fetchSatellites(true);
  }, [fetchSatellites]);

  // Initial load
  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);

    fetchSatellites(false);

    // 1-second cadence countdown for the 10-second sync cycle
    const countdownInterval = setInterval(() => {
      if (cancelled) return;
      setSecondsUntilNextSync((prev) => {
        if (prev <= 1) {
          // Trigger the 10s silent refresh
          fetchSatellites(true);
          return SYNC_CYCLE_SECONDS;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      cancelled = true;
      clearInterval(countdownInterval);
    };
  }, [fetchSatellites, session?.user?.id]);

  return {
    satellites,
    isLoading,
    isSyncing,
    error,
    lastUpdated,
    secondsUntilNextSync,
    instantSync,
    refetch: () => fetchSatellites(false),
  };
}
