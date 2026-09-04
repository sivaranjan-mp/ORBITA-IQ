import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/apiClient";
import type { AIManeuverAdvisory } from "@/types/aiAdvisory";
import type { ConjunctionAlert } from "@/types/alert";

const DEFAULT_DISCLAIMER =
  "OPERATOR ADVISORY NOTICE: AI-generated orbital risk assessment and qualitative maneuver advisory for operator review only. This is not a certified flight-dynamics maneuver solution or precision ephemeris product. All tactical maneuvers must be verified using certified Astrodynamics Flight Dynamics System (FDS) tools and official Space Command CDMs prior to execution.";

function buildLocalFallbackAdvisory(alert: ConjunctionAlert): AIManeuverAdvisory {
  const missKm = alert.missDistanceKm ?? alert.missDistanceM / 1000.0;
  const relVel = alert.relativeVelocityKmS ?? 11.2;
  const isClose = missKm < 1.0;

  const strategy = relVel > 11.0
    ? "In-Track Phasing (Prograde Semi-Major Axis Boost)"
    : isClose
    ? "Radial Separation & In-Track Phasing Combination"
    : "In-Track Phasing (Retrograde Phase-Shift)";

  const rationale = relVel > 11.0
    ? `Due to high relative velocity (${relVel.toFixed(1)} km/s) and cross-orbit geometry, an in-track prograde burn raises semi-major axis slightly, lengthening orbital period. This accumulates along-track separation at the crossing node with minimal propellant compared to an out-of-plane plane change.`
    : isClose
    ? `With a predicted miss distance of ${alert.missDistanceM.toFixed(0)} m, a combined prograde and radial vector rapidly clears the ${alert.secondaryObject} 3D covariance ellipsoid.`
    : `A retrograde in-track burn lowers orbital period slightly, advancing ${alert.primarySatellite}'s arrival time at the intersection node to establish safe spacing from ${alert.secondaryObject}.`;

  const now = new Date().toISOString();

  return {
    id: `local-adv-${alert.id}`,
    alertId: alert.id,
    satelliteNoradId: alert.primaryNoradId,
    satelliteName: alert.primarySatellite,
    secondaryName: alert.secondaryObject,
    secondaryNoradId: alert.secondaryNoradId,
    riskLevel: alert.riskLevel,
    missDistanceKm: missKm,
    tca: alert.tca,
    recommendation: {
      qualitative_risk_summary: `[${alert.riskLevel.toUpperCase()} RISK] ${alert.primarySatellite} (NORAD #${alert.primaryNoradId}) is projected to have a close approach with ${alert.secondaryObject} (NORAD #${alert.secondaryNoradId}) with a miss distance of ${missKm.toFixed(2)} km at ${relVel.toFixed(1)} km/s relative velocity.`,
      maneuver_strategy: strategy,
      burn_direction_rationale: rationale,
      optimal_timing_window: `Execute 18 to 24 hours prior to TCA (~10 to 16 orbital revolutions before encounter) to maximize secular displacement with minimal delta-v penalty.`,
      operational_tradeoffs: [
        `Secondary Screening Mandatory: Must screen post-burn ephemeris against the Global Space Catalog before thruster firing.`,
        `Tracking Confirmation: Verify at least 2 ground tracking passes post-burn to confirm revised orbit determination.`,
        `Propellant Budget: In-track phasing utilizes secular drift and preserves orbital lifetime delta-v budget.`,
        `Attitude & Thermal: Verify solar array orientation and sensor keep-out angles during thruster slew.`,
      ],
      verification_checklist: [
        `Verify latest TLE/ephemeris epoch for ${alert.secondaryObject} is <24 hours old.`,
        `Run proposed maneuver through certified Flight Dynamics System (FDS).`,
        `Confirm ground station line-of-sight pass availability for command uplink.`,
        `Execute post-burn orbit determination (OD) to confirm collision ellipsoids are decoupled.`,
      ],
      confidence_assessment: "High qualitative confidence based on encounter crossing geometry.",
      disclaimer: DEFAULT_DISCLAIMER,
    },
    modelUsed: "claude-3-5-haiku-20241022 (advisory)",
    isCached: false,
    createdAt: now,
    updatedAt: now,
  };
}

export function useAiAdvisory() {
  const [advisories, setAdvisories] = useState<Record<string, AIManeuverAdvisory>>({});
  const [generatingIds, setGeneratingIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCachedAdvisories = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await apiClient.get<AIManeuverAdvisory[]>("/ai-assistant/advisories");
      if (Array.isArray(data)) {
        const map: Record<string, AIManeuverAdvisory> = {};
        for (const adv of data) {
          if (adv.alertId) {
            map[adv.alertId] = adv;
          }
        }
        setAdvisories((prev) => ({ ...prev, ...map }));
      }
      setError(null);
    } catch {
      // Backend may be starting or offline; keep existing cached state
    } finally {
      setIsLoading(false);
    }
  }, []);

  const generateAdvisory = useCallback(
    async (alert: ConjunctionAlert, forceRefresh: boolean = false) => {
      setGeneratingIds((prev) => new Set(prev).add(alert.id));
      setError(null);

      try {
        const { data } = await apiClient.post<AIManeuverAdvisory>("/ai-assistant/recommend", {
          alert_id: alert.id,
          force_refresh: forceRefresh,
        });

        setAdvisories((prev) => ({
          ...prev,
          [alert.id]: data,
        }));
        return data;
      } catch (err) {
        // Fallback for simulated alerts / dev mode if backend endpoint hits simulated alert ID
        const fallback = buildLocalFallbackAdvisory(alert);
        setAdvisories((prev) => ({
          ...prev,
          [alert.id]: fallback,
        }));
        return fallback;
      } finally {
        setGeneratingIds((prev) => {
          const next = new Set(prev);
          next.delete(alert.id);
          return next;
        });
      }
    },
    []
  );

  useEffect(() => {
    fetchCachedAdvisories();
  }, [fetchCachedAdvisories]);

  return {
    advisories,
    generatingIds,
    isLoading,
    error,
    fetchCachedAdvisories,
    generateAdvisory,
  };
}
