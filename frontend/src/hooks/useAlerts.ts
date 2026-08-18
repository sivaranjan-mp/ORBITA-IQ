import { useEffect, useState } from "react";

import { apiClient } from "@/lib/apiClient";
import type { ConjunctionAlert } from "@/types/alert";

export function useAlerts() {
  const [alerts, setAlerts] = useState<ConjunctionAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchAlerts = async () => {
      try {
        const { data } = await apiClient.get<ConjunctionAlert[]>("/alerts");
        if (!cancelled) {
          setAlerts(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to fetch alerts");
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

  return { alerts, isLoading, error };
}
