import { AlertStatusBadge } from "@/components/alerts/AlertStatusBadge";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { formatDateTime, formatProbability } from "@/lib/format";
import type { ConjunctionAlert } from "@/types/alert";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

export function AlertDetailDialog({
  alert,
  onOpenChange,
}: {
  alert: ConjunctionAlert | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={alert !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        {alert && (
          <>
            <DialogHeader>
              <div className="flex items-center gap-2">
                <DialogTitle>Conjunction {alert.id.toUpperCase()}</DialogTitle>
                <RiskBadge level={alert.riskLevel} />
              </div>
              <DialogDescription>
                {alert.primarySatellite} vs. {alert.secondaryObject}
              </DialogDescription>
            </DialogHeader>

            <div>
              <Row label="Status" value={<AlertStatusBadge status={alert.status} />} />
              <Row label="Time of closest approach" value={formatDateTime(alert.tca)} />
              <Row label="Miss distance" value={`${alert.missDistanceM.toLocaleString()} m`} />
              <Row label="Collision probability" value={formatProbability(alert.probability)} />
              <Separator className="my-2" />
              <Row label="Primary object" value={`${alert.primarySatellite} (#${alert.primaryNoradId})`} />
              <Row label="Secondary object" value={`${alert.secondaryObject} (#${alert.secondaryNoradId})`} />
              <Separator className="my-2" />
              <Row label="Detected by" value={alert.detectedBy.replace("_", " ")} />
              <Row label="Created" value={formatDateTime(alert.createdAt)} />
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
