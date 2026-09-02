import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/apiClient";
import type { CatalogListResponse, CatalogSyncResponse, CatalogSyncStatus } from "@/types/catalog";

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
  const [syncStatus, setSyncStatus] = useState<CatalogSyncStatus | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

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

  // Status poller
  const checkSyncStatus = useCallback(async () => {
    try {
      const res = await apiClient.get<CatalogSyncStatus>("/catalog/sync/status");
      setSyncStatus(res.data);
      if (res.data.status === "completed") {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        fetchCatalog();
      } else if (res.data.status === "failed") {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      }
    } catch (err) {
      console.error("Failed to check sync status:", err);
    }
  }, [fetchCatalog]);

  // Clean up polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

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

  const syncCatalog = useCallback(async (force = false) => {
    try {
      const res = await apiClient.post<CatalogSyncResponse>(`/catalog/sync?force=${force}`);
      setSyncStatus({
        status: "running",
        processed: 0,
        total: 0,
        percent: 0,
        syncedCount: res.data.syncedCount,
        message: res.data.message,
      });

      // Start polling
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = setInterval(checkSyncStatus, 1500);
      // Run immediate status check
      checkSyncStatus();
    } catch (err: any) {
      console.error("Failed to synchronize catalog:", err);
      const msg = err.response?.data?.detail || "Synchronization trigger failed.";
      setSyncStatus({
        status: "failed",
        processed: 0,
        total: 0,
        percent: 0,
        syncedCount: 0,
        error: msg,
        message: msg,
      });
    }
  }, [checkSyncStatus]);

  const isSyncing = syncStatus?.status === "running";

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
