import { useState } from "react";
import { CheckCircle2, Eye } from "lucide-react";

import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
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
import { formatDateTime, formatProbability, formatTcaHorizon } from "@/lib/format";
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
      <DialogContent className="max-w-md">
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
          <Row label="Time of Closest Approach (TCA)" value={formatDateTime(alert.tca)} />
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
          <Row label="Collision Probability" value={formatProbability(alert.probability)} />

          <Separator className="my-2" />

          <Row
            label="Primary Object"
            value={`${alert.primarySatellite} (NORAD #${alert.primaryNoradId})`}
          />
          <Row
            label="Secondary Object"
            value={`${alert.secondaryObject} (NORAD #${alert.secondaryNoradId})`}
          />

          <Separator className="my-2" />

          <Row label="Detection Engine" value={alert.detectedBy.replace("_", " ")} />
          <Row label="Computed At" value={formatDateTime(alert.computedAt || alert.createdAt)} />
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
