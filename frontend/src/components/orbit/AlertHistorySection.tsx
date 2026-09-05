import { useMemo, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Eye,
  History,
  RefreshCw,
  Search,
  ShieldAlert,
  User,
  XCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAlertHistory } from "@/hooks/useAlertHistory";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AlertStatus } from "@/types/alert";

function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  if (isNaN(diffMs)) return "—";
  if (diffMs < 0) return "Just now";
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return "Just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function ActionBadge({
  status,
  previousStatus,
}: {
  status: AlertStatus;
  previousStatus?: AlertStatus;
}) {
  const normalized = (status?.toLowerCase() || "open") as AlertStatus;
  const prevNormalized = previousStatus ? (previousStatus.toLowerCase() as AlertStatus) : null;

  let icon = <Clock className="h-3 w-3" />;
  let color = "bg-blue-500/15 text-blue-300 border-blue-500/30";
  let label = "Updated";

  if (normalized === "monitoring") {
    icon = <Eye className="h-3 w-3 text-cyan-400" />;
    color = "bg-cyan-500/15 text-cyan-300 border-cyan-500/35";
    label = "Marked Monitoring";
  } else if (normalized === "resolved") {
    icon = <CheckCircle2 className="h-3 w-3 text-emerald-400" />;
    color = "bg-emerald-500/15 text-emerald-300 border-emerald-500/35";
    label = "Resolved";
  } else if (normalized === "dismissed") {
    icon = <XCircle className="h-3 w-3 text-muted-foreground" />;
    color = "bg-secondary text-muted-foreground border-border/50";
    label = "Dismissed";
  } else if (normalized === "open" || normalized === "active") {
    icon = <ShieldAlert className="h-3 w-3 text-amber-400" />;
    color = "bg-amber-500/15 text-amber-300 border-amber-500/35";
    label = "Reopened";
  }

  return (
    <div className="flex items-center gap-1.5 font-mono text-xs">
      {prevNormalized && prevNormalized !== normalized && (
        <>
          <span className="text-[11px] text-muted-foreground capitalize">{prevNormalized}</span>
          <ArrowRight className="h-3 w-3 text-muted-foreground/60" />
        </>
      )}
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold border shadow-sm",
          color
        )}
      >
        {icon}
        <span>{label}</span>
      </span>
    </div>
  );
}

export function AlertHistorySection() {
  const { history, total, page, totalPages, isLoading, refetch, nextPage, prevPage } =
    useAlertHistory(1, 10);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const filteredHistory = useMemo(() => {
    let list = history;
    if (statusFilter !== "all") {
      list = list.filter((item) => item.newStatus?.toLowerCase() === statusFilter.toLowerCase());
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (item) =>
          item.primarySatellite.toLowerCase().includes(q) ||
          item.secondaryObject.toLowerCase().includes(q) ||
          String(item.primaryNoradId).includes(q) ||
          String(item.secondaryNoradId).includes(q) ||
          (item.operatorName && item.operatorName.toLowerCase().includes(q)) ||
          (item.notes && item.notes.toLowerCase().includes(q))
      );
    }
    return list;
  }, [history, statusFilter, searchQuery]);

  return (
    <div className="rounded-xl border border-border/80 bg-card/85 shadow-2xl backdrop-blur-md overflow-hidden">
      {/* Section Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 p-4 bg-gradient-to-r from-card to-card/60">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.2)]">
            <History className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold tracking-tight text-foreground">
                Conjunction Alert Actions History
              </h2>
              <span className="rounded-full bg-cyan-500/15 px-2 py-0.5 font-mono text-[10px] font-semibold text-cyan-400 border border-cyan-500/30">
                {total} {total === 1 ? "RECORD" : "RECORDS"}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Audit log of operator decisions, state transitions, and resolutions across conjunction screening events.
            </p>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Filter Tabs */}
          <div className="flex items-center rounded-lg border border-border/70 bg-secondary/40 p-0.5 text-xs">
            {[
              { id: "all", label: "All Actions" },
              { id: "monitoring", label: "Monitoring" },
              { id: "resolved", label: "Resolved" },
              { id: "dismissed", label: "Dismissed" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-medium transition-all",
                  statusFilter === tab.id
                    ? "bg-primary text-primary-foreground shadow-sm font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Quick Search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search satellite or operator..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 w-48 sm:w-60 rounded-lg border border-border/70 bg-secondary/50 pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-cyan-400 transition-all"
            />
          </div>

          {/* Refresh Button */}
          <Button
            size="sm"
            variant="outline"
            onClick={() => refetch()}
            disabled={isLoading}
            className="h-8 gap-1.5 text-xs font-medium border-border/70 hover:border-cyan-500/40 hover:text-cyan-300"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin text-cyan-400")} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-border/60 hover:bg-transparent bg-secondary/20">
              <TableHead className="w-56 text-xs font-semibold">Satellite Pair (A vs B)</TableHead>
              <TableHead className="w-28 text-xs font-semibold">Risk Level</TableHead>
              <TableHead className="w-48 text-xs font-semibold">Action Taken</TableHead>
              <TableHead className="w-44 text-xs font-semibold">Operator / Author</TableHead>
              <TableHead className="w-48 text-xs font-semibold">Timestamp (UTC)</TableHead>
              <TableHead className="text-xs font-semibold">Operational Notes</TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {isLoading && history.length === 0 ? (
              Array.from({ length: 4 }).map((_, idx) => (
                <TableRow key={idx} className="border-border/40">
                  <TableCell><Skeleton className="h-4 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-36" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                </TableRow>
              ))
            ) : filteredHistory.length === 0 ? (
              <TableRow className="border-transparent hover:bg-transparent">
                <TableCell colSpan={6} className="py-12 text-center">
                  <div className="mx-auto flex max-w-sm flex-col items-center justify-center text-center">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary/60 border border-border/80 text-muted-foreground mb-3">
                      <History className="h-6 w-6" />
                    </div>
                    <h3 className="text-sm font-semibold text-foreground">No Alert Actions Recorded</h3>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {searchQuery || statusFilter !== "all"
                        ? "No history entries match your current search and filter criteria."
                        : "When operators mark conjunction alerts as Monitoring, Resolved, or Dismissed, the transition history and operator audit log will be displayed here in real-time."}
                    </p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filteredHistory.map((item) => (
                <TableRow
                  key={item.id}
                  className="border-border/40 hover:bg-secondary/30 transition-colors"
                >
                  {/* Satellites */}
                  <TableCell className="py-3">
                    <div className="space-y-0.5">
                      <div className="font-medium text-xs text-white">
                        {item.primarySatellite}{" "}
                        <span className="font-mono text-[10px] text-cyan-400">
                          #{item.primaryNoradId}
                        </span>
                      </div>
                      <div className="text-[11px] text-muted-foreground flex items-center gap-1">
                        <span className="text-[10px] uppercase font-mono text-muted-foreground/80">vs</span>
                        <span>{item.secondaryObject}</span>
                        <span className="font-mono text-[10px]">#{item.secondaryNoradId}</span>
                      </div>
                    </div>
                  </TableCell>

                  {/* Risk Level */}
                  <TableCell className="py-3">
                    <RiskBadge level={item.riskLevel} />
                  </TableCell>

                  {/* Action Taken */}
                  <TableCell className="py-3">
                    <ActionBadge status={item.newStatus} previousStatus={item.previousStatus} />
                  </TableCell>

                  {/* Operator */}
                  <TableCell className="py-3">
                    <div className="flex items-center gap-1.5">
                      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-secondary/80 border border-border/60 text-muted-foreground">
                        <User className="h-3 w-3 text-cyan-400" />
                      </div>
                      <div className="truncate">
                        <span className="text-xs font-medium text-foreground truncate block">
                          {item.operatorName || "System Operator"}
                        </span>
                      </div>
                    </div>
                  </TableCell>

                  {/* Timestamp */}
                  <TableCell className="py-3 font-mono text-xs">
                    <div className="space-y-0.5">
                      <div className="text-foreground font-medium">
                        {formatDateTime(item.changedAt)}
                      </div>
                      <div className="text-[10px] text-cyan-400/90 font-normal">
                        {formatRelativeTime(item.changedAt)}
                      </div>
                    </div>
                  </TableCell>

                  {/* Notes / Rationale */}
                  <TableCell className="py-3">
                    {item.notes ? (
                      <span className="text-xs text-muted-foreground line-clamp-2" title={item.notes}>
                        {item.notes}
                      </span>
                    ) : (
                      <span className="text-xs font-mono text-muted-foreground/40 italic">
                        No operational notes
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border/60 px-4 py-3 bg-secondary/10">
          <div className="text-xs text-muted-foreground">
            Showing <strong className="text-foreground">{filteredHistory.length}</strong> of{" "}
            <strong className="text-foreground">{total}</strong> total transitions
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={prevPage}
              disabled={page <= 1 || isLoading}
              className="h-7 px-2.5 text-xs gap-1 border-border/70"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Previous</span>
            </Button>

            <span className="font-mono text-xs text-muted-foreground px-1">
              Page <strong className="text-foreground">{page}</strong> of{" "}
              <strong className="text-foreground">{totalPages}</strong>
            </span>

            <Button
              size="sm"
              variant="outline"
              onClick={nextPage}
              disabled={page >= totalPages || isLoading}
              className="h-7 px-2.5 text-xs gap-1 border-border/70"
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
