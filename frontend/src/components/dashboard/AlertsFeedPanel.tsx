import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";

import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAlerts } from "@/hooks/useAlerts";
import { formatCountdown, formatTcaHorizon } from "@/lib/format";

export function AlertsFeedPanel() {
  const { alerts, isLoading } = useAlerts();
  const feed = [...alerts]
    .filter((a) => a.status === "open" || a.status === "monitoring" || a.status === "active")
    .sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime())
    .slice(0, 5);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Active Conjunction Feed (5-Day Horizon)
        </CardTitle>
        <Link
          to="/alerts"
          className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          View all ({alerts.length})
          <ArrowUpRight className="h-3 w-3" />
        </Link>
      </CardHeader>
      <CardContent className="space-y-1">
        {isLoading &&
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}

        {!isLoading && feed.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No active conjunctions.</p>
        )}

        {!isLoading &&
          feed.map((alert) => {
            const isFleetVsFleet = alert.screeningScope === "fleet_vs_fleet";
            const missKm = alert.missDistanceKm ?? (alert.missDistanceM / 1000.0);
            return (
              <div
                key={alert.id}
                className="flex items-center justify-between rounded-md px-2 py-2.5 hover:bg-secondary/40 transition-colors"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <p className="truncate text-sm font-medium text-foreground">
                      {alert.primarySatellite}{" "}
                      <span className="text-muted-foreground font-normal">vs</span>{" "}
                      {alert.secondaryObject}
                    </p>
                    <span className="text-[10px] text-muted-foreground font-mono">
                      ({isFleetVsFleet ? "Fleet" : "Catalog"})
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Miss distance: {missKm < 1.0 ? `${alert.missDistanceM.toFixed(0)} m` : `${missKm.toFixed(2)} km`} · {formatTcaHorizon(alert.tca)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="font-mono text-xs text-muted-foreground">
                    {formatCountdown(alert.tca)}
                  </span>
                  <RiskBadge level={alert.riskLevel} />
                </div>
              </div>
            );
          })}
      </CardContent>
    </Card>
  );
}
