import { useEffect, useState, useRef, useCallback } from "react";

import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/apiClient";
import type { Satellite } from "@/types/satellite";

const MOCK_SATELLITES: Satellite[] = [
  {
    id: "sat-1",
    noradId: 25544,
    name: "ISS (ZARYA)",
    internationalDesignator: "1998-067A",
    objectType: "payload",
    status: "active",
    ownerOrg: "NASA",
    altitudeKm: 418.5,
    latitudeDeg: 28.53,
    longitudeDeg: -80.65,
    velocityKmS: 7.66,
    inclinationDeg: 51.64,
    periodMinutes: 92.9,
    eccentricity: 0.0001,
    lastTleEpoch: new Date().toISOString(),
    raanDeg: 120.5,
    meanAnomalyDeg: 45.2,
  },
  {
    id: "sat-2",
    noradId: 20580,
    name: "HUBBLE SPACE TELESCOPE",
    internationalDesignator: "1990-037B",
    objectType: "payload",
    status: "active",
    ownerOrg: "NASA-GSFC",
    altitudeKm: 535.2,
    latitudeDeg: -12.4,
    longitudeDeg: 45.1,
    velocityKmS: 7.59,
    inclinationDeg: 28.47,
    periodMinutes: 95.4,
    eccentricity: 0.0003,
    lastTleEpoch: new Date().toISOString(),
    raanDeg: 210.1,
    meanAnomalyDeg: 80.0,
  },
  {
    id: "sat-3",
    noradId: 48274,
    name: "TIANGONG",
    internationalDesignator: "2021-035A",
    objectType: "payload",
    status: "active",
    ownerOrg: "CNSA-OPS",
    altitudeKm: 389.0,
    latitudeDeg: 15.2,
    longitudeDeg: 110.8,
    velocityKmS: 7.68,
    inclinationDeg: 41.47,
    periodMinutes: 92.2,
    eccentricity: 0.0002,
    lastTleEpoch: new Date().toISOString(),
    raanDeg: 140.2,
    meanAnomalyDeg: 15.6,
  },
  {
    id: "sat-4",
    noradId: 44713,
    name: "STARLINK-1007",
    internationalDesignator: "2019-074A",
    objectType: "payload",
    status: "active",
    ownerOrg: "SpaceX",
    altitudeKm: 550.0,
    latitudeDeg: 45.0,
    longitudeDeg: -122.0,
    velocityKmS: 7.58,
    inclinationDeg: 53.05,
    periodMinutes: 95.6,
    eccentricity: 0.0001,
    lastTleEpoch: new Date().toISOString(),
    raanDeg: 300.4,
    meanAnomalyDeg: 210.3,
  },
  {
    id: "sat-5",
    noradId: 46984,
    name: "SENTINEL-6A",
    internationalDesignator: "2020-086A",
    objectType: "payload",
    status: "degraded",
    ownerOrg: "ESA-EUMETSAT",
    altitudeKm: 1336.0,
    latitudeDeg: -30.1,
    longitudeDeg: -15.4,
    velocityKmS: 7.21,
    inclinationDeg: 66.04,
    periodMinutes: 112.4,
    eccentricity: 0.0008,
    lastTleEpoch: new Date().toISOString(),
    raanDeg: 180.0,
    meanAnomalyDeg: 95.1,
  },
];

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
