import { useEffect, useState } from "react";

import { apiClient } from "@/lib/apiClient";
import type { Satellite } from "@/types/satellite";

export function useSatellites() {
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchSatellites = async () => {
      try {
        const { data } = await apiClient.get<Satellite[]>("/satellites");
        if (!cancelled) {
          setSatellites(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to fetch satellites");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchSatellites();

    return () => {
      cancelled = true;
    };
  }, []);

  return { satellites, isLoading, error };
}
