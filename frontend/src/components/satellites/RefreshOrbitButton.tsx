import { useState, useEffect } from "react";
import { RefreshCw, CheckCircle2, AlertCircle, Clock, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { SatelliteRefreshResponse } from "@/types/satellite";

interface RefreshOrbitButtonProps {
  onRefresh: () => Promise<SatelliteRefreshResponse | null>;
  isRefreshing: boolean;
  cooldownRemaining: number;
  latestUpdatedAt: Date | null;
  refreshResult: SatelliteRefreshResponse | null;
  refreshError: string | null;
  className?: string;
  showStalenessText?: boolean;
}

function formatRelativeTime(date: Date | null): string {
  if (!date) return "Never";
  const now = Date.now();
  const diffSec = Math.floor((now - date.getTime()) / 1000);

  if (diffSec < 0 || diffSec < 15) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin === 1) return "1 min ago";
  if (diffMin < 60) return `${diffMin} mins ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours === 1) return "1 hour ago";
  if (diffHours < 24) return `${diffHours} hours ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} days ago`;
}

export function RefreshOrbitButton({
  onRefresh,
  isRefreshing,
  cooldownRemaining,
  latestUpdatedAt,
  refreshResult,
  refreshError,
  className,
  showStalenessText = true,
}: RefreshOrbitButtonProps) {
  const [, setTick] = useState(0);

  // Periodic tick to update "Last updated: X mins ago" in real time
  useEffect(() => {
    const interval = setInterval(() => {
      setTick((t) => t + 1);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const stalenessText = formatRelativeTime(latestUpdatedAt);
  const isCooldown = cooldownRemaining > 0;

  return (
    <div className={cn("flex flex-col sm:flex-row items-start sm:items-center gap-2", className)}>
      {showStalenessText && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-secondary/30 border border-border/50 px-2.5 py-1 rounded-md">
          <Clock className="h-3 w-3 text-cyan-400 shrink-0" />
          <span>Last updated:</span>
          <span className="font-mono font-medium text-foreground">
            {stalenessText}
          </span>
        </div>
      )}

      <div className="flex items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onRefresh}
          disabled={isRefreshing || isCooldown}
          className={cn(
            "relative h-8 px-3 text-xs font-medium transition-all shadow-sm",
            "border-cyan-500/30 hover:border-cyan-500/60 hover:bg-cyan-500/10 text-cyan-200",
            isRefreshing && "opacity-80 cursor-not-allowed",
            isCooldown && "border-slate-700 bg-slate-900/50 text-slate-400 cursor-not-allowed"
          )}
          title={
            isCooldown
              ? `Cooldown active: ${cooldownRemaining}s remaining`
              : "Propagate all active fleet satellites now"
          }
        >
          <RefreshCw
            className={cn(
              "h-3.5 w-3.5 mr-1.5 text-cyan-400",
              isRefreshing && "animate-spin text-cyan-300",
              isCooldown && "text-slate-500"
            )}
          />
          {isRefreshing ? (
            <span className="flex items-center gap-1">
              <span>Propagating...</span>
            </span>
          ) : isCooldown ? (
            <span>Cooldown ({cooldownRemaining}s)</span>
          ) : (
            <span className="flex items-center gap-1">
              <span>Refresh Now</span>
              <Sparkles className="h-2.5 w-2.5 text-cyan-400/80" />
            </span>
          )}
        </Button>

        {/* Live Feedback Notification Pill */}
        {refreshResult && !refreshError && (
          <div className="flex items-center gap-1.5 text-[11px] font-mono font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-500/40 px-2.5 py-1 rounded-md animate-in fade-in slide-in-from-left-2 duration-200">
            <CheckCircle2 className="h-3 w-3 text-emerald-400 shrink-0" />
            <span>
              Updated {refreshResult.updated_count} satellites ({refreshResult.duration_seconds}s)
            </span>
          </div>
        )}

        {refreshError && (
          <div className="flex items-center gap-1.5 text-[11px] font-mono font-medium text-destructive bg-destructive/10 border border-destructive/30 px-2.5 py-1 rounded-md animate-in fade-in slide-in-from-left-2 duration-200">
            <AlertCircle className="h-3 w-3 text-destructive shrink-0" />
            <span>{refreshError}</span>
          </div>
        )}
      </div>
    </div>
  );
}
