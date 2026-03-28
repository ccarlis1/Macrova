/**
 * Single-store, per-ingredient unbounded knapsack:
 * minimize sum(price) + wastePenalty * max(0, purchasedQty - requiredQty)
 * subject to purchasedQty >= requiredQty.
 *
 * Quantities are discretized to integer "micro-units" for stable DP transitions.
 */

import type {
  AggregatedIngredient,
  IngredientRequirement,
  IngredientSolution,
  NormalizedProduct,
  NormalizedProductOffer,
  OptimizationPreferences,
  OptimizationResult,
  SelectedProduct,
} from "./types.js";

const DEFAULT_WASTE_PENALTY = 0.02;
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

/** Include low-confidence SKUs when nothing else is available. */
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

export function optimizeIngredient(
  requirement: IngredientRequirement,
  candidates: NormalizedProduct[],
  prefs?: OptimizationPreferences,
): IngredientSolution {
  const wasteW = prefs?.wastePenaltyPerUnit ?? DEFAULT_WASTE_PENALTY;
  if (requirement.quantity <= 0) {
    return {
      requirement,
      products: [],
      totalCost: 0,
      waste: 0,
      confidence: 1,
      partial: false,
    };
  }

  const offers = buildOffersFromNormalizedLenient(candidates);
  if (offers.length === 0) {
    return {
      requirement,
      products: [],
      totalCost: 0,
      waste: requirement.quantity,
      confidence: 0,
      partial: true,
      reason: "No priced pack sizes for this ingredient.",
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
      const cand = dp[prev]! + o.packPrice;
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
    const obj = dp[t]! + wasteW * waste;
    if (obj < bestObj) {
      bestObj = obj;
      bestT = t;
    }
  }

  if (bestT < 0) {
    // Fallback: single cheapest unit-price * required qty heuristic
    const sorted = [...offers].sort(
      (a, b) => a.packPrice / a.packQuantity - b.packPrice / b.packQuantity,
    );
    const pick = sorted[0]!;
    const packs = Math.max(1, Math.ceil(requirement.quantity / pick.packQuantity));
    const totalQty = packs * pick.packQuantity;
    const waste = Math.max(0, totalQty - requirement.quantity);
    return {
      requirement,
      products: [{ product: pick.product, packCount: packs }],
      totalCost: packs * pick.packPrice,
      waste,
      confidence: pick.product.confidence === "high" ? 0.7 : 0.4,
      partial: true,
      reason: "DP could not reach required quantity with discrete pack sizes; used cheapest SKU fallback.",
    };
  }

  // Reconstruct unbounded knapsack counts by backtracking greedy from bestT
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

  return {
    requirement,
    products,
    totalCost,
    waste,
    confidence: minConf,
    partial: false,
  };
}

export function optimizeCart(
  requirements: IngredientRequirement[],
  candidatesByIngredient: Record<string, NormalizedProduct[]>,
  prefs?: OptimizationPreferences,
): OptimizationResult {
  const perIngredient: IngredientSolution[] = [];
  const selectedProducts: SelectedProduct[] = [];
  let totalCost = 0;
  const storeBreakdown: Record<string, number> = {};
  const unmet: string[] = [];

  for (const req of requirements) {
    const cands = candidatesByIngredient[req.canonicalKey] ?? [];
    const sol = optimizeIngredient(req, cands, prefs);
    perIngredient.push(sol);
    totalCost += sol.totalCost;
    if (sol.partial) {
      unmet.push(req.canonicalKey);
    }
    for (const sp of sol.products) {
      selectedProducts.push(sp);
      const sid = sp.product.candidate.storeId;
      storeBreakdown[sid] = (storeBreakdown[sid] ?? 0) + sp.packCount * (sp.product.totalPackPrice ?? 0);
    }
  }

  return {
    selectedProducts,
    totalCost,
    storeBreakdown,
    unmetRequirements: unmet,
    perIngredient,
  };
}
