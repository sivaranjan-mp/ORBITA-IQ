import { useMemo, useState } from "react";
import {
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import { AiAlertCard } from "@/components/ai-assistant/AiAlertCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAiAdvisory } from "@/hooks/useAiAdvisory";
import { useAlerts } from "@/hooks/useAlerts";
import { formatTcaHorizon } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { RiskLevel, ScreeningScope } from "@/types/alert";

const RISK_FILTERS: Array<{ label: string; value: RiskLevel | "all" }> = [
  { label: "All Risk", value: "all" },
  { label: "Critical (<1 km)", value: "critical" },
  { label: "High (1–5 km)", value: "high" },
  { label: "Medium (5–25 km)", value: "medium" },
  { label: "Low (25–50 km)", value: "low" },
];

const SCOPE_FILTERS: Array<{ label: string; value: ScreeningScope | "all" }> = [
  { label: "All Scopes", value: "all" },
  { label: "Fleet vs Fleet", value: "fleet_vs_fleet" },
  { label: "Fleet vs Catalog", value: "fleet_vs_catalog" },
];

export function AiAssistantPage() {
  const { alerts, isLoading: isAlertsLoading, refetch: refetchAlerts } = useAlerts();
  const {
    advisories,
    generatingIds,
    generateAdvisory,
    fetchCachedAdvisories,
  } = useAiAdvisory();

  const [riskFilter, setRiskFilter] = useState<RiskLevel | "all">("all");
  const [scopeFilter, setScopeFilter] = useState<ScreeningScope | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredAlerts = useMemo(() => {
    let rows = alerts;

    if (riskFilter !== "all") {
      rows = rows.filter((a) => a.riskLevel === riskFilter);
    }
    if (scopeFilter !== "all") {
      rows = rows.filter((a) => (a.screeningScope || "fleet_vs_catalog") === scopeFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      rows = rows.filter(
        (a) =>
          a.primarySatellite.toLowerCase().includes(q) ||
          a.secondaryObject.toLowerCase().includes(q) ||
          String(a.primaryNoradId).includes(q) ||
          String(a.secondaryNoradId).includes(q)
      );
    }

    return [...rows].sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime());
  }, [alerts, riskFilter, scopeFilter, searchQuery]);

  // Metric computations
  const totalAlerts = alerts.length;
  const criticalHighCount = alerts.filter((a) => a.riskLevel === "critical" || a.riskLevel === "high").length;
  const advisoriesCount = Object.keys(advisories).length;
  const nearestAlert = alerts.length > 0
    ? [...alerts].sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime())[0]
    : null;

  const handleRefresh = async () => {
    await Promise.all([refetchAlerts(true), fetchCachedAdvisories()]);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight">AI Assistant</h1>
            <span className="flex items-center gap-1 rounded-full border border-purple-500/30 bg-purple-500/10 px-2.5 py-0.5 text-xs font-semibold text-purple-300">
              <Sparkles className="h-3.5 w-3.5 text-purple-400" />
              Maneuver Intelligence
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            LLM-driven qualitative conjunction analysis, orbital encounter synthesis, and collision avoidance maneuver guidance.
          </p>
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={handleRefresh}
          disabled={isAlertsLoading}
          className="h-8 gap-1.5 text-xs font-medium"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isAlertsLoading && "animate-spin text-primary")} />
          Refresh Intel
        </Button>
      </div>

      {/* Metric Summary Cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-border bg-card/60 p-3.5 shadow-sm">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Active Conjunctions
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-foreground">
            {isAlertsLoading ? "—" : totalAlerts}
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">Across Fleet & Catalog</p>
        </div>

        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3.5 shadow-sm">
          <p className="text-[11px] font-medium uppercase tracking-wider text-red-300">
            Critical / High Risk
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-red-400">
            {isAlertsLoading ? "—" : criticalHighCount}
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">Requiring Operator Attention</p>
        </div>

        <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-3.5 shadow-sm">
          <p className="text-[11px] font-medium uppercase tracking-wider text-purple-300">
            AI Advisories Ready
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-purple-400">
            {advisoriesCount}
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">Cached for Instant Review</p>
        </div>

        <div className="rounded-lg border border-border bg-card/60 p-3.5 shadow-sm">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Nearest Encounter
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-cyan-400">
            {nearestAlert ? formatTcaHorizon(nearestAlert.tca) : "—"}
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground truncate">
            {nearestAlert ? `${nearestAlert.primarySatellite} vs ${nearestAlert.secondaryObject}` : "No events"}
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {/* Risk Filters */}
          <div className="flex flex-wrap gap-1.5">
            {RISK_FILTERS.map((f) => (
              <Button
                key={f.value}
                size="sm"
                variant={riskFilter === f.value ? "default" : "outline"}
                onClick={() => setRiskFilter(f.value)}
                className={cn(
                  "h-8 text-xs font-medium",
                  riskFilter !== f.value && "text-muted-foreground hover:text-foreground"
                )}
              >
                {f.label}
              </Button>
            ))}
          </div>

          <div className="hidden h-5 w-px bg-border sm:block" />

          {/* Scope Filters */}
          <div className="flex rounded-md border border-border bg-card p-0.5 text-xs">
            {SCOPE_FILTERS.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => setScopeFilter(s.value)}
                className={cn(
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  scopeFilter === s.value
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Search Box */}
        <div className="relative w-full lg:w-64">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search satellite or NORAD…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 pl-8 text-xs"
          />
        </div>
      </div>

      {/* Alert Cards List */}
      <div className="space-y-3">
        {isAlertsLoading &&
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-lg border border-border bg-card/40 p-4 space-y-3">
              <Skeleton className="h-6 w-1/3" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ))}

        {!isAlertsLoading && filteredAlerts.length === 0 && (
          <div className="rounded-lg border border-border bg-card/30 py-12 text-center text-muted-foreground">
            <div className="mx-auto flex max-w-sm flex-col items-center justify-center space-y-2">
              <ShieldAlert className="h-8 w-8 text-muted-foreground/60" />
              <p className="text-sm font-medium text-foreground">No conjunction alerts match</p>
              <p className="text-xs text-muted-foreground">
                Try adjusting the risk filter, scope, or search query.
              </p>
            </div>
          </div>
        )}

        {!isAlertsLoading &&
          filteredAlerts.map((alert) => {
            const advisory = advisories[alert.id];
            const isGenerating = generatingIds.has(alert.id);

            return (
              <AiAlertCard
                key={alert.id}
                alert={alert}
                advisory={advisory}
                isGenerating={isGenerating}
                onGenerate={generateAdvisory}
              />
            );
          })}
      </div>
    </div>
  );
}
