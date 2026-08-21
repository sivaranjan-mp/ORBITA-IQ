import { format, parseISO } from "date-fns";
import { Activity, ShieldAlert, Navigation } from "lucide-react";

import { useConjunctions } from "@/hooks/useConjunctions";
import { ProbabilityGauge } from "./ProbabilityGauge";
import { RiskBadge } from "@/components/dashboard/RiskBadge";
import { Button } from "@/components/ui/button";

export function ConjunctionsTable() {
  const { conjunctions, isLoading, error, triggerScreening } = useConjunctions();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-indigo-500" />
          Conjunction Events
        </h2>
        <Button onClick={triggerScreening} disabled={isLoading} variant="outline" className="gap-2">
          <Activity className="h-4 w-4" />
          Run SatGuard Screening
        </Button>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-4 dark:bg-red-900/20 text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      <div className="rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-6 py-4 font-medium">Primary Object</th>
                <th className="px-6 py-4 font-medium">Secondary Object</th>
                <th className="px-6 py-4 font-medium text-right">TCA (UTC)</th>
                <th className="px-6 py-4 font-medium text-right">Miss Distance</th>
                <th className="px-6 py-4 font-medium text-right">Rel Velocity</th>
                <th className="px-6 py-4 font-medium text-center">Probability (Pc)</th>
                <th className="px-6 py-4 font-medium">Risk Level</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    <Activity className="h-6 w-6 animate-spin mx-auto mb-2 text-indigo-500" />
                    Loading conjunctions...
                  </td>
                </tr>
              ) : conjunctions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    <Navigation className="h-6 w-6 mx-auto mb-2 opacity-50" />
                    No conjunction events detected in the lookahead window.
                  </td>
                </tr>
              ) : (
                conjunctions.map((event) => (
                  <tr key={event.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900 dark:text-white">
                        {event.primarySatelliteName}
                      </div>
                      <div className="text-xs text-slate-500">NORAD: {event.primaryNoradId}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900 dark:text-white">
                        {event.secondarySatelliteName}
                      </div>
                      <div className="text-xs text-slate-500">NORAD: {event.secondaryNoradId}</div>
                    </td>
                    <td className="px-6 py-4 text-right font-mono whitespace-nowrap">
                      {format(parseISO(event.tca), "yyyy-MM-dd HH:mm:ss")}
                    </td>
                    <td className="px-6 py-4 text-right font-mono">
                      {event.missDistanceKm.toFixed(3)} km
                    </td>
                    <td className="px-6 py-4 text-right font-mono">
                      {event.relativeVelocityKmS.toFixed(2)} km/s
                    </td>
                    <td className="px-6 py-2 flex justify-center">
                      <ProbabilityGauge probability={event.probability} size={48} />
                    </td>
                    <td className="px-6 py-4">
                      <RiskBadge level={event.riskLevel} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
