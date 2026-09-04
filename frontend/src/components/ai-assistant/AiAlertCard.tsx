import { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Satellite,
  Sparkles,
} from "lucide-react";

import { AiAdvisoryDetail } from "@/components/ai-assistant/AiAdvisoryDetail";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCollisionDate, formatCollisionTime, formatTcaHorizon } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AIManeuverAdvisory } from "@/types/aiAdvisory";
import type { ConjunctionAlert } from "@/types/alert";

interface AiAlertCardProps {
  alert: ConjunctionAlert;
  advisory?: AIManeuverAdvisory;
  isGenerating?: boolean;
  onGenerate: (alert: ConjunctionAlert, forceRefresh?: boolean) => Promise<unknown>;
}

export function AiAlertCard({
  alert,
  advisory,
  isGenerating = false,
  onGenerate,
}: AiAlertCardProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(Boolean(advisory));

  const missKm = alert.missDistanceKm ?? alert.missDistanceM / 1000.0;
  const isFleetVsFleet = alert.screeningScope === "fleet_vs_fleet";
  const horizon = formatTcaHorizon(alert.tca);
  const hasAdvisory = Boolean(advisory);
  const isSimulated =
    advisory &&
    (advisory.modelUsed.toLowerCase().includes("simulated") ||
      advisory.modelUsed.toLowerCase().includes("fallback") ||
      advisory.modelUsed.toLowerCase().includes("(advisory)"));

  const handleGenerateClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded(true);
    await onGenerate(alert, false);
  };

  const toggleExpand = () => {
    setIsExpanded((prev) => !prev);
  };

  return (
    <div
      className={cn(
        "rounded-lg border transition-all duration-200 overflow-hidden",
        hasAdvisory
          ? isSimulated
            ? "border-amber-500/40 bg-card/60 shadow-sm hover:border-amber-500/60"
            : "border-purple-500/30 bg-card/60 shadow-sm hover:border-purple-500/50"
          : "border-border bg-card/40 hover:border-border/80"
      )}
    >
      {/* Clickable Header Bar */}
      <div
        onClick={hasAdvisory ? toggleExpand : undefined}
        className={cn(
          "flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between",
          hasAdvisory && "cursor-pointer hover:bg-muted/30"
        )}
      >
        {/* Left: Satellite Pair & Scope */}
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-foreground text-sm flex items-center gap-1.5">
              <Satellite className="h-4 w-4 text-primary" />
              {alert.primarySatellite}
            </span>
            <span className="text-xs text-muted-foreground">vs</span>
            <span className="font-medium text-foreground text-sm">
              {alert.secondaryObject}
            </span>

            <span
              className={cn(
                "inline-flex items-center rounded px-2 py-0.5 text-[10px] font-medium font-mono",
                isFleetVsFleet
                  ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                  : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
              )}
            >
              {isFleetVsFleet ? "Fleet vs Fleet" : "Fleet vs Catalog"}
            </span>

            <RiskBadge level={alert.riskLevel} />
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground font-mono">
            <span>Primary: #{alert.primaryNoradId}</span>
            <span>•</span>
            <span>Secondary: #{alert.secondaryNoradId}</span>
            <span>•</span>
            <span className="text-foreground font-semibold">
              Miss: {missKm < 1.0 ? `${alert.missDistanceM.toFixed(0)} m` : `${missKm.toFixed(2)} km`}
            </span>
            <span>•</span>
            <span>
              Rel Vel: {alert.relativeVelocityKmS != null ? `${alert.relativeVelocityKmS.toFixed(1)} km/s` : "—"}
            </span>
          </div>
        </div>

        {/* Middle / Right: TCA & Action Button */}
        <div className="flex flex-wrap items-center gap-3 sm:justify-end">
          {/* TCA collision date and horizon badge */}
          <div className="text-right font-mono text-xs">
            <div className="flex items-center gap-1.5 sm:justify-end">
              <span className="text-xs font-semibold text-foreground">
                {formatCollisionDate(alert.tca)}
              </span>
              <span className="rounded bg-secondary/80 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                {horizon}
              </span>
            </div>
            <span className="text-[11px] text-muted-foreground">
              {formatCollisionTime(alert.tca)}
            </span>
          </div>

          {/* Action or Expand Button */}
          <div className="flex items-center gap-2">
            {!hasAdvisory && !isGenerating && (
              <Button
                size="sm"
                onClick={handleGenerateClick}
                disabled={isGenerating}
                className="h-8 gap-1.5 text-xs font-medium bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Generate Advisory
              </Button>
            )}

            {isGenerating && (
              <Button
                size="sm"
                disabled
                className="h-8 gap-1.5 text-xs font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30"
              >
                <Sparkles className="h-3.5 w-3.5 animate-spin" />
                Analyzing Orbital Telemetry…
              </Button>
            )}

            {hasAdvisory && (
              <div className="flex items-center gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={toggleExpand}
                  className={cn(
                    "h-8 gap-1 text-xs font-medium",
                    isSimulated
                      ? "border-amber-500/40 text-amber-300 bg-amber-500/10 hover:bg-amber-500/20"
                      : "border-purple-500/30 text-purple-300 bg-purple-500/10 hover:bg-purple-500/20"
                  )}
                >
                  {isSimulated ? (
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                  )}
                  <span>{isSimulated ? "Simulated Advisory Ready" : "Advisory Ready"}</span>
                  {isExpanded ? (
                    <ChevronUp className="h-3.5 w-3.5 ml-1" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5 ml-1" />
                  )}
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Expandable Section */}
      {isExpanded && (
        <div>
          {isGenerating ? (
            <div className="rounded-b-lg border-t border-border/80 bg-card/30 p-6 space-y-4">
              <div className="flex items-center gap-3 text-purple-300">
                <Sparkles className="h-5 w-5 animate-pulse text-purple-400" />
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider">
                    Querying LLM & Synthesizing Encounter Astrodynamics…
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Evaluating crossing geometry, along-track secular drift, and qualitative mitigation strategies.
                  </p>
                </div>
              </div>
              <div className="space-y-2 pt-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-16 w-full" />
              </div>
            </div>
          ) : advisory ? (
            <AiAdvisoryDetail
              advisory={advisory}
              onRegenerate={() => onGenerate(alert, true)}
              isRegenerating={isGenerating}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}
