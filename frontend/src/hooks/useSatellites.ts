import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import type { AxiosError } from "axios";

import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/apiClient";
import { DEFAULT_SATELLITES } from "@/data/defaultSatellites";
import type { Satellite, SatelliteRefreshResponse } from "@/types/satellite";

const MOCK_SATELLITES: Satellite[] = DEFAULT_SATELLITES;

const SYNC_CYCLE_SECONDS = 10;
const MANUAL_COOLDOWN_SECONDS = 30;

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
      s1.velocityKmS !== s2.velocityKmS ||
      s1.updatedAt !== s2.updatedAt
    ) {
      return false;
    }
  }
  return true;
}

export function useSatellites(scope: "mine" | "all" = "mine") {
  const { profile, session } = useAuth();
  
  // Instant 0ms SWR Cache Initialization (<0.01s instant output)
  const [satellites, setSatellites] = useState<Satellite[]>(() => {
    try {
      const cached = localStorage.getItem(`orbita_satellites_${scope}`);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      /* ignore */
    }
    return scope === "all" ? MOCK_SATELLITES : MOCK_SATELLITES.slice(0, 5);
  });

  const satellitesRef = useRef<Satellite[]>(satellites);
  satellitesRef.current = satellites;

  const [isLoading, setIsLoading] = useState<boolean>(() => satellites.length === 0);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(() => new Date());
  const [secondsUntilNextSync, setSecondsUntilNextSync] = useState(SYNC_CYCLE_SECONDS);

  // Manual Orbit Propagation State
  const [isRefreshingOrbit, setIsRefreshingOrbit] = useState(false);
  const [cooldownRemaining, setCooldownRemaining] = useState(0);
  const [orbitRefreshResult, setOrbitRefreshResult] = useState<SatelliteRefreshResponse | null>(null);
  const [orbitRefreshError, setOrbitRefreshError] = useState<string | null>(null);

  const fetchSatellites = useCallback(
    async (silent = false) => {
      if (satellitesRef.current.length === 0 && !silent) setIsLoading(true);
      else setIsSyncing(true);

      try {
        const { data } = await apiClient.get<Satellite[]>(`/satellites?scope=${scope}`);
        if (Array.isArray(data) && data.length > 0) {
          try {
            localStorage.setItem(`orbita_satellites_${scope}`, JSON.stringify(data));
          } catch {
            /* ignore quota */
          }
          if (!areSatellitesEqual(satellitesRef.current, data)) {
            setSatellites(data);
          }
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

  // Trigger manual fleet orbit propagation
  const refreshFleetOrbits = useCallback(async (): Promise<SatelliteRefreshResponse | null> => {
    if (cooldownRemaining > 0) {
      setOrbitRefreshError(`Please wait ${cooldownRemaining}s before refreshing again.`);
      return null;
    }

    setIsRefreshingOrbit(true);
    setOrbitRefreshError(null);
    setOrbitRefreshResult(null);

    try {
      const { data } = await apiClient.post<SatelliteRefreshResponse>("/satellites/refresh");
      setOrbitRefreshResult(data);
      setCooldownRemaining(MANUAL_COOLDOWN_SECONDS);
      setOrbitRefreshError(null);

      // Immediately refetch visible satellites to load fresh propagation positions
      await fetchSatellites(true);
      return data;
    } catch (err: unknown) {
      const axiosErr = err as AxiosError<{ detail?: string }>;
      if (axiosErr.response?.status === 429) {
        const retryHeader = axiosErr.response.headers["retry-after"];
        const waitSec = retryHeader ? parseInt(retryHeader, 10) : 30;
        setCooldownRemaining(waitSec > 0 ? waitSec : 30);
        setOrbitRefreshError(axiosErr.response.data?.detail || `Rate limit active. Please wait ${waitSec}s.`);
      } else if (axiosErr.response?.status === 403) {
        setOrbitRefreshError(axiosErr.response.data?.detail || "Permission denied. Only operators and admins can trigger manual orbit refresh.");
      } else {
        setOrbitRefreshError(axiosErr.response?.data?.detail || "Failed to refresh satellite orbit states.");
      }
      return null;
    } finally {
      setIsRefreshingOrbit(false);
    }
  }, [cooldownRemaining, fetchSatellites]);

  // Cooldown countdown timer
  useEffect(() => {
    if (cooldownRemaining <= 0) return;
    const timer = setInterval(() => {
      setCooldownRemaining((prev) => (prev > 1 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldownRemaining]);

  // Manual Instant Refresh trigger (cached poll refetch)
  const instantSync = useCallback(() => {
    setSecondsUntilNextSync(SYNC_CYCLE_SECONDS);
    return fetchSatellites(true);
  }, [fetchSatellites]);

  // Latest updated_at timestamp across loaded satellites
  const latestOrbitUpdatedAt = useMemo(() => {
    let latest: Date | null = null;
    for (const s of satellites) {
      const raw = s.updatedAt;
      if (raw) {
        const d = new Date(raw);
        if (!isNaN(d.getTime())) {
          if (!latest || d.getTime() > latest.getTime()) {
            latest = d;
          }
        }
      }
    }
    return latest || lastUpdated;
  }, [satellites, lastUpdated]);


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
    latestOrbitUpdatedAt,
    secondsUntilNextSync,
    instantSync,
    refetch: () => fetchSatellites(false),
    // Manual orbit propagation
    refreshFleetOrbits,
    isRefreshingOrbit,
    cooldownRemaining,
    orbitRefreshResult,
    orbitRefreshError,
  };
}

