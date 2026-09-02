import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/apiClient";
import type { CatalogListResponse, CatalogSyncResponse } from "@/types/catalog";

interface UseCatalogOptions {
  search?: string;
  regime?: string;
  objectType?: string;
  page?: number;
  limit?: number;
}

export function useCatalog({
  search = "",
  regime = "ALL",
  objectType = "all",
  page = 1,
  limit = 25,
}: UseCatalogOptions = {}) {
  const [data, setData] = useState<CatalogListResponse>({
    items: [],
    total: 0,
    page: 1,
    limit: 25,
    totalPages: 1,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);

  const fetchCatalog = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (regime && regime !== "ALL") params.set("regime", regime);
      if (objectType && objectType !== "all") params.set("object_type", objectType);
      params.set("page", String(page));
      params.set("limit", String(limit));

      const res = await apiClient.get<CatalogListResponse>(`/catalog?${params.toString()}`);
      setData(res.data);
      setError(null);
    } catch (err) {
      console.error("Failed to load satellite catalog:", err);
      setError("Failed to load catalog data.");
    } finally {
      setIsLoading(false);
    }
  }, [search, regime, objectType, page, limit]);

  useEffect(() => {
    fetchCatalog();
  }, [fetchCatalog]);

  const trackSatellite = useCallback(async (noradId: number): Promise<boolean> => {
    try {
      await apiClient.post(`/catalog/track/${noradId}`);
      // Optimistically mark as tracked in local list
      setData((prev) => ({
        ...prev,
        items: prev.items.map((item) =>
          item.noradId === noradId ? { ...item, isTracked: true } : item
        ),
      }));
      return true;
    } catch (err) {
      console.error(`Failed to track satellite ${noradId}:`, err);
      throw err;
    }
  }, []);

  const syncCatalog = useCallback(async () => {
    setIsSyncing(true);
    setSyncStatus(null);
    try {
      const res = await apiClient.post<CatalogSyncResponse>("/catalog/sync");
      setSyncStatus(res.data.message || `Synced ${res.data.syncedCount} objects.`);
      await fetchCatalog();
    } catch (err) {
      console.error("Failed to synchronize catalog:", err);
      setSyncStatus("Synchronization failed. Check permissions or network.");
    } finally {
      setIsSyncing(false);
    }
  }, [fetchCatalog]);

  return {
    items: data.items,
    total: data.total,
    page: data.page,
    limit: data.limit,
    totalPages: data.totalPages,
    isLoading,
    error,
    isSyncing,
    syncStatus,
    refetch: fetchCatalog,
    trackSatellite,
    syncCatalog,
  };
}
