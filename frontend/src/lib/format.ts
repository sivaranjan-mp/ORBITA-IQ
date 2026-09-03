export function formatCountdown(targetIso: string): string {
  const diffMs = new Date(targetIso).getTime() - Date.now();
  const isPast = diffMs < 0;
  const abs = Math.abs(diffMs);

  const hours = Math.floor(abs / 3_600_000);
  const minutes = Math.floor((abs % 3_600_000) / 60_000);
  const seconds = Math.floor((abs % 60_000) / 1000);

  const label = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(
    seconds
  ).padStart(2, "0")}`;

  return isPast ? `T+${label}` : `T-${label}`;
}

export function formatTcaHorizon(targetIso: string): string {
  const diffMs = new Date(targetIso).getTime() - Date.now();
  if (diffMs < 0) return "Passed";
  const hours = diffMs / 3_600_000;
  if (hours >= 24) {
    const days = (hours / 24).toFixed(1);
    return `${days}d out`;
  } else if (hours >= 1) {
    return `${hours.toFixed(1)}h out`;
  } else {
    const mins = Math.max(1, Math.round(diffMs / 60_000));
    return `${mins}m out`;
  }
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return (
    d.toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZone: "UTC",
    }) + " UTC"
  );
}

export function formatCollisionDate(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    timeZone: "UTC",
  });
}

export function formatCollisionTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return (
    d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZone: "UTC",
    }) + " UTC"
  );
}

export function formatCollisionDateTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return `${formatCollisionDate(iso)} · ${formatCollisionTime(iso)}`;
}

export function formatProbability(p: number): string {
  return p.toExponential(2);
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat().format(n);
}
