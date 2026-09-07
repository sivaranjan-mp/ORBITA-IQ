import { useState } from "react";
import { CheckCircle2, Eye } from "lucide-react";

import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
import { OrbitDataQualityPanel } from "@/components/conjunctions/OrbitDataQualityPanel";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
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
import { formatCollisionDate, formatCollisionTime, formatDateTime, formatProbability, formatTcaHorizon } from "@/lib/format";
import type { AlertStatus, ConjunctionAlert } from "@/types/alert";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
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

  const missKm = alert.missDistanceKm ?? (alert.missDistanceM / 1000.0);
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

  return (
    <Dialog open={alert !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center justify-between pr-4">
            <div className="flex items-center gap-2">
              <DialogTitle className="text-base font-semibold">
                Conjunction Assessment
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

        <div className="space-y-1 text-xs">
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
            label="Miss Distance"
            value={
              <span className="font-mono font-semibold">
                {missKm.toFixed(3)} km ({alert.missDistanceM.toLocaleString()} m)
              </span>
            }
          />
          <Row
            label="Relative Velocity"
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

          <Separator className="my-2" />

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

          <Separator className="my-2" />

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


        {onStatusUpdate && (
          <DialogFooter className="flex gap-2 sm:justify-between pt-2">
            <div className="flex gap-2">
              {alert.status !== "monitoring" && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isUpdating}
                  onClick={() => handleStatus("monitoring")}
                  className="gap-1.5 text-xs"
                >
                  <Eye className="h-3.5 w-3.5" />
                  Monitor
                </Button>
              )}
              {alert.status !== "resolved" && (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={isUpdating}
                  onClick={() => handleStatus("resolved")}
                  className="gap-1.5 text-xs"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Resolve
                </Button>
              )}
            </div>
            <Button size="sm" variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
