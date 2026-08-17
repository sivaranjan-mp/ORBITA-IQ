import { Badge } from "@/components/ui/badge";
import type { AlertStatus } from "@/types/alert";

const VARIANT: Record<AlertStatus, "warning" | "default" | "success" | "secondary"> = {
  open: "warning",
  monitoring: "default",
  resolved: "success",
  dismissed: "secondary",
};

const LABEL: Record<AlertStatus, string> = {
  open: "Open",
  monitoring: "Monitoring",
  resolved: "Resolved",
  dismissed: "Dismissed",
};

export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  return <Badge variant={VARIANT[status]}>{LABEL[status]}</Badge>;
}
