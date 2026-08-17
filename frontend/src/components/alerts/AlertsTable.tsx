import { useMemo, useState } from "react";

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
import { cn } from "@/lib/utils";
import type { ConjunctionAlert, RiskLevel } from "@/types/alert";

const RISK_FILTERS: Array<{ label: string; value: RiskLevel | "all" }> = [
  { label: "All risk", value: "all" },
  { label: "Critical", value: "critical" },
  { label: "High", value: "high" },
  { label: "Medium", value: "medium" },
  { label: "Low", value: "low" },
];

export function AlertsTable() {
  const { alerts, isLoading } = useAlerts();
  const [riskFilter, setRiskFilter] = useState<RiskLevel | "all">("all");
  const [selected, setSelected] = useState<ConjunctionAlert | null>(null);

  const filtered = useMemo(() => {
    const rows = riskFilter === "all" ? alerts : alerts.filter((a) => a.riskLevel === riskFilter);
    return [...rows].sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime());
  }, [alerts, riskFilter]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {RISK_FILTERS.map((f) => (
          <Button
            key={f.value}
            size="sm"
            variant={riskFilter === f.value ? "default" : "outline"}
            onClick={() => setRiskFilter(f.value)}
            className={cn(riskFilter !== f.value && "text-muted-foreground")}
          >
            {f.label}
          </Button>
        ))}
      </div>

      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Satellite A</TableHead>
              <TableHead>Satellite B</TableHead>
              <TableHead className="text-right">Miss Distance</TableHead>
              <TableHead className="text-right">Relative Velocity</TableHead>
              <TableHead>Risk</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={5}>
                    <Skeleton className="h-6 w-full" />
                  </TableCell>
                </TableRow>
              ))}

            {!isLoading && filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                  No conjunctions at this risk level.
                </TableCell>
              </TableRow>
            )}

            {!isLoading &&
              filtered.map((alert) => (
                <TableRow
                  key={alert.id}
                  className="cursor-pointer"
                  onClick={() => setSelected(alert)}
                >
                  <TableCell>
                    <p className="font-medium">{alert.primarySatellite}</p>
                    <p className="text-xs text-muted-foreground">{alert.primaryNoradId}</p>
                  </TableCell>
                  <TableCell>
                    <p className="font-medium">{alert.secondaryObject}</p>
                    <p className="text-xs text-muted-foreground">{alert.secondaryNoradId}</p>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {alert.missDistanceM.toLocaleString()} m
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {alert.relativeVelocityKmS?.toFixed(1)} km/s
                  </TableCell>
                  <TableCell>
                    <RiskBadge level={alert.riskLevel} />
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </div>

      <AlertDetailDialog alert={selected} onOpenChange={(open) => !open && setSelected(null)} />
    </div>
  );
}
