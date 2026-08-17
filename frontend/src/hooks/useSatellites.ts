import { useEffect, useState } from "react";

import { apiClient } from "@/lib/apiClient";
import { MOCK_SATELLITES } from "@/mock/satellites";
import type { Satellite } from "@/types/satellite";

export function useSatellites() {
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const fetchSatellites = async () => {
      try {
        const { data } = await apiClient.get<Satellite[]>("/satellites");
        if (!cancelled) {
          setSatellites(data);
        }
      } catch (error) {
        console.warn("Failed to fetch satellites from API, falling back to mock data.", error);
        if (!cancelled) {
          setSatellites(MOCK_SATELLITES);
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

  return { satellites, isLoading };
}
