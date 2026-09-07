import { useState } from "react";
import { CheckCircle2, Compass, Crosshair, Eye, ShieldCheck } from "lucide-react";

import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
import { OrbitDataQualityPanel } from "@/components/conjunctions/OrbitDataQualityPanel";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import {
  formatCollisionDate,
  formatCollisionTime,
  formatDateTime,
  formatProbability,
  formatTcaHorizon,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AlertStatus, ConjunctionAlert } from "@/types/alert";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

export function AlertDetailDialog({
  alert,
  onOpenChange,
  onStatusUpdate,
}: {
  alert: ConjunctionAlert | null;
  onOpenChange: (open: boolean) => void;
  onStatusUpdate?: (alertId: string, status: AlertStatus) => Promise<void>;
}) {
  const [isUpdating, setIsUpdating] = useState(false);

  if (!alert) return null;

  const missKm = alert.missDistanceKm ?? alert.missDistanceM / 1000.0;
  const horizon = formatTcaHorizon(alert.tca);
  const isFleetVsFleet = alert.screeningScope === "fleet_vs_fleet";

  const handleStatus = async (status: AlertStatus) => {
    if (!onStatusUpdate) return;
    setIsUpdating(true);
    try {
      await onStatusUpdate(alert.id, status);
    } finally {
      setIsUpdating(false);
    }
  };

  // RIC Decomposition calculations & check
  const r = alert.radialSeparationKm;
  const i = alert.alongTrackSeparationKm;
  const c = alert.crossTrackSeparationKm;
  const hasRic = r != null && i != null && c != null;
  const reconstructedMiss = hasRic ? Math.sqrt(r * r + i * i + c * c) : null;
  const isConsistent =
    reconstructedMiss != null && Math.abs(reconstructedMiss - missKm) < 0.005;

  const geomLabel = alert.encounterGeometry || "crossing";
  const geomColor =
    geomLabel === "co-orbital"
      ? "bg-blue-500/10 text-blue-400 border-blue-500/30"
      : geomLabel === "head-on"
      ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
      : "bg-purple-500/10 text-purple-400 border-purple-500/30";

  return (
    <Dialog open={alert !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center justify-between pr-4">
            <div className="flex items-center gap-2">
              <DialogTitle className="text-base font-semibold">
                Conjunction Assessment & Encounter Geometry
              </DialogTitle>
              <RiskBadge level={alert.riskLevel} />
            </div>
            <span className="rounded bg-secondary/80 px-2 py-0.5 text-xs font-mono text-muted-foreground">
              {horizon}
            </span>
          </div>
          <DialogDescription className="text-xs">
            {alert.primarySatellite} vs. {alert.secondaryObject}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-xs">
          {/* Top Status & Timing Info */}
          <div className="rounded-md border border-border/60 bg-muted/20 p-2.5 space-y-1">
            <Row label="Current Status" value={<AlertStatusBadge status={alert.status} />} />
            <Row
              label="Screening Scope"
              value={
                <span className="font-mono text-xs font-semibold">
                  {isFleetVsFleet ? "Fleet vs Fleet (Internal)" : "Fleet vs Space Catalog"}
                </span>
              }
            />
            <Row
              label="Date of Collision"
              value={<span className="font-mono font-semibold">{formatCollisionDate(alert.tca)}</span>}
            />
            <Row
              label="Time of Collision (TCA)"
              value={
                <div className="flex items-center gap-2 font-mono">
                  <span>{formatCollisionTime(alert.tca)}</span>
                  <span className="rounded bg-secondary/80 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                    {horizon}
                  </span>
                </div>
              }
            />
            <Row
              label="Total Miss Distance"
              value={
                <span className="font-mono font-semibold text-foreground">
                  {missKm.toFixed(3)} km ({alert.missDistanceM.toLocaleString()} m)
                </span>
              }
            />
            <Row
              label="Relative Velocity (|Δv|)"
              value={
                alert.relativeVelocityKmS != null
                  ? `${alert.relativeVelocityKmS.toFixed(2)} km/s`
                  : "—"
              }
            />
            <Row label="Collision Probability (Pc)" value={formatProbability(alert.probability)} />
            <Row
              label="Combined Collision Disk (HBR)"
              value={
                <div className="flex items-center gap-1.5">
                  <span className="font-mono font-semibold">
                    {(alert.combinedHbr ?? 3.0).toFixed(1)} m
                  </span>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    (HBR₁ + HBR₂)
                  </span>
                </div>
              }
            />
          </div>

          {/* Encounter Geometry Card */}
          <div className="rounded-md border border-border/80 bg-card/60 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
                <Compass className="h-3.5 w-3.5 text-primary" />
                Encounter Geometry Classification
              </span>
              <Badge variant="outline" className={cn("capitalize font-mono text-[11px]", geomColor)}>
                {geomLabel.replace("-", " ")}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
              <div className="rounded border border-border/40 bg-background/50 p-2 space-y-0.5">
                <span className="text-[10px] text-muted-foreground uppercase block font-sans">
                  Velocity Vector Angle
                </span>
                <span className="text-xs font-semibold text-foreground">
                  {alert.relativeVelocityAngleDeg != null
                    ? `${alert.relativeVelocityAngleDeg.toFixed(2)}°`
                    : "—"}
                </span>
                <span className="text-[9px] text-muted-foreground block font-sans">
                  Angle between velocity vectors at TCA
                </span>
              </div>

              <div className="rounded border border-border/40 bg-background/50 p-2 space-y-0.5">
                <span className="text-[10px] text-muted-foreground uppercase block font-sans">
                  Relative Inclination (Δi)
                </span>
                <span className="text-xs font-semibold text-foreground">
                  {alert.relativeInclinationDeg != null
                    ? `${alert.relativeInclinationDeg.toFixed(2)}°`
                    : "—"}
                </span>
                <span className="text-[9px] text-muted-foreground block font-sans">
                  Orbital plane momentum intersection
                </span>
              </div>
            </div>
          </div>

          {/* RIC Frame Decomposition Card */}
          <div className="rounded-md border border-border/80 bg-card/60 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
                <Crosshair className="h-3.5 w-3.5 text-primary" />
                RIC Frame Decomposition (Primary Orbit Basis)
              </span>
              {isConsistent && (
                <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 font-mono">
                  <ShieldCheck className="h-3 w-3" />
                  √(R²+I²+C²) Verified
                </span>
              )}
            </div>

            <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-[11px]">
              {/* Radial Component */}
              <div className="rounded border border-border/40 bg-background/50 p-2 space-y-0.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-sky-400 uppercase font-sans">
                    Radial (ΔR)
                  </span>
                </div>
                <span className="text-xs font-semibold text-foreground block">
                  {r != null ? `${r >= 0 ? "+" : ""}${r.toFixed(3)} km` : "—"}
                </span>
                <span className="text-[9px] text-muted-foreground block font-sans leading-tight">
                  Altitude separation
                </span>
              </div>

              {/* In-Track Component */}
              <div className="rounded border border-border/40 bg-background/50 p-2 space-y-0.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-amber-400 uppercase font-sans">
                    In-Track (ΔI)
                  </span>
                </div>
                <span className="text-xs font-semibold text-foreground block">
                  {i != null ? `${i >= 0 ? "+" : ""}${i.toFixed(3)} km` : "—"}
                </span>
                <span className="text-[9px] text-muted-foreground block font-sans leading-tight">
                  Along-track lead/lag
                </span>
              </div>

              {/* Cross-Track Component */}
              <div className="rounded border border-border/40 bg-background/50 p-2 space-y-0.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-purple-400 uppercase font-sans">
                    Cross-Track (ΔC)
                  </span>
                </div>
                <span className="text-xs font-semibold text-foreground block">
                  {c != null ? `${c >= 0 ? "+" : ""}${c.toFixed(3)} km` : "—"}
                </span>
                <span className="text-[9px] text-muted-foreground block font-sans leading-tight">
                  Out-of-plane offset
                </span>
              </div>
            </div>

            {/* Relative Vectors in TEME */}
            {(alert.relativePosition || alert.relativeVelocity) && (
              <div className="pt-1 text-[10px] text-muted-foreground font-mono space-y-0.5 border-t border-border/40 mt-2">
                {alert.relativePosition && (
                  <div className="flex justify-between">
                    <span>Δr (TEME):</span>
                    <span>
                      [{alert.relativePosition[0].toFixed(3)},{" "}
                      {alert.relativePosition[1].toFixed(3)},{" "}
                      {alert.relativePosition[2].toFixed(3)}] km
                    </span>
                  </div>
                )}
                {alert.relativeVelocity && (
                  <div className="flex justify-between">
                    <span>Δv (TEME):</span>
                    <span>
                      [{alert.relativeVelocity[0].toFixed(3)},{" "}
                      {alert.relativeVelocity[1].toFixed(3)},{" "}
                      {alert.relativeVelocity[2].toFixed(3)}] km/s
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Objects & Telemetry */}
          <div className="rounded-md border border-border/60 bg-muted/20 p-2.5 space-y-1">
            <Row
              label="Primary Object"
              value={
                <div className="flex flex-col items-end gap-1">
                  <span>{alert.primarySatellite} (NORAD #{alert.primaryNoradId})</span>
                  <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono ${
                    alert.hbrAIsKnown
                      ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                      : "bg-secondary text-muted-foreground border border-border"
                  }`}>
                    HBR: {(alert.hbrA ?? 1.5).toFixed(1)} m {alert.hbrAIsKnown ? "• Measured / Known" : "• CARA Default (1.5 m)"}
                  </span>
                </div>
              }
            />
            <Row
              label="Secondary Object"
              value={
                <div className="flex flex-col items-end gap-1">
                  <span>{alert.secondaryObject} (NORAD #{alert.secondaryNoradId})</span>
                  <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono ${
                    alert.hbrBIsKnown
                      ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                      : "bg-secondary text-muted-foreground border border-border"
                  }`}>
                    HBR: {(alert.hbrB ?? 1.5).toFixed(1)} m {alert.hbrBIsKnown ? "• Measured / Known" : "• CARA Default (1.5 m)"}
                  </span>
                </div>
              }
            />
            <Row label="Detection Engine" value={alert.detectedBy.replace("_", " ")} />
            <Row label="Computed At" value={formatDateTime(alert.computedAt || alert.createdAt)} />

            {/* Real-time Orbit Data Quality & Freshness Assessment */}
            <Separator className="my-3" />
            <OrbitDataQualityPanel
              primarySatelliteName={alert.primarySatellite}
              primaryNoradId={alert.primaryNoradId}
              secondaryObjectName={alert.secondaryObject}
              secondaryNoradId={alert.secondaryNoradId}
              primaryQuality={alert.primaryDataQuality}
              secondaryQuality={alert.secondaryDataQuality}
            />
          </div>
        </div>

        {onStatusUpdate && (
          <DialogFooter className="flex gap-2 sm:justify-between pt-2">
            <div className="flex gap-2">
              {alert.status !== "monitoring" && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs"
                  disabled={isUpdating}
                  onClick={() => handleStatus("monitoring")}
                >
                  <Eye className="mr-1.5 h-3.5 w-3.5" />
                  Monitor
                </Button>
              )}
              {alert.status !== "resolved" && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs text-emerald-400 hover:text-emerald-300"
                  disabled={isUpdating}
                  onClick={() => handleStatus("resolved")}
                >
                  <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                  Resolve
                </Button>
              )}
            </div>
            <Button
              size="sm"
              variant="secondary"
              className="text-xs"
              onClick={() => onOpenChange(false)}
            >
              Close
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
