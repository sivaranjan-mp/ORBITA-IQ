import type { SatelliteStatus } from "@/types/satellite";
import { cn } from "@/lib/utils";

export function SatelliteStatusBadge({
  status,
  className,
}: {
  status: SatelliteStatus;
  className?: string;
}) {
  if (status === "active") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.15)]",
          className
        )}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.9)] animate-pulse" />
        Active (Moving)
      </span>
    );
  }

  if (status === "degraded") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.15)]",
          className
        )}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.8)]" />
        Degraded
      </span>
    );
  }

  if (status === "inactive") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border border-slate-500/30 bg-slate-500/15 px-2.5 py-0.5 text-[11px] font-medium text-slate-300",
          className
        )}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
        Inactive (Derelict)
      </span>
    );
  }

  // decayed / dead debris
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-rose-500/40 bg-rose-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.2)]",
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-rose-500 shadow-[0_0_6px_rgba(244,63,94,0.9)]" />
      Dead (Debris)
    </span>
  );
}
