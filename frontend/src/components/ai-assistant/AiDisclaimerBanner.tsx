import { ShieldAlert } from "lucide-react";

export function AiDisclaimerBanner() {
  return (
    <div className="relative overflow-hidden rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200 shadow-sm backdrop-blur-md">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-amber-500/20 text-amber-400">
          <ShieldAlert className="h-5 w-5" />
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-amber-300">
              Operator Advisory Notice — Qualitative Guidance Only
            </h3>
            <span className="rounded bg-amber-500/25 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-200">
              Not a Certified Maneuver Solution
            </span>
          </div>
          <p className="text-xs text-amber-200/90 leading-relaxed">
            AI-generated suggestions are designed exclusively for qualitative operator review and situational reasoning. An LLM reasoning over orbital telemetry is not a substitute for certified Flight Dynamics System (FDS) astrodynamics propagators or official Space Command Conjunction Data Messages (CDMs). All tactical thruster firings must be verified using certified ground software and secondary screening prior to command upload.
          </p>
        </div>
      </div>
    </div>
  );
}
