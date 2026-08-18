import { AlertTriangle, Radar, Satellite, ShieldAlert } from "lucide-react";

import { AlertsFeedPanel } from "@/components/dashboard/AlertsFeedPanel";
import { AltitudeTrendChart } from "@/components/dashboard/AltitudeTrendChart";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { SatelliteQuickList } from "@/components/dashboard/SatelliteQuickList";
import { useDashboard } from "@/hooks/useDashboard";
import { formatCountdown, formatDateTime } from "@/lib/format";

export function DashboardPage() {
  const { summary, isLoading, error } = useDashboard();

  if (error) {
    return <div className="text-destructive font-medium p-4">Error loading dashboard: {error}</div>;
  }

  const upcoming = summary?.next_conjunction;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Fleet-wide status overview and conjunction risk summary.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Tracked Satellites"
          value={String(summary?.tracked_satellites ?? "—")}
          icon={Satellite}
          accent="default"
          sublabel="Total satellites in database"
          isLoading={isLoading}
        />
        <KpiCard
          label="Active Alerts"
          value={String(summary?.active_alerts ?? "—")}
          icon={AlertTriangle}
          accent="warning"
          sublabel="Open + monitoring"
          isLoading={isLoading}
        />
        <KpiCard
          label="High Risk Alerts"
          value={String(summary?.high_risk_alerts ?? "—")}
          icon={ShieldAlert}
          accent="destructive"
          sublabel="High + critical risk"
          isLoading={isLoading}
        />
        <KpiCard
          label="Next Conjunction"
          value={upcoming ? formatCountdown(upcoming.tca) : "—"}
          icon={Radar}
          accent={upcoming?.riskLevel === "critical" ? "destructive" : "default"}
          sublabel={upcoming ? `${upcoming.primarySatellite} · TCA ${formatDateTime(upcoming.tca)}` : "No upcoming events"}
          isLoading={isLoading}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <AltitudeTrendChart trendData={summary?.altitude_trend} />
        </div>
        <SatelliteQuickList />
      </div>

      <AlertsFeedPanel />
    </div>
  );
}
