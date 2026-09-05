import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, CheckCircle2, ChevronLeft, ChevronRight, Globe2, Loader2, RefreshCw, Search, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAlerts } from "@/hooks/useAlerts";
import { useAuth } from "@/hooks/useAuth";
import { useCatalog } from "@/hooks/useCatalog";
import { formatCollisionDate, formatTcaHorizon } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ConjunctionAlert } from "@/types/alert";

const REGIMES = ["ALL", "LEO", "MEO", "GEO", "HEO"] as const;
const OBJECT_TYPES = [
  { value: "all", label: "All Objects" },
  { value: "conjunction_risk", label: "⚠️ Conjunction Risk" },
  { value: "payload", label: "Payloads" },
  { value: "debris", label: "Debris" },
  { value: "rocket_body", label: "Rocket Bodies" },
] as const;

export function CatalogTable() {
  const { profile } = useAuth();
  const { alerts } = useAlerts();
  const isOperatorOrAdmin = profile?.role === "admin" || profile?.role === "operator";

  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [regime, setRegime] = useState<string>("ALL");
  const [objectType, setObjectType] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(25);
  const [trackingId, setTrackingId] = useState<number | null>(null);

  // Map each satellite NORAD ID to its earliest upcoming conjunction alert
  const collisionMap = useMemo(() => {
    const map = new Map<number, ConjunctionAlert>();
    const sortedAlerts = [...alerts].sort(
      (a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime()
    );
    for (const alert of sortedAlerts) {
      if (!map.has(alert.primaryNoradId)) {
        map.set(alert.primaryNoradId, alert);
      }
      if (!map.has(alert.secondaryNoradId)) {
        map.set(alert.secondaryNoradId, alert);
      }
    }
    return map;
  }, [alerts]);

  // Debounce search input by 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput);
      setPage(1); // Reset to page 1 on search change
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const {
    items: rawItems,
    total,
    totalPages,
    isLoading,
    isSyncing,
    syncStatus,
    trackSatellite,
    syncCatalog,
  } = useCatalog({
    search: debouncedSearch,
    regime,
    objectType: objectType === "conjunction_risk" ? "all" : objectType,
    page,
    limit,
  });

  // Sort satellites with upcoming collisions to the top
  const items = useMemo(() => {
    let list = [...rawItems];

    if (objectType === "conjunction_risk") {
      list = list.filter((sat) => collisionMap.has(sat.noradId));
    }

    return list.sort((a, b) => {
      const colA = collisionMap.get(a.noradId);
      const colB = collisionMap.get(b.noradId);

      if (colA && colB) {
        return new Date(colA.tca).getTime() - new Date(colB.tca).getTime();
      }
      if (colA) return -1;
      if (colB) return 1;
      return a.name.localeCompare(b.name);
    });
  }, [rawItems, objectType, collisionMap]);

  const handleTrack = async (noradId: number) => {
    setTrackingId(noradId);
    try {
      await trackSatellite(noradId);
    } catch {
      alert(`Failed to track satellite ${noradId}. Please try again.`);
    } finally {
      setTrackingId(null);
    }
  };

  const getRegimeColor = (reg: string) => {
    switch (reg) {
      case "LEO":
        return "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";
      case "MEO":
        return "bg-amber-500/15 text-amber-400 border-amber-500/30";
      case "GEO":
        return "bg-purple-500/15 text-purple-400 border-purple-500/30";
      case "HEO":
        return "bg-rose-500/15 text-rose-400 border-rose-500/30";
      default:
        return "bg-secondary text-secondary-foreground border-border";
    }
  };

  const getTypeBadge = (type: string) => {
    switch (type) {
      case "payload":
        return <Badge variant="outline" className="text-[11px]">Payload</Badge>;
      case "debris":
        return <Badge variant="destructive" className="text-[11px]">Debris</Badge>;
      case "rocket_body":
        return <Badge variant="warning" className="text-[11px]">Rocket Body</Badge>;
      default:
        return <Badge variant="outline" className="text-[11px]">Object</Badge>;
    }
  };

  const startIdx = total > 0 ? (page - 1) * limit + 1 : 0;
  const endIdx = Math.min(page * limit, total);

  return (
    <div className="space-y-4">
      {/* Top Filter and Controls Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 flex-wrap items-center gap-3">
          {/* Search Box */}
          <div className="relative min-w-[240px] max-w-sm flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by name, NORAD ID, or COSPAR ID…"
              className="pl-9"
            />
          </div>

          {/* Regime Pills */}
          <div className="flex items-center rounded-lg border border-border bg-card p-1 text-xs">
            {REGIMES.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => {
                  setRegime(r);
                  setPage(1);
                }}
                className={cn(
                  "rounded-md px-2.5 py-1 font-medium transition-colors",
                  regime === r
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {r}
              </button>
            ))}
          </div>

          {/* Object Type Filter */}
          <div className="flex items-center rounded-lg border border-border bg-card p-1 text-xs">
            {OBJECT_TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => {
                  setObjectType(t.value);
                  setPage(1);
                }}
                className={cn(
                  "rounded-md px-2.5 py-1 font-medium transition-colors",
                  objectType === t.value
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sync Button */}
        {isOperatorOrAdmin && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => syncCatalog(false)}
              disabled={isSyncing}
              className="shrink-0"
            >
              <RefreshCw className={cn("mr-2 h-3.5 w-3.5", isSyncing && "animate-spin")} />
              {isSyncing ? "Syncing CelesTrak…" : "Sync Catalog"}
            </Button>
          </div>
        )}
      </div>

      {/* Sync Status Banner */}
      {syncStatus && syncStatus.status === "running" && (
        <div className="rounded-lg border border-primary/30 bg-primary/10 p-4 space-y-2.5">
          <div className="flex items-center justify-between text-xs font-medium text-primary">
            <span className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              {syncStatus.message || "Downloading and indexing active space objects from CelesTrak..."}
            </span>
            <span>
              {syncStatus.processed > 0 && syncStatus.total > 0
                ? `${syncStatus.processed.toLocaleString()} / ${syncStatus.total.toLocaleString()} (${syncStatus.percent}%)`
                : `${syncStatus.percent}%`}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-primary/20">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${Math.max(5, syncStatus.percent)}%` }}
            />
          </div>
        </div>
      )}

      {syncStatus && syncStatus.status === "completed" && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-xs text-emerald-400">
          <span className="flex items-center gap-2 font-medium">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            {syncStatus.message || `Sync completed: ${syncStatus.syncedCount.toLocaleString()} space objects updated.`}
          </span>
          <span className="text-[11px] opacity-75">Refreshed</span>
        </div>
      )}

      {syncStatus && syncStatus.status === "failed" && (
        <div className="flex items-center justify-between rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-xs text-destructive">
          <span className="flex items-center gap-2 font-medium">
            <XCircle className="h-4 w-4 text-destructive" />
            {syncStatus.error || syncStatus.message || "Catalog synchronization encountered an error."}
          </span>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 text-[11px] text-destructive hover:bg-destructive/20"
            onClick={() => syncCatalog(true)}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Catalog Table */}
      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-14 text-center">S.No</TableHead>
              <TableHead>Space Object</TableHead>
              <TableHead>NORAD ID</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Regime</TableHead>
              <TableHead className="text-right">Perigee</TableHead>
              <TableHead className="text-right">Apogee</TableHead>
              <TableHead className="text-right">Inclination</TableHead>
              <TableHead className="text-right">Period</TableHead>
              <TableHead className="text-center">Fleet Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading &&
              Array.from({ length: 8 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={10}>
                    <Skeleton className="h-7 w-full" />
                  </TableCell>
                </TableRow>
              ))}

            {!isLoading && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={10} className="py-12 text-center text-muted-foreground">
                  <Globe2 className="mx-auto mb-2 h-8 w-8 text-muted-foreground/50" />
                  <p className="font-medium text-foreground">No catalog objects found</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Try adjusting your search filters or click "Sync Catalog" to fetch latest CelesTrak elements.
                  </p>
                </TableCell>
              </TableRow>
            )}

            {!isLoading &&
              items.map((sat, index) => {
                const serialNumber = (page - 1) * limit + index + 1;
                const isCurrentlyTracking = trackingId === sat.noradId;
                const collision = collisionMap.get(sat.noradId);
                const opponentName = collision
                  ? collision.primaryNoradId === sat.noradId
                    ? collision.secondaryObject
                    : collision.primarySatellite
                  : null;

                return (
                  <TableRow
                    key={sat.noradId}
                    className={cn(
                      "hover:bg-muted/40",
                      collision && "bg-amber-500/5 hover:bg-amber-500/10 border-l-2 border-l-amber-500"
                    )}
                  >
                    {/* Serial Number */}
                    <TableCell className="text-center font-mono text-xs text-muted-foreground">
                      {serialNumber}
                    </TableCell>

                    {/* Object Name & COSPAR / Collision Alert */}
                    <TableCell>
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1.5">
                          <p className="font-medium text-foreground">{sat.name}</p>
                          {collision && (
                            <span
                              className={cn(
                                "inline-flex items-center gap-1 rounded px-1.5 py-0.2 text-[10px] font-mono font-medium",
                                collision.riskLevel === "critical"
                                  ? "bg-red-500/15 text-red-400 border border-red-500/30"
                                  : collision.riskLevel === "high"
                                  ? "bg-orange-500/15 text-orange-400 border border-orange-500/30"
                                  : collision.riskLevel === "medium"
                                  ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                                  : "bg-blue-500/15 text-blue-400 border border-blue-500/30"
                              )}
                            >
                              <AlertTriangle className="h-2.5 w-2.5" />
                              {collision.riskLevel.toUpperCase()}
                            </span>
                          )}
                        </div>

                        {collision ? (
                          <p className="font-mono text-[11px] text-amber-400/90 font-medium">
                            ⚠️ Collision: {formatCollisionDate(collision.tca)} ({formatTcaHorizon(collision.tca)}) vs {opponentName}
                          </p>
                        ) : sat.internationalDesignator ? (
                          <p className="font-mono text-xs text-muted-foreground">
                            {sat.internationalDesignator}
                          </p>
                        ) : null}
                      </div>
                    </TableCell>

                    {/* NORAD ID */}
                    <TableCell className="font-mono text-xs text-foreground">
                      {sat.noradId}
                    </TableCell>

                    {/* Object Type */}
                    <TableCell>{getTypeBadge(sat.objectType)}</TableCell>

                    {/* Regime */}
                    <TableCell>
                      <span
                        className={cn(
                          "inline-block rounded border px-2 py-0.5 font-mono text-[11px] font-semibold",
                          getRegimeColor(sat.orbitRegime)
                        )}
                      >
                        {sat.orbitRegime}
                      </span>
                    </TableCell>

                    {/* Perigee */}
                    <TableCell className="text-right font-mono text-xs text-foreground">
                      {sat.perigeeKm != null ? `${sat.perigeeKm.toLocaleString()} km` : "N/A"}
                    </TableCell>

                    {/* Apogee */}
                    <TableCell className="text-right font-mono text-xs text-foreground">
                      {sat.apogeeKm != null ? `${sat.apogeeKm.toLocaleString()} km` : "N/A"}
                    </TableCell>

                    {/* Inclination */}
                    <TableCell className="text-right font-mono text-xs text-foreground">
                      {sat.inclinationDeg != null ? `${sat.inclinationDeg.toFixed(1)}°` : "N/A"}
                    </TableCell>

                    {/* Period */}
                    <TableCell className="text-right font-mono text-xs text-foreground">
                      {sat.periodMinutes != null ? `${sat.periodMinutes.toFixed(1)} min` : "N/A"}
                    </TableCell>

                    {/* Action */}
                    <TableCell className="text-center">
                      {sat.isTracked ? (
                        <span className="inline-flex items-center gap-1 rounded bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-400">
                          <Check className="h-3 w-3" />
                          In Fleet
                        </span>
                      ) : (
                        <Button
                          size="sm"
                          variant="secondary"
                          className="h-7 text-xs font-medium"
                          disabled={isCurrentlyTracking}
                          onClick={() => handleTrack(sat.noradId)}
                        >
                          {isCurrentlyTracking ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            "+ Track"
                          )}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Footer */}
      <div className="flex flex-col items-center justify-between gap-3 text-xs text-muted-foreground sm:flex-row">
        <div>
          Showing <span className="font-medium text-foreground">{startIdx}</span> to{" "}
          <span className="font-medium text-foreground">{endIdx}</span> of{" "}
          <span className="font-medium text-foreground">{total.toLocaleString()}</span> space objects
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span>Rows:</span>
            <select
              value={limit}
              onChange={(e) => {
                setLimit(Number(e.target.value));
                setPage(1);
              }}
              className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span className="sr-only">Previous</span>
            </Button>
            <span className="px-2 font-medium text-foreground">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              disabled={page >= totalPages || isLoading}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              <ChevronRight className="h-3.5 w-3.5" />
              <span className="sr-only">Next</span>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
