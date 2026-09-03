import { AlertTriangle, Radar, Satellite, ShieldAlert } from "lucide-react";

import { AlertsFeedPanel } from "@/components/dashboard/AlertsFeedPanel";
import { AltitudeTrendChart } from "@/components/dashboard/AltitudeTrendChart";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { SatelliteQuickList } from "@/components/dashboard/SatelliteQuickList";
import { useAlerts } from "@/hooks/useAlerts";
import { useDashboard } from "@/hooks/useDashboard";
import { formatCollisionDateTime, formatCountdown } from "@/lib/format";

import { ConjunctionsTable } from "@/components/conjunctions/ConjunctionsTable";
import { TimelineChart } from "@/components/conjunctions/TimelineChart";

export function DashboardPage() {
  const { summary, isLoading: isDashLoading, error } = useDashboard();
  const { alerts, isLoading: isAlertsLoading } = useAlerts();

  if (error) {
    return <div className="text-destructive font-medium p-4">Error loading dashboard: {error}</div>;
  }

  const activeAlertsCount =
    alerts.length > 0
      ? alerts.filter((a) => a.status === "open" || a.status === "monitoring" || a.status === "active").length
      : (summary?.active_alerts ?? 0);

  const highRiskAlertsCount =
    alerts.length > 0
      ? alerts.filter((a) => a.riskLevel === "high" || a.riskLevel === "critical").length
      : (summary?.high_risk_alerts ?? 0);

  const sortedUpcoming = [...alerts]
    .filter((a) => a.status === "open" || a.status === "monitoring" || a.status === "active")
    .sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime());

  const upcoming = sortedUpcoming.length > 0 ? sortedUpcoming[0] : summary?.next_conjunction;
  const isLoading = isDashLoading && isAlertsLoading;

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
          value={String(activeAlertsCount)}
          icon={AlertTriangle}
          accent={activeAlertsCount > 0 ? "warning" : "default"}
          sublabel="Open + monitoring"
          isLoading={isLoading}
        />
        <KpiCard
          label="High Risk Alerts"
          value={String(highRiskAlertsCount)}
          icon={ShieldAlert}
          accent={highRiskAlertsCount > 0 ? "destructive" : "default"}
          sublabel="High + critical risk"
          isLoading={isLoading}
        />
        <KpiCard
          label="Next Conjunction"
          value={upcoming ? formatCountdown(upcoming.tca) : "—"}
          icon={Radar}
          accent={upcoming?.riskLevel === "critical" ? "destructive" : "default"}
          sublabel={
            upcoming
              ? `${upcoming.primarySatellite} · Collision ${formatCollisionDateTime(upcoming.tca)}`
              : "No upcoming events"
          }
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
      
      <div className="pt-6 border-t border-slate-200 dark:border-slate-800">
        <TimelineChart />
      </div>

      <div className="pt-4">
        <ConjunctionsTable />
      </div>
    </div>
  );
}
