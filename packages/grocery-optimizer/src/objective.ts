/**
 * Resolved objective weights and unified effective-cost function for the DP optimizer.
 * All tuning flows through {@link computeEffectiveCost}; DP uses the same resolved weights.
 */

import type { OptimizationPreferences } from "./types.js";

export type ObjectiveMode = "min_cost" | "min_waste" | "balanced";

/** Normalized knobs used by the optimizer (no hidden literals in DP beyond these). */
export interface ResolvedObjectivePreferences {
  mode: ObjectiveMode;
  wastePenaltyPerUnit: number;
  storeSplitPenalty: number;
  confidencePenalty: number;
}

export interface EffectiveCostParams {
  monetaryCost: number;
  /** Surplus quantity in recipe base units (g, ml, or count). */
  leftover: number;
  /** `max(0, uniqueStoresInPurchase - 1)` for the scope being scored. */
  extraStores: number;
  /** 0 = best confidence, 1 = worst (drives confidence penalty). */
  lowConfidenceScore: number;
}

const DEFAULT_BALANCED: Omit<ResolvedObjectivePreferences, "mode"> = {
  wastePenaltyPerUnit: 0.02,
  storeSplitPenalty: 0.02,
  confidencePenalty: 0.03,
};

/**
 * Maps API preferences (including legacy `minimize_*` aliases) to concrete weights.
 */
export function resolveObjectivePreferences(
  prefs?: OptimizationPreferences,
): ResolvedObjectivePreferences {
  const raw = prefs?.objective;
  let mode: ObjectiveMode = "balanced";
  if (raw === "min_cost" || raw === "minimize_cost") mode = "min_cost";
  else if (raw === "min_waste" || raw === "minimize_waste") mode = "min_waste";
  else if (raw === "balanced") mode = "balanced";

  const wastePenaltyPerUnit =
    prefs?.wastePenaltyPerUnit ??
    (mode === "min_cost" ? 0.0005 : mode === "min_waste" ? 0.12 : DEFAULT_BALANCED.wastePenaltyPerUnit);

  const storeSplitPenalty =
    prefs?.storeSplitPenalty ??
    (mode === "min_cost" ? 0 : mode === "min_waste" ? 0.04 : DEFAULT_BALANCED.storeSplitPenalty);

  const confidencePenalty =
    prefs?.confidencePenalty ??
    (mode === "min_cost" ? 0.005 : mode === "min_waste" ? 0.06 : DEFAULT_BALANCED.confidencePenalty);

  return {
    mode,
    wastePenaltyPerUnit,
    storeSplitPenalty,
    confidencePenalty,
  };
}

/**
 * Extended objective: monetary + waste + multi-store split + low-confidence penalty.
 */
export function computeEffectiveCost(
  params: EffectiveCostParams,
  resolved: ResolvedObjectivePreferences,
): number {
  return (
    params.monetaryCost +
    resolved.wastePenaltyPerUnit * params.leftover +
    resolved.storeSplitPenalty * params.extraStores +
    resolved.confidencePenalty * params.lowConfidenceScore
  );
}

/** Maps parse/normalization confidence to a 0..1 "badness" score for penalty terms. */
export function lowConfidenceScoreFromProductConfidence(
  confidence: "high" | "medium" | "low",
): number {
  if (confidence === "high") return 0;
  if (confidence === "medium") return 0.35;
  return 0.85;
}
