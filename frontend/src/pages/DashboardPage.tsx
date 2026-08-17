import { AlertTriangle, Radar, Satellite, ShieldAlert } from "lucide-react";

import { AlertsFeedPanel } from "@/components/dashboard/AlertsFeedPanel";
import { AltitudeTrendChart } from "@/components/dashboard/AltitudeTrendChart";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { SatelliteQuickList } from "@/components/dashboard/SatelliteQuickList";
import { useAlerts } from "@/hooks/useAlerts";
import { getUpcomingAlert } from "@/mock/alerts";
import { useSatellites } from "@/hooks/useSatellites";
import { formatCountdown, formatDateTime } from "@/lib/format";

export function DashboardPage() {
  const { satellites, isLoading: satellitesLoading } = useSatellites();
  const { alerts, isLoading: alertsLoading } = useAlerts();

  const activeAlerts = alerts.filter((a) => a.status === "open" || a.status === "monitoring");
  const highRiskAlerts = activeAlerts.filter(
    (a) => a.riskLevel === "high" || a.riskLevel === "critical"
  );
  const upcoming = getUpcomingAlert(alerts);
  const isLoading = satellitesLoading || alertsLoading;

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
          value={String(satellites.length)}
          icon={Satellite}
          accent="default"
          sublabel={`${satellites.filter((s) => s.status === "active").length} active`}
          isLoading={isLoading}
        />
        <KpiCard
          label="Active Alerts"
          value={String(activeAlerts.length)}
          icon={AlertTriangle}
          accent="warning"
          sublabel="Open + monitoring"
          isLoading={isLoading}
        />
        <KpiCard
          label="High Risk Alerts"
          value={String(highRiskAlerts.length)}
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
          <AltitudeTrendChart />
        </div>
        <SatelliteQuickList />
      </div>

      <AlertsFeedPanel />
    </div>
  );
}
