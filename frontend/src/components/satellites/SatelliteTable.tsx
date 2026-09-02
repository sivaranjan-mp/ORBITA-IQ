import { useMemo, useState } from "react";
import { Search } from "lucide-react";

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
import { useAuth } from "@/hooks/useAuth";
import { useSatellites } from "@/hooks/useSatellites";
import { cn } from "@/lib/utils";

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
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return satellites;
    return satellites.filter(
      (sat) => sat.name.toLowerCase().includes(q) || String(sat.noradId).includes(q)
    );
  }, [satellites, query]);

  return (
    <div className="space-y-3">
      <div className="relative max-w-xs">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or NORAD ID…"
          className="pl-9"
        />
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

                const satOwner = sat.ownerOrg?.trim().toLowerCase();

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

                return (
                  <TableRow
                    key={sat.id}
                    className={cn(
                      isOwner &&
                        "bg-amber-950/40 hover:bg-amber-950/60 text-amber-100 border-amber-900/40"
                    )}
                  >
                    <TableCell>
                      <p className={cn("font-medium", isOwner ? "text-amber-100" : "text-foreground")}>
                        {sat.name || "Unknown"}
                      </p>
                      <p className={cn("text-xs", isOwner ? "text-amber-200/70" : "text-muted-foreground")}>
                        {sat.internationalDesignator}
                      </p>
                    </TableCell>
                    <TableCell className={cn("font-mono text-xs", isOwner ? "text-amber-100" : "text-foreground")}>
                      {sat.noradId}
                    </TableCell>
                    {showOwner && (
                      <TableCell className={cn("text-xs", isOwner ? "text-amber-200 font-medium" : "text-muted-foreground")}>
                        {sat.ownerOrg}
                        {isOwner && (
                          <span className="ml-1.5 inline-block rounded bg-amber-500/20 px-1 py-0.5 text-[10px] font-semibold text-amber-300">
                            You
                          </span>
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
                      <SatelliteStatusBadge status={sat.status} />
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
