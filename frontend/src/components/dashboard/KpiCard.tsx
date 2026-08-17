import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  accent?: "default" | "destructive" | "warning" | "success";
  sublabel?: string;
  isLoading?: boolean;
}

const ACCENT_STYLES: Record<NonNullable<KpiCardProps["accent"]>, string> = {
  default: "bg-primary/15 text-primary",
  destructive: "bg-destructive/15 text-destructive",
  warning: "bg-amber-500/15 text-amber-400",
  success: "bg-emerald-500/15 text-emerald-400",
};

export function KpiCard({
  label,
  value,
  icon: Icon,
  accent = "default",
  sublabel,
  isLoading,
}: KpiCardProps) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-4 p-5">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          {isLoading ? (
            <Skeleton className="mt-2 h-8 w-20" />
          ) : (
            <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
          )}
          {sublabel && !isLoading && (
            <p className="mt-1 truncate text-xs text-muted-foreground">{sublabel}</p>
          )}
        </div>
        <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", ACCENT_STYLES[accent])}>
          <Icon className="h-5 w-5" />
        </div>
      </CardContent>
    </Card>
  );
}
