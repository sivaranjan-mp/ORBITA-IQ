import { useMemo, useState } from "react";
import { RefreshCw, ShieldAlert } from "lucide-react";

import { AlertDetailDialog } from "@/components/alerts/AlertDetailDialog";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { Button } from "@/components/ui/button";
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
import { formatDateTime, formatTcaHorizon } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ConjunctionAlert, RiskLevel, ScreeningScope } from "@/types/alert";

const RISK_FILTERS: Array<{ label: string; value: RiskLevel | "all" }> = [
  { label: "All risk", value: "all" },
  { label: "Critical (<1 km)", value: "critical" },
  { label: "High (1–5 km)", value: "high" },
  { label: "Medium (5–25 km)", value: "medium" },
  { label: "Low (25–50 km)", value: "low" },
];

const SCOPE_FILTERS: Array<{ label: string; value: ScreeningScope | "all" }> = [
  { label: "All Scopes", value: "all" },
  { label: "Fleet vs Fleet", value: "fleet_vs_fleet" },
  { label: "Fleet vs Catalog", value: "fleet_vs_catalog" },
];

export function AlertsTable() {
  const { alerts, isLoading, isScreening, triggerScreening, updateAlertStatus } = useAlerts();
  const [riskFilter, setRiskFilter] = useState<RiskLevel | "all">("all");
  const [scopeFilter, setScopeFilter] = useState<ScreeningScope | "all">("all");
  const [selected, setSelected] = useState<ConjunctionAlert | null>(null);

  const filtered = useMemo(() => {
    let rows = alerts;
    if (riskFilter !== "all") {
      rows = rows.filter((a) => a.riskLevel === riskFilter);
    }
    if (scopeFilter !== "all") {
      rows = rows.filter((a) => (a.screeningScope || "fleet_vs_catalog") === scopeFilter);
    }
    return [...rows].sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime());
  }, [alerts, riskFilter, scopeFilter]);

  return (
    <div className="space-y-4">
      {/* Top Filter and Action Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {/* Risk Filters */}
          <div className="flex flex-wrap gap-1.5">
            {RISK_FILTERS.map((f) => (
              <Button
                key={f.value}
                size="sm"
                variant={riskFilter === f.value ? "default" : "outline"}
                onClick={() => setRiskFilter(f.value)}
                className={cn(
                  "h-8 text-xs font-medium",
                  riskFilter !== f.value && "text-muted-foreground hover:text-foreground"
                )}
              >
                {f.label}
              </Button>
            ))}
          </div>

          <div className="hidden h-5 w-px bg-border sm:block" />

          {/* Scope Filters */}
          <div className="flex rounded-md border border-border bg-card p-0.5 text-xs">
            {SCOPE_FILTERS.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => setScopeFilter(s.value)}
                className={cn(
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  scopeFilter === s.value
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Screening Trigger Button */}
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => triggerScreening()}
            disabled={isScreening}
            className="h-8 gap-1.5 text-xs font-medium"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isScreening && "animate-spin text-primary")} />
            {isScreening ? "Screening 5-Day Window…" : "Run Screening"}
          </Button>
        </div>
      </div>

      {/* Main Table */}
      <div className="rounded-lg border border-border bg-card/50 overflow-hidden shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Satellite A</TableHead>
              <TableHead>Satellite B</TableHead>
              <TableHead>Scope</TableHead>
              <TableHead>TCA (UTC)</TableHead>
              <TableHead className="text-right">Miss Distance</TableHead>
              <TableHead className="text-right">Relative Velocity</TableHead>
              <TableHead>Risk</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={7}>
                    <Skeleton className="h-7 w-full" />
                  </TableCell>
                </TableRow>
              ))}

            {!isLoading && filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-12 text-center text-muted-foreground">
                  <div className="mx-auto flex max-w-sm flex-col items-center justify-center space-y-2">
                    <ShieldAlert className="h-8 w-8 text-muted-foreground/60" />
                    <p className="text-sm font-medium text-foreground">No conjunctions detected</p>
                    <p className="text-xs text-muted-foreground">
                      No close approaches matching the selected filter within the 5-day screening horizon.
                    </p>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {!isLoading &&
              filtered.map((alert) => {
                const isFleetVsFleet = alert.screeningScope === "fleet_vs_fleet";
                const missKm = alert.missDistanceKm ?? (alert.missDistanceM / 1000.0);
                const horizonBadge = formatTcaHorizon(alert.tca);

                return (
                  <TableRow
                    key={alert.id}
                    className="cursor-pointer transition-colors hover:bg-muted/50"
                    onClick={() => setSelected(alert)}
                  >
                    <TableCell>
                      <p className="font-medium text-foreground">{alert.primarySatellite}</p>
                      <p className="font-mono text-xs text-muted-foreground">NORAD #{alert.primaryNoradId}</p>
                    </TableCell>
                    <TableCell>
                      <p className="font-medium text-foreground">{alert.secondaryObject}</p>
                      <p className="font-mono text-xs text-muted-foreground">NORAD #{alert.secondaryNoradId}</p>
                    </TableCell>
                    <TableCell>
                      <span
                        className={cn(
                          "inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium font-mono",
                          isFleetVsFleet
                            ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                            : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                        )}
                      >
                        {isFleetVsFleet ? "Fleet vs Fleet" : "Fleet vs Catalog"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-foreground font-medium">{formatDateTime(alert.tca)}</span>
                        <span className="rounded bg-secondary/80 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                          {horizonBadge}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      <span className="font-semibold text-foreground">{missKm < 1.0 ? `${alert.missDistanceM.toFixed(0)} m` : `${missKm.toFixed(2)} km`}</span>
                      {missKm >= 1.0 && (
                        <p className="text-[10px] text-muted-foreground">({alert.missDistanceM.toLocaleString()} m)</p>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs text-muted-foreground">
                      {alert.relativeVelocityKmS != null ? `${alert.relativeVelocityKmS.toFixed(2)} km/s` : "—"}
                    </TableCell>
                    <TableCell>
                      <RiskBadge level={alert.riskLevel} />
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
      </div>

      <AlertDetailDialog
        alert={selected}
        onOpenChange={(open) => !open && setSelected(null)}
        onStatusUpdate={async (alertId, status) => {
          await updateAlertStatus(alertId, status);
          if (selected && selected.id === alertId) {
            setSelected({ ...selected, status });
          }
        }}
      />
    </div>
  );
}
