import { useMemo, useState } from "react";
import { AlertTriangle, ArrowUpDown, Search } from "lucide-react";

import { SatelliteStatusBadge } from "@/components/satellites/SatelliteStatusBadge";
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
import { useSatellites } from "@/hooks/useSatellites";
import { formatCollisionDate, formatTcaHorizon } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ConjunctionAlert } from "@/types/alert";

interface SatelliteTableProps {
  showOwner?: boolean;
  scope?: "mine" | "all";
  highlightOwned?: boolean;
}

export function SatelliteTable({
  showOwner = false,
  scope = "mine",
  highlightOwned = scope === "all",
}: SatelliteTableProps = {}) {
  const { profile, session } = useAuth();
  const { satellites, isLoading } = useSatellites(scope);
  const { alerts } = useAlerts();
  const [query, setQuery] = useState("");
  const [riskOnly, setRiskOnly] = useState(false);
  const [sortBy, setSortBy] = useState<"collision" | "name" | "norad" | "altitude">("collision");

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

  const atRiskCount = useMemo(() => {
    return satellites.filter((s) => collisionMap.has(s.noradId)).length;
  }, [satellites, collisionMap]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = satellites;

    if (q) {
      rows = rows.filter(
        (sat) =>
          sat.name.toLowerCase().includes(q) ||
          String(sat.noradId).includes(q) ||
          (sat.ownerName && sat.ownerName.toLowerCase().includes(q)) ||
          (sat.ownerEmployeeId && sat.ownerEmployeeId.toLowerCase().includes(q)) ||
          (sat.ownerOrg && sat.ownerOrg.toLowerCase().includes(q))
      );
    }

    if (riskOnly) {
      rows = rows.filter((sat) => collisionMap.has(sat.noradId));
    }

    return [...rows].sort((a, b) => {
      const colA = collisionMap.get(a.noradId);
      const colB = collisionMap.get(b.noradId);

      if (sortBy === "collision") {
        if (colA && colB) {
          return new Date(colA.tca).getTime() - new Date(colB.tca).getTime();
        }
        if (colA) return -1;
        if (colB) return 1;
        return (a.name || "").localeCompare(b.name || "");
      }

      if (sortBy === "name") {
        return (a.name || "").localeCompare(b.name || "");
      }

      if (sortBy === "norad") {
        return a.noradId - b.noradId;
      }

      if (sortBy === "altitude") {
        return (b.altitudeKm ?? 0) - (a.altitudeKm ?? 0);
      }

      return 0;
    });
  }, [satellites, query, riskOnly, sortBy, collisionMap]);

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {/* Search box */}
          <div className="relative min-w-[220px] max-w-xs flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name or NORAD ID…"
              className="pl-9 h-8 text-xs"
            />
          </div>

          {/* Filter Pills */}
          <div className="flex items-center rounded-md border border-border bg-card p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setRiskOnly(false)}
              className={cn(
                "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                !riskOnly
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              All ({satellites.length})
            </button>
            <button
              type="button"
              onClick={() => setRiskOnly(true)}
              className={cn(
                "rounded px-2.5 py-1 text-xs font-medium transition-colors flex items-center gap-1",
                riskOnly
                  ? "bg-amber-500 text-amber-950 font-semibold shadow-sm"
                  : "text-amber-400 hover:text-amber-300"
              )}
            >
              <AlertTriangle className="h-3 w-3" />
              At Collision Risk ({atRiskCount})
            </button>
          </div>
        </div>

        {/* Sort Controls */}
        <div className="flex items-center gap-1.5 text-xs">
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-muted-foreground font-medium">Sort:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as "collision" | "name" | "norad" | "altitude")}
            className="rounded border border-border bg-card px-2 py-1 text-xs font-medium text-foreground outline-none cursor-pointer"
          >
            <option value="collision">Collision Risk (Earliest First)</option>
            <option value="name">Name (A–Z)</option>
            <option value="norad">NORAD ID</option>
            <option value="altitude">Altitude (High to Low)</option>
          </select>
        </div>
      </div>

      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Satellite</TableHead>
              <TableHead>NORAD ID</TableHead>
              {showOwner && <TableHead>Owner</TableHead>}
              <TableHead className="text-right">Altitude</TableHead>
              <TableHead className="text-right">Latitude</TableHead>
              <TableHead className="text-right">Longitude</TableHead>
              <TableHead className="text-right">Velocity</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading &&
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={showOwner ? 8 : 7}>
                    <Skeleton className="h-6 w-full" />
                  </TableCell>
                </TableRow>
              ))}

            {!isLoading && filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={showOwner ? 8 : 7} className="py-10 text-center text-muted-foreground">
                  No satellites match "{query}".
                </TableCell>
              </TableRow>
            )}

            {!isLoading &&
              filtered.map((sat) => {
                const currentEmployeeId = (
                  profile?.employee_id ||
                  (session?.user?.user_metadata?.employee_id as string | undefined)
                )?.trim().toLowerCase();

                const currentUserId = (
                  profile?.id ||
                  session?.user?.id
                )?.trim().toLowerCase();

                const currentUserEmail = (
                  session?.user?.email
                )?.trim().toLowerCase();

                const satOwner = (sat.ownerEmployeeId || sat.ownerOrg)?.trim().toLowerCase();

                const isOwner = Boolean(
                  highlightOwned &&
                  satOwner &&
                  satOwner !== "unknown" &&
                  (
                    (currentEmployeeId && satOwner === currentEmployeeId) ||
                    (currentUserId && satOwner === currentUserId) ||
                    (currentUserEmail && satOwner === currentUserEmail)
                  )
                );

                const primaryOwner = sat.ownerName || sat.ownerEmployeeId || sat.ownerOrg || "Unknown";
                const secondaryOwner =
                  (sat.ownerEmployeeId || sat.ownerOrg) && (sat.ownerEmployeeId || sat.ownerOrg) !== primaryOwner
                    ? (sat.ownerEmployeeId || sat.ownerOrg)
                    : null;

                const collision = collisionMap.get(sat.noradId);
                const opponentName = collision
                  ? collision.primaryNoradId === sat.noradId
                    ? collision.secondaryObject
                    : collision.primarySatellite
                  : null;

                return (
                  <TableRow
                    key={sat.id}
                    className={cn(
                      isOwner && "bg-amber-950/40 hover:bg-amber-950/60 text-amber-100 border-amber-900/40",
                      collision && !isOwner && "bg-amber-500/5 hover:bg-amber-500/10 border-l-2 border-l-amber-500"
                    )}
                  >
                    <TableCell>
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1.5">
                          <p className={cn("font-medium", isOwner ? "text-amber-100" : "text-foreground")}>
                            {sat.name || "Unknown"}
                          </p>
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
                        ) : (
                          <p className={cn("text-xs", isOwner ? "text-amber-200/70" : "text-muted-foreground")}>
                            {sat.internationalDesignator}
                          </p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className={cn("font-mono text-xs", isOwner ? "text-amber-100" : "text-foreground")}>
                      {sat.noradId}
                    </TableCell>
                    {showOwner && (
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <p className={cn("font-medium text-xs", isOwner ? "text-amber-100" : "text-foreground")}>
                            {primaryOwner}
                          </p>
                          {isOwner && (
                            <span className="inline-block rounded bg-amber-500/20 px-1 py-0.5 text-[10px] font-semibold text-amber-300">
                              You
                            </span>
                          )}
                        </div>
                        {secondaryOwner && (
                          <p className={cn("font-mono text-[11px]", isOwner ? "text-amber-200/70" : "text-muted-foreground")}>
                            {secondaryOwner}
                          </p>
                        )}
                      </TableCell>
                    )}
                    <TableCell className={cn("text-right font-mono text-xs", isOwner ? "text-amber-100" : "text-foreground")}>
                      {sat.altitudeKm != null ? `${sat.altitudeKm.toLocaleString()} km` : "N/A"}
                    </TableCell>
                    <TableCell className={cn("text-right font-mono text-xs", isOwner ? "text-amber-100" : "text-foreground")}>
                      {sat.latitudeDeg != null ? `${sat.latitudeDeg.toFixed(2)}°` : "N/A"}
                    </TableCell>
                    <TableCell className={cn("text-right font-mono text-xs", isOwner ? "text-amber-100" : "text-foreground")}>
                      {sat.longitudeDeg != null ? `${sat.longitudeDeg.toFixed(2)}°` : "N/A"}
                    </TableCell>
                    <TableCell className={cn("text-right font-mono text-xs", isOwner ? "text-amber-100" : "text-foreground")}>
                      {sat.velocityKmS != null ? `${sat.velocityKmS.toFixed(2)} km/s` : "N/A"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col items-start gap-1">
                        <SatelliteStatusBadge status={sat.status} />
                        {collision && (
                          <span className="text-[10px] font-mono text-muted-foreground">
                            Miss: {(collision.missDistanceKm ?? collision.missDistanceM / 1000).toFixed(1)} km
                          </span>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
