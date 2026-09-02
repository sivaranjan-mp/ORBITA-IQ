import { AddSatelliteDialog } from "@/components/satellites/AddSatelliteDialog";
import { SatelliteTable } from "@/components/satellites/SatelliteTable";

export function AllSatellitesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">All Satellites</h1>
          <p className="text-sm text-muted-foreground">
            All objects currently tracked across the entire system.
          </p>
        </div>
        <AddSatelliteDialog />
      </div>

      <SatelliteTable showOwner={true} scope="all" />
    </div>
  );
}
