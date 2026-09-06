import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  Award,
  CheckCircle2,
  Clock,
  Compass,
  Database,
  Layers,
  Percent,
  Satellite as SatelliteIcon,
  ShieldCheck,
  Zap,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { OrbitDataQualityBundle } from "@/types/alert";


interface OrbitDataQualityPanelProps {
  primarySatelliteName: string;
  primaryNoradId: number;
  secondaryObjectName: string;
  secondaryNoradId: number;
  primaryQuality?: OrbitDataQualityBundle | null;
  secondaryQuality?: OrbitDataQualityBundle | null;
  className?: string;
  compact?: boolean;
}

function QualityBadge({ quality }: { quality?: string }) {
  const q = (quality || "UNKNOWN").toUpperCase();
  if (q === "HIGH") {
    return (
      <Badge className="bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 gap-1 font-mono text-[11px] font-semibold">
        <CheckCircle2 className="h-3 w-3" />
        HIGH QUALITY
      </Badge>
    );
  }
  if (q === "MEDIUM") {
    return (
      <Badge className="bg-amber-500/15 text-amber-400 border border-amber-500/30 gap-1 font-mono text-[11px] font-semibold">
        <AlertTriangle className="h-3 w-3" />
        MEDIUM QUALITY
      </Badge>
    );
  }
  if (q === "LOW") {
    return (
      <Badge className="bg-rose-500/15 text-rose-400 border border-rose-500/30 gap-1 font-mono text-[11px] font-semibold">
        <AlertOctagon className="h-3 w-3" />
        LOW QUALITY
      </Badge>
    );
  }
  return (
    <Badge className="bg-red-500/20 text-red-300 border border-red-500/40 gap-1 font-mono text-[11px] font-semibold">
      <AlertOctagon className="h-3 w-3" />
      UNRELIABLE
    </Badge>
  );
}

function FreshnessTierBadge({ tier }: { tier?: string }) {
  const t = (tier || "UNKNOWN").toUpperCase();
  if (t === "FRESH") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold font-mono text-emerald-300 border border-emerald-500/20">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
        FRESH
      </span>
    );
  }
  if (t === "AGING") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold font-mono text-amber-300 border border-amber-500/20">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
        AGING
      </span>
    );
  }
  if (t === "STALE") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-rose-500/15 px-1.5 py-0.5 text-[10px] font-semibold font-mono text-rose-300 border border-rose-500/20">
        <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
        STALE
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] font-semibold font-mono text-red-300 border border-red-500/30">
      <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
      CRITICAL
    </span>
  );
}

function ConfidenceBar({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  let color = "bg-emerald-500";
  let textColor = "text-emerald-400";
  if (clamped < 35) {
    color = "bg-red-500";
    textColor = "text-red-400";
  } else if (clamped < 60) {
    color = "bg-rose-500";
    textColor = "text-rose-400";
  } else if (clamped < 75) {
    color = "bg-amber-500";
    textColor = "text-amber-400";
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[11px] font-mono">
        <span className="text-muted-foreground flex items-center gap-1">
          <Percent className="h-3 w-3 text-primary" /> Confidence Score:
        </span>
        <span className={cn("font-bold", textColor)}>{clamped.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary/80">
        <div
          className={cn("h-full transition-all duration-300", color)}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}

function QualityCard({
  title,
  noradId,
  quality,
  isPrimary,
}: {
  title: string;
  noradId: number;
  quality?: OrbitDataQualityBundle | null;
  isPrimary: boolean;
}) {
  if (!quality) {
    return (
      <div className="rounded-lg border border-border/60 bg-secondary/20 p-3.5 space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-xs text-foreground flex items-center gap-1.5">
            <SatelliteIcon className="h-3.5 w-3.5 text-primary" />
            {title} (#{noradId})
          </span>
          <Badge variant="outline" className="text-[10px]">Evaluating…</Badge>
        </div>
        <p className="text-xs text-muted-foreground">Calculating telemetry quality…</p>
      </div>
    );
  }

  const ageFormatted =
    quality.age_hours < 24
      ? `${quality.age_hours.toFixed(1)}h old`
      : `${(quality.age_hours / 24.0).toFixed(1)}d (${quality.age_hours.toFixed(0)}h) old`;

  return (
    <div className="rounded-lg border border-border/80 bg-card/60 p-3.5 space-y-3 shadow-sm backdrop-blur-sm">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-2.5">
        <div className="space-y-0.5">
          <div className="flex items-center gap-1.5">
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase",
                isPrimary
                  ? "bg-primary/20 text-primary border border-primary/30"
                  : "bg-secondary text-muted-foreground border border-border/80"
              )}
            >
              {isPrimary ? "Primary Fleet Object" : "Secondary Encounter Object"}
            </span>
            <span className="rounded bg-secondary/60 px-1 py-0.5 font-mono text-[10px] text-muted-foreground">
              {quality.orbit_regime}
            </span>
          </div>
          <p className="font-semibold text-xs text-foreground flex items-center gap-1.5">
            <SatelliteIcon className="h-3.5 w-3.5 text-primary" />
            <span>{title}</span>
            <span className="font-mono text-muted-foreground text-[11px]">#{noradId}</span>
          </p>
        </div>

        <QualityBadge quality={quality.data_quality} />
      </div>

      {/* 8-Field Matrix */}
      <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
        {/* 1. Source */}
        <div className="space-y-0.5">
          <span className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Database className="h-3 w-3 text-muted-foreground/80" /> Source
          </span>
          <div className="flex items-center gap-1">
            <span className="font-medium text-foreground text-[11px] truncate">
              {quality.source}
            </span>
            {quality.is_authoritative && (
              <span title="Authoritative Source" className="text-emerald-400">
                <ShieldCheck className="h-3 w-3 shrink-0" />
              </span>
            )}
          </div>
        </div>

        {/* 2. Age & Freshness Tier */}
        <div className="space-y-0.5">
          <span className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3 text-muted-foreground/80" /> Age & Freshness
          </span>
          <div className="flex items-center gap-1.5 font-mono text-[11px]">
            <span className="font-semibold text-foreground">{ageFormatted}</span>
            <FreshnessTierBadge tier={quality.freshness_tier} />
          </div>
        </div>

        {/* 3. Epoch */}
        <div className="space-y-0.5">
          <span className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Activity className="h-3 w-3 text-muted-foreground/80" /> Element Epoch
          </span>
          <span className="font-mono text-[11px] text-foreground">
            {formatDateTime(quality.epoch)}
          </span>
        </div>

        {/* 4. Ingestion Time */}
        <div className="space-y-0.5">
          <span className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Layers className="h-3 w-3 text-muted-foreground/80" /> Ingestion Time
          </span>
          <span className="font-mono text-[11px] text-muted-foreground">
            {formatDateTime(quality.ingestion_time)}
          </span>
        </div>

        {/* 5. Propagation Model */}
        <div className="space-y-0.5">
          <span className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Compass className="h-3 w-3 text-muted-foreground/80" /> Propagation Model
          </span>
          <span className="font-mono text-[11px] text-foreground">
            {quality.propagation_model}
          </span>
        </div>

        {/* 6. Covariance Status */}
        <div className="space-y-0.5">
          <span className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Zap className="h-3 w-3 text-muted-foreground/80" /> Covariance
          </span>
          <div className="flex items-center gap-1">
            {quality.covariance_available ? (
              <span className="font-mono text-[11px] text-emerald-400 font-medium">Available (6x6)</span>
            ) : (
              <span className="font-mono text-[11px] text-amber-300/90 font-medium">
                Not Available (SGP4 TLE)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 7 & 8: Confidence Score Gauge & Provenance */}
      <div className="border-t border-border/60 pt-2 space-y-1.5">
        <ConfidenceBar score={quality.confidence_score} />
        <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono">
          <span>Scoring Alg: DATA_QUALITY_SCORING v{quality.scoring_algorithm_version}</span>
          <span>Regime: {quality.orbit_regime}</span>
        </div>
      </div>
    </div>
  );
}

export function OrbitDataQualityPanel({
  primarySatelliteName,
  primaryNoradId,
  secondaryObjectName,
  secondaryNoradId,
  primaryQuality,
  secondaryQuality,
  className,
}: OrbitDataQualityPanelProps) {
  return (
    <div className={cn("space-y-2.5", className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Award className="h-4 w-4 text-primary" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-foreground">
            Orbit Data Quality & Freshness Assessment
          </h4>
        </div>
        <span className="text-[10px] font-mono text-muted-foreground">
          Real-time Astrodynamics Ingestion Audit
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <QualityCard
          title={primarySatelliteName}
          noradId={primaryNoradId}
          quality={primaryQuality}
          isPrimary={true}
        />
        <QualityCard
          title={secondaryObjectName}
          noradId={secondaryNoradId}
          quality={secondaryQuality}
          isPrimary={false}
        />
      </div>
    </div>
  );
}
