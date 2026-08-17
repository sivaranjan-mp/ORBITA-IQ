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
import { useSatellites } from "@/hooks/useSatellites";

export function SatelliteTable() {
  const { satellites, isLoading } = useSatellites();
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
                  <TableCell colSpan={7}>
                    <Skeleton className="h-6 w-full" />
                  </TableCell>
                </TableRow>
              ))}

            {!isLoading && filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                  No satellites match "{query}".
                </TableCell>
              </TableRow>
            )}

            {!isLoading &&
              filtered.map((sat) => (
                <TableRow key={sat.id}>
                  <TableCell>
                    <p className="font-medium">{sat.name}</p>
                    <p className="text-xs text-muted-foreground">{sat.internationalDesignator}</p>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{sat.noradId}</TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {sat.altitudeKm.toLocaleString()} km
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {sat.latitudeDeg?.toFixed(2)}°
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {sat.longitudeDeg?.toFixed(2)}°
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {sat.velocityKmS?.toFixed(2)} km/s
                  </TableCell>
                  <TableCell>
                    <SatelliteStatusBadge status={sat.status} />
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
