import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSatellites } from "@/hooks/useSatellites";
import { cn } from "@/lib/utils";

const STATUS_DOT: Record<string, string> = {
  active: "bg-emerald-400",
  degraded: "bg-amber-400",
  inactive: "bg-muted-foreground",
  decayed: "bg-destructive",
};

export function SatelliteQuickList() {
  const { satellites, isLoading } = useSatellites();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">Tracked Fleet</CardTitle>
        <Link
          to="/satellites"
          className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          View all
          <ArrowUpRight className="h-3 w-3" />
        </Link>
      </CardHeader>
      <CardContent className="space-y-1">
        {isLoading &&
          Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}

        {!isLoading &&
          satellites.slice(0, 6).map((sat) => (
            <div
              key={sat.id}
              className="flex items-center justify-between rounded-md px-2 py-2 hover:bg-secondary/40"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATUS_DOT[sat.status])} />
                <span className="truncate text-sm font-medium">{sat.name}</span>
              </div>
              <span className="shrink-0 font-mono text-xs text-muted-foreground">
                {sat.altitudeKm != null ? `${sat.altitudeKm} km` : "N/A"}
              </span>
            </div>
          ))}
      </CardContent>
    </Card>
  );
}
