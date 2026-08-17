import { AlertsTable } from "@/components/alerts/AlertsTable";

export function AlertsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Alerts</h1>
        <p className="text-sm text-muted-foreground">
          Conjunction Data Message screening results, sorted by time of closest approach.
        </p>
      </div>

      <AlertsTable />
    </div>
  );
}
