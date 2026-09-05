import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/apiClient";
import { supabase } from "@/lib/supabaseClient";
import type { AlertStatusHistoryItem, AlertStatusHistoryListResponse } from "@/types/alert";

export function useAlertHistory(initialPage: number = 1, limit: number = 10, alertId?: string) {
  const [history, setHistory] = useState<AlertStatusHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(initialPage);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async (currentPage: number = page, showLoading = false) => {
    if (showLoading) setIsLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(currentPage));
      params.set("limit", String(limit));
      if (alertId) {
        params.set("alert_id", alertId);
      }

      const { data } = await apiClient.get<AlertStatusHistoryListResponse>(`/alerts/history?${params.toString()}`);
      if (data && Array.isArray(data.items)) {
        setHistory(data.items);
        setTotal(data.total);
        setTotalPages(data.totalPages || Math.max(1, Math.ceil(data.total / limit)));
      } else {
        setHistory([]);
        setTotal(0);
        setTotalPages(1);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alert history");
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, [page, limit, alertId]);

  useEffect(() => {
    fetchHistory(page, true);
  }, [page, fetchHistory]);

  useEffect(() => {
    // 1. Polling fallback every 20 seconds
    const interval = setInterval(() => {
      fetchHistory(page, false);
    }, 20000);

    // 2. Supabase Realtime Subscription on alert_status_history
    let channel: ReturnType<typeof supabase.channel> | null = null;
    try {
      channel = supabase
        .channel("alert_status_history_realtime")
        .on(
          "postgres_changes",
          { event: "*", schema: "public", table: "alert_status_history" },
          () => {
            fetchHistory(page, false);
          }
        )
        .subscribe();
    } catch {
      // Realtime fallback to polling
    }

    return () => {
      clearInterval(interval);
      if (channel) {
        supabase.removeChannel(channel);
      }
    };
  }, [page, fetchHistory]);

  const nextPage = () => {
    if (page < totalPages) setPage((p) => p + 1);
  };

  const prevPage = () => {
    if (page > 1) setPage((p) => p - 1);
  };

  const goToPage = (p: number) => {
    if (p >= 1 && p <= totalPages) setPage(p);
  };

  return {
    history,
    total,
    page,
    limit,
    totalPages,
    isLoading,
    error,
    refetch: () => fetchHistory(page, true),
    setPage: goToPage,
    nextPage,
    prevPage,
  };
}
