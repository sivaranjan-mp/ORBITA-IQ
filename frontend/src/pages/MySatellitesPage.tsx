import { AddSatelliteDialog } from "@/components/satellites/AddSatelliteDialog";
import { SatelliteTable } from "@/components/satellites/SatelliteTable";

export function MySatellitesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">My Satellites</h1>
          <p className="text-sm text-muted-foreground">
            Objects currently under active tracking for your organization.
          </p>
        </div>
        <AddSatelliteDialog />
      </div>

      <SatelliteTable />
    </div>
  );
}
