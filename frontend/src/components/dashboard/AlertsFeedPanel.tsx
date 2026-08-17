import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";

import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAlerts } from "@/hooks/useAlerts";
import { formatCountdown } from "@/lib/format";

export function AlertsFeedPanel() {
  const { alerts, isLoading } = useAlerts();
  const feed = [...alerts]
    .filter((a) => a.status === "open" || a.status === "monitoring")
    .sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime())
    .slice(0, 5);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Active Conjunction Feed
        </CardTitle>
        <Link
          to="/alerts"
          className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          View all
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
          feed.map((alert) => (
            <div
              key={alert.id}
              className="flex items-center justify-between rounded-md px-2 py-2.5 hover:bg-secondary/40"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {alert.primarySatellite}{" "}
                  <span className="text-muted-foreground">vs</span> {alert.secondaryObject}
                </p>
                <p className="text-xs text-muted-foreground">
                  Miss distance {alert.missDistanceM.toLocaleString()} m
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <span className="font-mono text-xs text-muted-foreground">
                  {formatCountdown(alert.tca)}
                </span>
                <RiskBadge level={alert.riskLevel} />
              </div>
            </div>
          ))}
      </CardContent>
    </Card>
  );
}
