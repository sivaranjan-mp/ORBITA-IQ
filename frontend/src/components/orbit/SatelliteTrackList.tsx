import { useState, useMemo } from "react";
import { Search, Radio, Filter, Eye } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { Satellite, SatelliteStatus } from "@/types/satellite";

const STATUS_DOT: Record<SatelliteStatus, string> = {
  active: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]",
  degraded: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]",
  inactive: "bg-slate-400",
  decayed: "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.8)]",
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

  const filteredSatellites = useMemo(() => {
    return satellites.filter((sat) => {
      const matchesSearch =
        sat.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        sat.noradId.toString().includes(searchTerm) ||
        sat.ownerOrg.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesStatus =
        statusFilter === "all" || sat.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [satellites, searchTerm, statusFilter]);

  const statusCounts = useMemo(() => {
    return {
      all: satellites.length,
      active: satellites.filter((s) => s.status === "active").length,
      degraded: satellites.filter((s) => s.status === "degraded").length,
      inactive: satellites.filter((s) => s.status === "inactive" || s.status === "decayed").length,
    };
  }, [satellites]);

  return (
    <Card className="flex h-full flex-col overflow-hidden border-border/80 bg-card/70 backdrop-blur-md">
      <CardHeader className="p-3 pb-2 space-y-2 border-b border-border/50">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xs font-semibold tracking-wider uppercase text-muted-foreground flex items-center gap-1.5">
            <Radio className="h-3.5 w-3.5 text-primary animate-pulse" />
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
            placeholder="Search name, NORAD..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-md border border-border/60 bg-background/60 py-1.5 pl-8 pr-3 text-xs placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Status filter chips */}
        <div className="flex items-center gap-1 overflow-x-auto pb-0.5">
          <button
            onClick={() => setStatusFilter("all")}
            className={cn(
              "rounded px-2 py-0.5 text-[10px] font-medium transition-colors",
              statusFilter === "all"
                ? "bg-primary text-primary-foreground"
                : "bg-secondary/60 text-muted-foreground hover:bg-secondary"
            )}
          >
            All ({statusCounts.all})
          </button>
          <button
            onClick={() => setStatusFilter("active")}
            className={cn(
              "rounded px-2 py-0.5 text-[10px] font-medium transition-colors",
              statusFilter === "active"
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                : "bg-secondary/60 text-muted-foreground hover:bg-secondary"
            )}
          >
            Active ({statusCounts.active})
          </button>
          {statusCounts.degraded > 0 && (
            <button
              onClick={() => setStatusFilter("degraded")}
              className={cn(
                "rounded px-2 py-0.5 text-[10px] font-medium transition-colors",
                statusFilter === "degraded"
                  ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                  : "bg-secondary/60 text-muted-foreground hover:bg-secondary"
              )}
            >
              Degraded ({statusCounts.degraded})
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
            <p className="text-xs">No space objects found</p>
          </div>
        )}

        {!isLoading &&
          filteredSatellites.map((sat) => {
            const isFocused = focusedId === sat.id;
            return (
              <button
                key={sat.id}
                onClick={() => onFocus(sat.id)}
                className={cn(
                  "group relative flex w-full flex-col rounded-md border p-2.5 text-left transition-all",
                  isFocused
                    ? "border-amber-400/80 bg-amber-500/15 shadow-[0_0_15px_rgba(255,230,0,0.2)]"
                    : "border-border/40 bg-card/40 hover:border-border hover:bg-secondary/40"
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
                          STATUS_DOT[sat.status]
                        )}
                      />
                    )}
                    <p
                      className={cn(
                        "truncate text-xs font-semibold leading-tight",
                        isFocused ? "text-amber-200" : "text-foreground"
                      )}
                    >
                      {sat.name}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {isFocused && (
                      <span className="flex items-center gap-1 rounded bg-amber-400/20 px-1.5 py-0.5 text-[9px] font-mono font-bold text-amber-300 border border-amber-400/40 animate-pulse">
                        <Eye className="h-2.5 w-2.5 text-amber-300" />
                        TRACKING
                      </span>
                    )}
                    <span className="shrink-0 font-mono text-[11px] font-medium text-muted-foreground">
                      {sat.altitudeKm != null ? `${Math.round(sat.altitudeKm)} km` : "N/A"}
                    </span>
                  </div>
                </div>

                <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                  <span>#{sat.noradId} • {sat.ownerOrg.slice(0, 14)}</span>
                  <span>{sat.periodMinutes ? `${sat.periodMinutes.toFixed(0)}m` : "--"} • {sat.inclinationDeg ? `${sat.inclinationDeg.toFixed(0)}°` : "--"}</span>
                </div>
              </button>
            );
          })}
      </CardContent>
    </Card>
  );
}
