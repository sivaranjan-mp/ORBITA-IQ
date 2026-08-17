import { useEffect, useState } from "react";

import { apiClient } from "@/lib/apiClient";
import { MOCK_ALERTS } from "@/mock/alerts";
import type { ConjunctionAlert } from "@/types/alert";

export function useAlerts() {
  const [alerts, setAlerts] = useState<ConjunctionAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const fetchAlerts = async () => {
      try {
        const { data } = await apiClient.get<ConjunctionAlert[]>("/alerts");
        if (!cancelled) {
          setAlerts(data);
        }
      } catch (error) {
        console.warn("Failed to fetch alerts from API, falling back to mock data.", error);
        if (!cancelled) {
          setAlerts(MOCK_ALERTS);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchAlerts();

    return () => {
      cancelled = true;
    };
  }, []);

  return { alerts, isLoading };
}
