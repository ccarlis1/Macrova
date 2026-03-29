/**
 * Single-store, per-ingredient unbounded knapsack with resolved objective weights.
 * Effective cost uses {@link computeEffectiveCost} for terminal selection; transitions
 * include per-pack monetary cost + confidence penalty (no magic literals in DP).
 */

import { OptimizationErrorCode, err, mergeErrors, type OptimizationError } from "./errors.js";
import {
  buildIngredientExplanation,
  pickRejectedAlternatives,
} from "./explainability.js";
import {
  computeEffectiveCost,
  lowConfidenceScoreFromProductConfidence,
  resolveObjectivePreferences,
  type ResolvedObjectivePreferences,
} from "./objective.js";
import type {
  AggregatedIngredient,
  Explanation,
  IngredientOptimizationResult,
  IngredientRequirement,
  IngredientSolution,
  NormalizedProduct,
  NormalizedProductOffer,
  OptimizationPreferences,
  OptimizationResult,
  RankedProduct,
  SelectedProduct,
} from "./types.js";

const SCALE = 1000;

export function toIngredientRequirement(
  agg: AggregatedIngredient,
): IngredientRequirement {
  return {
    canonicalKey: agg.canonicalKey,
    displayName: agg.displayName,
    quantity: agg.totalQuantity,
    kind: agg.normalizedUnit,
  };
}

function toScaled(x: number): number {
  return Math.max(0, Math.round(x * SCALE));
}

function fromScaled(n: number): number {
  return n / SCALE;
}

export function buildOffersFromNormalized(
  products: NormalizedProduct[],
): NormalizedProductOffer[] {
  const offers: NormalizedProductOffer[] = [];
  for (const p of products) {
    const qty = p.normalizedPackQuantity;
    const price = p.totalPackPrice;
    if (
      qty !== null &&
      price !== null &&
      qty > 0 &&
      price > 0 &&
      !p.lowConfidence
    ) {
      offers.push({
        product: p,
        packQuantity: qty,
        packPrice: price,
      });
    }
  }
  return offers;
}

export function buildOffersFromNormalizedLenient(
  products: NormalizedProduct[],
): NormalizedProductOffer[] {
  const strict = buildOffersFromNormalized(products);
  if (strict.length > 0) return strict;
  const offers: NormalizedProductOffer[] = [];
  for (const p of products) {
    const qty = p.normalizedPackQuantity;
    const price = p.totalPackPrice;
    if (qty !== null && price !== null && qty > 0 && price > 0) {
      offers.push({ product: p, packQuantity: qty, packPrice: price });
    }
  }
  return offers;
}

function transitionCost(
  o: NormalizedProductOffer,
  resolved: ResolvedObjectivePreferences,
): number {
  const conf = lowConfidenceScoreFromProductConfidence(o.product.confidence);
  return (
    o.packPrice +
    resolved.confidencePenalty * conf
  );
}

export function optimizeIngredientDetailed(
  requirement: IngredientRequirement,
  candidates: NormalizedProduct[],
  rankedConsidered: RankedProduct[],
  prefs?: OptimizationPreferences,
  incomingErrors?: OptimizationError[],
): IngredientOptimizationResult {
  const resolved = resolveObjectivePreferences(prefs);
  const errors = mergeErrors(incomingErrors);

  if (requirement.quantity <= 0) {
    const solution: IngredientSolution = {
      requirement,
      products: [],
      totalCost: 0,
      waste: 0,
      confidence: 1,
      partial: false,
    };
    return {
      solution,
      errors,
      explanation: buildIngredientExplanation({
        requirement,
        selected: [],
        totalMonetaryCost: 0,
        waste: 0,
        rankedConsidered,
        rejected: pickRejectedAlternatives(rankedConsidered, new Set(), 2),
      }),
    };
  }

  const offers = buildOffersFromNormalizedLenient(candidates);
  if (offers.length === 0) {
    errors.push(
      err(OptimizationErrorCode.NO_CANDIDATES, "No priced pack sizes for this ingredient.", {
        ingredient: requirement.displayName,
        severity: "error",
      }),
    );
    const solution: IngredientSolution = {
      requirement,
      products: [],
      totalCost: 0,
      waste: requirement.quantity,
      confidence: 0,
      partial: true,
      reason: "No priced pack sizes for this ingredient.",
    };
    return {
      solution,
      errors,
      explanation: buildIngredientExplanation({
        requirement,
        selected: [],
        totalMonetaryCost: 0,
        waste: requirement.quantity,
        rankedConsidered,
        rejected: pickRejectedAlternatives(rankedConsidered, new Set(), 2),
      }),
    };
  }

  const R = toScaled(requirement.quantity);
  let maxQ = 0;
  for (const o of offers) {
    maxQ = Math.max(maxQ, toScaled(o.packQuantity));
  }
  const T_MAX = R + maxQ * 24;

  const inf = Number.POSITIVE_INFINITY;
  const dp: number[] = new Array(T_MAX + 1).fill(inf);
  const choice: Int32Array = new Int32Array(T_MAX + 1).fill(-1);

  dp[0] = 0;

  for (let t = 1; t <= T_MAX; t++) {
    for (let i = 0; i < offers.length; i++) {
      const o = offers[i]!;
      const q = toScaled(o.packQuantity);
      if (q <= 0) continue;
      const prev = t >= q ? t - q : -1;
      if (prev < 0) continue;
      const step = transitionCost(o, resolved);
      const cand = dp[prev]! + step;
      if (cand < dp[t]!) {
        dp[t] = cand;
        choice[t] = i;
      }
    }
  }

  let bestT = -1;
  let bestObj = inf;
  for (let t = R; t <= T_MAX; t++) {
    if (dp[t]! === inf) continue;
    const waste = fromScaled(t - R);
    const obj = computeEffectiveCost(
      {
        monetaryCost: dp[t]!,
        leftover: waste,
        extraStores: 0,
        lowConfidenceScore: 0,
      },
      resolved,
    );
    if (obj < bestObj) {
      bestObj = obj;
      bestT = t;
    }
  }

  if (bestT < 0) {
    const sorted = [...offers].sort(
      (a, b) => a.packPrice / a.packQuantity - b.packPrice / b.packQuantity,
    );
    const pick = sorted[0]!;
    const packs = Math.max(1, Math.ceil(requirement.quantity / pick.packQuantity));
    const totalQty = packs * pick.packQuantity;
    const waste = Math.max(0, totalQty - requirement.quantity);
    const totalMonetary = packs * pick.packPrice;
    errors.push(
      err(
        OptimizationErrorCode.INSUFFICIENT_QUANTITY,
        "Could not reach required quantity with discrete pack sizes; applied cheapest-SKU fallback.",
        { ingredient: requirement.displayName, severity: "error" },
      ),
    );
    if (pick.product.lowConfidence) {
      errors.push(
        err(OptimizationErrorCode.LOW_CONFIDENCE_MATCH, "Fallback SKU has low parsing confidence.", {
          ingredient: requirement.displayName,
          severity: "warning",
        }),
      );
    }
    const solution: IngredientSolution = {
      requirement,
      products: [{ product: pick.product, packCount: packs }],
      totalCost: totalMonetary,
      waste,
      confidence:
        pick.product.confidence === "high" ? 1 : pick.product.confidence === "medium" ? 0.75 : 0.45,
      partial: true,
      reason: "DP could not reach required quantity with discrete pack sizes; used cheapest SKU fallback.",
    };
    const selectedIds = new Set(solution.products.map((p) => p.product.candidate.id));
    return {
      solution,
      errors,
      explanation: buildIngredientExplanation({
        requirement,
        selected: solution.products,
        totalMonetaryCost: totalMonetary,
        waste,
        rankedConsidered,
        rejected: pickRejectedAlternatives(rankedConsidered, selectedIds, 2),
      }),
    };
  }

  const packCounts = new Map<number, number>();
  let cur = bestT;
  let guard = 0;
  while (cur > 0 && guard++ < T_MAX + 5) {
    const i = choice[cur];
    if (i === undefined || i < 0) break;
    const o = offers[i]!;
    const q = toScaled(o.packQuantity);
    if (q <= 0 || cur < q) break;
    packCounts.set(i, (packCounts.get(i) ?? 0) + 1);
    cur -= q;
  }

  const products: SelectedProduct[] = [];
  let totalCost = 0;
  let minConf = 1;
  for (const [i, n] of packCounts) {
    const o = offers[i]!;
    products.push({ product: o.product, packCount: n });
    totalCost += n * o.packPrice;
    minConf = Math.min(
      minConf,
      o.product.confidence === "high" ? 1 : o.product.confidence === "medium" ? 0.75 : 0.45,
    );
  }

  const waste = Math.max(0, fromScaled(bestT) - requirement.quantity);

  if (products.some((p) => p.product.lowConfidence)) {
    errors.push(
      err(OptimizationErrorCode.LOW_CONFIDENCE_MATCH, "Selected SKU includes low-confidence price/size parse.", {
        ingredient: requirement.displayName,
        severity: "warning",
      }),
    );
  }

  const solution: IngredientSolution = {
    requirement,
    products,
    totalCost,
    waste,
    confidence: minConf,
    partial: false,
  };

  const selectedIds = new Set(products.map((p) => p.product.candidate.id));
  return {
    solution,
    errors,
    explanation: buildIngredientExplanation({
      requirement,
      selected: products,
      totalMonetaryCost: totalCost,
      waste,
      rankedConsidered,
      rejected: pickRejectedAlternatives(rankedConsidered, selectedIds, 2),
    }),
  };
}

export function optimizeIngredient(
  requirement: IngredientRequirement,
  candidates: NormalizedProduct[],
  prefs?: OptimizationPreferences,
  rankedConsidered: RankedProduct[] = [],
): IngredientSolution {
  return optimizeIngredientDetailed(
    requirement,
    candidates,
    rankedConsidered,
    prefs,
  ).solution;
}

export function optimizeCart(
  requirements: IngredientRequirement[],
  candidatesByIngredient: Record<string, NormalizedProduct[]>,
  prefs?: OptimizationPreferences,
  rankedByIngredient?: Record<string, RankedProduct[]>,
  incomingErrorsByIngredient?: Record<string, OptimizationError[]>,
): OptimizationResult {
  const perIngredient: IngredientSolution[] = [];
  const selectedProducts: SelectedProduct[] = [];
  let totalCost = 0;
  const storeBreakdown: Record<string, number> = {};
  const unmet: string[] = [];
  const explanations: Explanation[] = [];
  const errors: OptimizationError[] = [];

  for (const req of requirements) {
    const cands = candidatesByIngredient[req.canonicalKey] ?? [];
    const ranked = rankedByIngredient?.[req.canonicalKey] ?? [];
    const incoming = incomingErrorsByIngredient?.[req.canonicalKey];
    const detail = optimizeIngredientDetailed(req, cands, ranked, prefs, incoming);
    perIngredient.push(detail.solution);
    explanations.push(detail.explanation);
    errors.push(...detail.errors);
    totalCost += detail.solution.totalCost;
    if (detail.solution.partial) {
      unmet.push(req.canonicalKey);
    }
    for (const sp of detail.solution.products) {
      selectedProducts.push(sp);
      const sid = sp.product.candidate.storeId;
      storeBreakdown[sid] =
        (storeBreakdown[sid] ?? 0) + sp.packCount * (sp.product.totalPackPrice ?? 0);
    }
  }

  return {
    selectedProducts,
    totalCost,
    storeBreakdown,
    unmetRequirements: unmet,
    perIngredient,
    explanations,
    errors,
  };
}
