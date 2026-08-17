import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { Satellite } from "@/types/satellite";

const STATUS_DOT: Record<string, string> = {
  active: "bg-emerald-400",
  degraded: "bg-amber-400",
  inactive: "bg-muted-foreground",
  decayed: "bg-destructive",
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
  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Tracked Objects ({satellites.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 space-y-1 overflow-y-auto pt-0">
        {isLoading &&
          Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-11 w-full" />)}

        {!isLoading &&
          satellites.map((sat) => (
            <button
              key={sat.id}
              onClick={() => onFocus(sat.id)}
              className={cn(
                "flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left transition-colors",
                focusedId === sat.id
                  ? "bg-primary/15 text-primary"
                  : "hover:bg-secondary/50"
              )}
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATUS_DOT[sat.status])} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium leading-tight">{sat.name}</p>
                  <p className="text-[11px] text-muted-foreground">#{sat.noradId}</p>
                </div>
              </div>
              <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
                {sat.altitudeKm} km
              </span>
            </button>
          ))}
      </CardContent>
    </Card>
  );
}
