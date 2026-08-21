import { useEffect, useState } from "react";
import { apiClient } from "@/lib/apiClient";
import type { RiskLevel } from "@/types/alert";

export interface ConjunctionEventResponse {
  id: string;
  primarySatelliteId: string;
  primarySatelliteName: string;
  primaryNoradId: number;
  secondarySatelliteId: string;
  secondarySatelliteName: string;
  secondaryNoradId: number;
  tca: string;
  missDistanceKm: number;
  relativeVelocityKmS: number;
  probability: number;
  riskLevel: RiskLevel;
  status: string;
  detectedBy: string;
  createdAt: string;
}

export function useConjunctions() {
  const [conjunctions, setConjunctions] = useState<ConjunctionEventResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConjunctions = async () => {
    setIsLoading(true);
    try {
      const { data } = await apiClient.get<ConjunctionEventResponse[]>("/conjunctions");
      setConjunctions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch conjunctions");
    } finally {
      setIsLoading(false);
    }
  };

  const triggerScreening = async () => {
    try {
      await apiClient.post("/conjunctions/screen");
      await fetchConjunctions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger screening");
    }
  };

  useEffect(() => {
    fetchConjunctions();
  }, []);

  return { conjunctions, isLoading, error, fetchConjunctions, triggerScreening };
}
