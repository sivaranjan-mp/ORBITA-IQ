import { Badge } from "@/components/ui/badge";
import type { AlertStatus } from "@/types/alert";

const VARIANT: Record<AlertStatus, "warning" | "default" | "success" | "secondary"> = {
  open: "warning",
  active: "warning",
  monitoring: "default",
  acknowledged: "default",
  resolved: "success",
  dismissed: "secondary",
};

const LABEL: Record<AlertStatus, string> = {
  open: "Open",
  active: "Active",
  monitoring: "Monitoring",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
  dismissed: "Dismissed",
};

export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  const normalized = (status?.toLowerCase() || "open") as AlertStatus;
  const variant = VARIANT[normalized] || "secondary";
  const label = LABEL[normalized] || normalized;
  return <Badge variant={variant}>{label}</Badge>;
}
