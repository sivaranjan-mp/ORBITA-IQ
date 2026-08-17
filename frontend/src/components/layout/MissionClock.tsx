import { useMissionClock } from "@/hooks/useMissionClock";

export function MissionClock() {
  const now = useMissionClock();

  const time = now.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "UTC",
  });

  const date = now.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "2-digit",
    timeZone: "UTC",
  });

  const doy = Math.floor(
    (Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) -
      Date.UTC(now.getUTCFullYear(), 0, 0)) /
      86_400_000
  );

  return (
    <div className="flex items-center gap-3 rounded-md border border-border bg-secondary/40 px-3 py-1.5 font-mono">
      <div className="text-right leading-none">
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground">UTC · DOY {doy}</p>
        <p className="text-sm font-semibold tabular-nums text-primary">{time}</p>
      </div>
      <span className="hidden text-xs text-muted-foreground sm:inline">{date}</span>
    </div>
  );
}
