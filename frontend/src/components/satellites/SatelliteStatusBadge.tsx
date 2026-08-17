import { Badge } from "@/components/ui/badge";
import type { SatelliteStatus } from "@/types/satellite";

const VARIANT: Record<SatelliteStatus, "success" | "warning" | "secondary" | "destructive"> = {
  active: "success",
  degraded: "warning",
  inactive: "secondary",
  decayed: "destructive",
};

const LABEL: Record<SatelliteStatus, string> = {
  active: "Active",
  degraded: "Degraded",
  inactive: "Inactive",
  decayed: "Decayed",
};

export function SatelliteStatusBadge({ status }: { status: SatelliteStatus }) {
  return <Badge variant={VARIANT[status]}>{LABEL[status]}</Badge>;
}
