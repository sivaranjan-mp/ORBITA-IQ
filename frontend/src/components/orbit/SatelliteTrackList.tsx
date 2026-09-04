import { useState, useMemo } from "react";
import { Search, Radio, Filter, Eye, Activity } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { Satellite, SatelliteStatus } from "@/types/satellite";

export const SATELLITE_ORBIT_HEX: Record<string, string> = {
  "sat-25544": "#00F2FE", // ISS (Zarya) - Electric Cyan
  "sat-20580": "#38BDF8", // Hubble Space Telescope - Sky Blue
  "sat-44713": "#818CF8", // Starlink-3011 - Electric Indigo
  "sat-48274": "#10B981", // Tiangong (CSS) - Emerald Neon
  "sat-24876": "#FBBF24", // GPS BIIR-2 - Solar Amber Gold
  "sat-49260": "#2DD4BF", // Landsat 9 - Mint Turquoise
  "sat-46984": "#C084FC", // Sentinel-6 - Bright Violet
};

export function getSatelliteHexColor(sat: Satellite): string {
  if (sat.status === "active") {
    return SATELLITE_ORBIT_HEX[sat.id] || "#00F2FE";
  }
  if (sat.status === "degraded") return "#FB923C";
  if (sat.status === "inactive") return "#94A3B8";
  return "#EF4444"; // decayed / dead debris
}

const STATUS_META: Record<
  SatelliteStatus,
  { dot: string; badgeClass: string; label: string; tag: string }
> = {
  active: {
    dot: "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.9)]",
    badgeClass: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
    label: "ACTIVE",
    tag: "MOVING",
  },
  degraded: {
    dot: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]",
    badgeClass: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    label: "DEGRADED",
    tag: "WARN",
  },
  inactive: {
    dot: "bg-slate-400 shadow-[0_0_6px_rgba(148,163,184,0.5)]",
    badgeClass: "bg-slate-500/15 text-slate-300 border-slate-500/30",
    label: "INACTIVE",
    tag: "DERELICT",
  },
  decayed: {
    dot: "bg-rose-500 shadow-[0_0_9px_rgba(244,63,94,0.9)]",
    badgeClass: "bg-rose-500/15 text-rose-300 border-rose-500/40",
    label: "DEAD",
    tag: "DEBRIS",
  },
};

export function SatelliteTrackList({
  satellites,
  isLoading,
  focusedId,
  onFocus,
}: {
  satellites: Satellite[];
  isLoading: boolean;
  focusedId: string | null;
  onFocus: (id: string) => void;
}) {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Filter and sort active moving satellites FIRST!
  const filteredSatellites = useMemo(() => {
    const list = satellites.filter((sat) => {
      const matchesSearch =
        sat.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        sat.noradId.toString().includes(searchTerm) ||
        sat.ownerOrg.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesStatus =
        statusFilter === "all" || sat.status === statusFilter;

      return matchesSearch && matchesStatus;
    });

    const statusPriority: Record<SatelliteStatus, number> = {
      active: 1,    // Operational moving satellites shown FIRST
      degraded: 2,  // Degraded moving satellites second
      inactive: 3,  // Inactive derelict satellites third
      decayed: 4,   // Dead space debris satellites last
    };

    return list.sort((a, b) => {
      const pA = statusPriority[a.status] ?? 99;
      const pB = statusPriority[b.status] ?? 99;
      if (pA !== pB) return pA - pB;
      return a.name.localeCompare(b.name);
    });
  }, [satellites, searchTerm, statusFilter]);

  const statusCounts = useMemo(() => {
    return {
      all: satellites.length,
      active: satellites.filter((s) => s.status === "active").length,
      degraded: satellites.filter((s) => s.status === "degraded").length,
      inactive: satellites.filter((s) => s.status === "inactive").length,
      decayed: satellites.filter((s) => s.status === "decayed").length,
    };
  }, [satellites]);

  return (
    <Card className="flex h-full flex-col overflow-hidden border-border/80 bg-card/70 backdrop-blur-md">
      <CardHeader className="p-3 pb-2 space-y-2 border-b border-border/50">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xs font-semibold tracking-wider uppercase text-muted-foreground flex items-center gap-1.5">
            <Radio className="h-3.5 w-3.5 text-cyan-400 animate-pulse" />
            Tracked Fleet ({filteredSatellites.length}/{satellites.length})
          </CardTitle>
          {focusedId && (
            <button
              onClick={() => onFocus("")}
              className="text-[10px] text-amber-400 hover:text-amber-300 hover:underline font-mono"
            >
              Reset Focus
            </button>
          )}
        </div>

        {/* Search bar */}
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search name, NORAD, owner..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-md border border-border/60 bg-background/60 py-1.5 pl-8 pr-3 text-xs placeholder:text-muted-foreground focus:border-cyan-400 focus:outline-none focus:ring-1 focus:ring-cyan-400"
          />
        </div>

        {/* Distinct Status filter chips (Active Moving First, Degraded, Inactive, Dead/Debris) */}
        <div className="flex items-center gap-1 overflow-x-auto pb-0.5 scrollbar-none">
          <button
            onClick={() => setStatusFilter("all")}
            className={cn(
              "shrink-0 rounded px-2 py-0.5 text-[10px] font-medium transition-colors",
              statusFilter === "all"
                ? "bg-primary text-primary-foreground shadow-sm font-semibold"
                : "bg-secondary/60 text-muted-foreground hover:bg-secondary"
            )}
          >
            All ({statusCounts.all})
          </button>
          <button
            onClick={() => setStatusFilter("active")}
            className={cn(
              "shrink-0 flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium transition-colors",
              statusFilter === "active"
                ? "bg-emerald-500/25 text-emerald-300 border border-emerald-500/50 shadow-sm font-semibold"
                : "bg-secondary/60 text-muted-foreground hover:bg-secondary"
            )}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Active ({statusCounts.active})
          </button>
          {statusCounts.degraded > 0 && (
            <button
              onClick={() => setStatusFilter("degraded")}
              className={cn(
                "shrink-0 flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium transition-colors",
                statusFilter === "degraded"
                  ? "bg-amber-500/25 text-amber-300 border border-amber-500/50 shadow-sm font-semibold"
                  : "bg-secondary/60 text-muted-foreground hover:bg-secondary"
              )}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              Degraded ({statusCounts.degraded})
            </button>
          )}
          {statusCounts.inactive > 0 && (
            <button
              onClick={() => setStatusFilter("inactive")}
              className={cn(
                "shrink-0 flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium transition-colors",
                statusFilter === "inactive"
                  ? "bg-slate-500/25 text-slate-200 border border-slate-500/50 shadow-sm font-semibold"
                  : "bg-secondary/60 text-muted-foreground hover:bg-secondary"
              )}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
              Inactive ({statusCounts.inactive})
            </button>
          )}
          {statusCounts.decayed > 0 && (
            <button
              onClick={() => setStatusFilter("decayed")}
              className={cn(
                "shrink-0 flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium transition-colors",
                statusFilter === "decayed"
                  ? "bg-rose-500/25 text-rose-300 border border-rose-500/50 shadow-sm font-semibold"
                  : "bg-secondary/60 text-muted-foreground hover:bg-secondary"
              )}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
              Dead ({statusCounts.decayed})
            </button>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex-1 space-y-1.5 overflow-y-auto p-2">
        {isLoading &&
          Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-md" />
          ))}

        {!isLoading && filteredSatellites.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground">
            <Filter className="h-6 w-6 opacity-40 mb-1" />
            <p className="text-xs">No space objects match filter</p>
          </div>
        )}

        {!isLoading &&
          filteredSatellites.map((sat) => {
            const isFocused = focusedId === sat.id;
            const meta = STATUS_META[sat.status] || STATUS_META.active;
            const orbitHex = getSatelliteHexColor(sat);

            return (
              <button
                key={sat.id}
                onClick={() => onFocus(sat.id)}
                className={cn(
                  "group relative flex w-full flex-col rounded-md border p-2.5 text-left transition-all",
                  isFocused
                    ? "border-amber-400/80 bg-amber-500/15 shadow-[0_0_15px_rgba(255,230,0,0.2)]"
                    : sat.status === "active"
                    ? "border-border/50 bg-card/50 hover:border-cyan-500/40 hover:bg-secondary/40"
                    : sat.status === "degraded"
                    ? "border-amber-500/20 bg-amber-950/10 hover:border-amber-500/40 hover:bg-amber-950/20"
                    : sat.status === "inactive"
                    ? "border-slate-700/40 bg-slate-900/20 opacity-85 hover:opacity-100 hover:border-slate-600"
                    : "border-rose-900/30 bg-rose-950/15 opacity-80 hover:opacity-100 hover:border-rose-700/50"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    {isFocused ? (
                      <span className="relative flex h-2.5 w-2.5 shrink-0">
                        <span className="absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75 animate-ping" />
                        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#FFE600] shadow-[0_0_8px_rgba(255,230,0,0.9)]" />
                      </span>
                    ) : (
                      <span
                        className={cn(
                          "h-2 w-2 shrink-0 rounded-full transition-transform group-hover:scale-125",
                          meta.dot
                        )}
                      />
                    )}
                    <p
                      className={cn(
                        "truncate text-xs font-semibold leading-tight",
                        isFocused
                          ? "text-amber-200"
                          : sat.status === "active"
                          ? "text-foreground group-hover:text-cyan-200"
                          : sat.status === "decayed"
                          ? "text-rose-300/90"
                          : "text-muted-foreground group-hover:text-foreground"
                      )}
                    >
                      {sat.name}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {isFocused ? (
                      <span className="flex items-center gap-1 rounded bg-amber-400/20 px-1.5 py-0.5 text-[9px] font-mono font-bold text-amber-300 border border-amber-400/40 animate-pulse">
                        <Eye className="h-2.5 w-2.5 text-amber-300" />
                        TRACKING
                      </span>
                    ) : (
                      <span
                        className={cn(
                          "rounded border px-1.5 py-0.5 text-[8.5px] font-mono font-bold uppercase",
                          meta.badgeClass
                        )}
                      >
                        {sat.status === "active" ? (
                          <span className="flex items-center gap-1">
                            <Activity className="h-2.5 w-2.5 animate-pulse text-emerald-400" />
                            MOVING
                          </span>
                        ) : (
                          meta.label
                        )}
                      </span>
                    )}
                    <span className="shrink-0 font-mono text-[11px] font-medium text-muted-foreground">
                      {sat.altitudeKm != null ? `${Math.round(sat.altitudeKm)} km` : "N/A"}
                    </span>
                  </div>
                </div>

                <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                  <span className="flex items-center gap-1.5">
                    {/* Visual orbit ribbon color indicator */}
                    <span
                      title={`Orbit Path Color: ${orbitHex}`}
                      className="inline-block h-2 w-2 rounded-sm shrink-0 border border-white/20"
                      style={{ backgroundColor: orbitHex }}
                    />
                    <span>#{sat.noradId} • {sat.ownerOrg.slice(0, 14)}</span>
                  </span>
                  <span>
                    {sat.velocityKmS ? `${sat.velocityKmS.toFixed(1)} km/s` : "--"} •{" "}
                    {sat.periodMinutes ? `${sat.periodMinutes.toFixed(0)}m` : "--"}
                  </span>
                </div>
              </button>
            );
          })}
      </CardContent>
    </Card>
  );
}
