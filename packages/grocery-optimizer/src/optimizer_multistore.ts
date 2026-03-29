/**
 * Multi-store global cart optimization: per-ingredient store-tagged frontiers +
 * branch-and-bound under maxStores, with greedy fallback when the search space is too large.
 */

import { mergeErrors, type OptimizationError } from "./errors.js";
import { buildIngredientExplanation, pickRejectedAlternatives } from "./explainability.js";
import {
  computeEffectiveCost,
  resolveObjectivePreferences,
  type ResolvedObjectivePreferences,
} from "./objective.js";
import {
  optimizeIngredientDetailed,
} from "./optimizer.js";
import type {
  Explanation,
  IngredientRequirement,
  IngredientSolution,
  MultiStoreOptimizationResult,
  NormalizedProduct,
  OptimizationPreferences,
  RankedProduct,
  SelectedProduct,
} from "./types.js";

const MAX_BNB_NODES = 200_000;
const MAX_FRONTIER_PER_INGREDIENT = 16;
const DEFAULT_MAX_STORES = 4;

export interface FrontierOption {
  storeId: string;
  cost: number;
  waste: number;
  solution: IngredientSolution;
  errors: OptimizationError[];
}

function filterByStore(
  products: NormalizedProduct[],
  storeId: string,
): NormalizedProduct[] {
  return products.filter((p) => p.candidate.storeId === storeId);
}

function uniqueStoresFromCandidates(
  candidatesByIngredient: Record<string, NormalizedProduct[]>,
): string[] {
  const s = new Set<string>();
  for (const key of Object.keys(candidatesByIngredient)) {
    for (const p of candidatesByIngredient[key] ?? []) {
      s.add(p.candidate.storeId);
    }
  }
  return [...s].sort();
}

/** Pareto-efficient options on (cost, waste); lower is better for both. */
export function paretoFilter(options: FrontierOption[]): FrontierOption[] {
  if (options.length <= 1) return options.slice(0, MAX_FRONTIER_PER_INGREDIENT);
  const nd: FrontierOption[] = [];
  for (const o of options) {
    let dominated = false;
    for (const p of options) {
      if (o === p) continue;
      if (
        p.cost <= o.cost &&
        p.waste <= o.waste &&
        (p.cost < o.cost || p.waste < o.waste)
      ) {
        dominated = true;
        break;
      }
    }
    if (!dominated) nd.push(o);
  }
  return nd.slice(0, MAX_FRONTIER_PER_INGREDIENT);
}

function buildFrontierForIngredient(
  req: IngredientRequirement,
  candidates: NormalizedProduct[],
  ranked: RankedProduct[],
  prefs: OptimizationPreferences | undefined,
  storeIds: string[],
): FrontierOption[] {
  const raw: FrontierOption[] = [];
  for (const sid of storeIds) {
    const subset = filterByStore(candidates, sid);
    if (subset.length === 0) continue;
    const detail = optimizeIngredientDetailed(req, subset, ranked, prefs);
    raw.push({
      storeId: sid,
      cost: detail.solution.totalCost,
      waste: detail.solution.waste,
      solution: detail.solution,
      errors: detail.errors,
    });
  }
  return paretoFilter(raw);
}

function globalObjective(
  monetary: number,
  wasteSum: number,
  uniqueStores: number,
  resolved: ResolvedObjectivePreferences,
): number {
  const extraStores = Math.max(0, uniqueStores - 1);
  return computeEffectiveCost(
    {
      monetaryCost: monetary,
      leftover: wasteSum,
      extraStores,
      lowConfidenceScore: 0,
    },
    resolved,
  );
}

function aggregateStorePlans(
  solutions: IngredientSolution[],
): Record<string, SelectedProduct[]> {
  const plans: Record<string, SelectedProduct[]> = {};
  for (const sol of solutions) {
    for (const sp of sol.products) {
      const sid = sp.product.candidate.storeId;
      if (!plans[sid]) plans[sid] = [];
      plans[sid]!.push(sp);
    }
  }
  return plans;
}

function minConfidence(solutions: IngredientSolution[]): number {
  let c = 1;
  for (const s of solutions) {
    c = Math.min(c, s.confidence);
  }
  return c;
}

function buildExplanationsForSolutions(
  requirements: IngredientRequirement[],
  solutions: IngredientSolution[],
  rankedByIngredient: Record<string, RankedProduct[]> | undefined,
): Explanation[] {
  const out: Explanation[] = [];
  for (let i = 0; i < requirements.length; i++) {
    const req = requirements[i]!;
    const sol = solutions[i]!;
    const ranked = rankedByIngredient?.[req.canonicalKey] ?? [];
    const selectedIds = new Set(sol.products.map((p) => p.product.candidate.id));
    out.push(
      buildIngredientExplanation({
        requirement: req,
        selected: sol.products,
        totalMonetaryCost: sol.totalCost,
        waste: sol.waste,
        rankedConsidered: ranked,
        rejected: pickRejectedAlternatives(ranked, selectedIds, 2),
      }),
    );
  }
  return out;
}

/**
 * Best cart when all ingredients must come from a single store (maxStores === 1).
 */
export function optimizeSingleStoreCart(
  requirements: IngredientRequirement[],
  candidatesByIngredient: Record<string, NormalizedProduct[]>,
  prefs?: OptimizationPreferences,
  rankedByIngredient?: Record<string, RankedProduct[]>,
): MultiStoreOptimizationResult {
  const resolved = resolveObjectivePreferences(prefs);
  const stores = uniqueStoresFromCandidates(candidatesByIngredient);

  let best: {
    objective: number;
    storeId: string;
    solutions: IngredientSolution[];
    errors: OptimizationError[];
  } | null = null;

  for (const sid of stores) {
    const per: IngredientSolution[] = [];
    const roundErrors: OptimizationError[] = [];
    let ok = true;
    let totalCost = 0;
    let totalWaste = 0;
    for (const req of requirements) {
      const cands = filterByStore(
        candidatesByIngredient[req.canonicalKey] ?? [],
        sid,
      );
      const ranked = rankedByIngredient?.[req.canonicalKey] ?? [];
      const detail = optimizeIngredientDetailed(req, cands, ranked, prefs);
      roundErrors.push(...detail.errors);
      per.push(detail.solution);
      totalCost += detail.solution.totalCost;
      totalWaste += detail.solution.waste;
      if (detail.solution.partial) ok = false;
    }
    if (!ok) continue;
    const obj = globalObjective(totalCost, totalWaste, 1, resolved);
    if (!best || obj < best.objective) {
      best = { objective: obj, storeId: sid, solutions: per, errors: roundErrors };
    }
  }

  if (!best) {
    const degraded = optimizeMultiStoreGreedy(
      requirements,
      candidatesByIngredient,
      prefs,
      rankedByIngredient,
      resolved,
    );
    return {
      ...degraded,
      degraded: true,
      reason: degraded.reason ?? "no_single_store_cover",
    };
  }

  const storePlans = aggregateStorePlans(best.solutions);
  return {
    storePlans,
    totalCost: best.solutions.reduce((a, s) => a + s.totalCost, 0),
    totalWaste: best.solutions.reduce((a, s) => a + s.waste, 0),
    storesUsed: [best.storeId],
    confidence: minConfidence(best.solutions),
    perIngredient: best.solutions,
    explanations: buildExplanationsForSolutions(
      requirements,
      best.solutions,
      rankedByIngredient,
    ),
    errors: mergeErrors(best.errors),
  };
}

/**
 * Per-ingredient greedy baseline (same selection as the internal greedy fallback).
 * Monetary total only; use with {@link optimizeMultiStoreCart} to compute savings vs DP/BnB.
 */
export function computeGreedyMonetaryBaseline(
  requirements: IngredientRequirement[],
  candidatesByIngredient: Record<string, NormalizedProduct[]>,
  prefs: OptimizationPreferences | undefined,
  rankedByIngredient: Record<string, RankedProduct[]> | undefined,
): number {
  const resolved = resolveObjectivePreferences(prefs);
  return optimizeMultiStoreGreedy(
    requirements,
    candidatesByIngredient,
    prefs,
    rankedByIngredient,
    resolved,
  ).totalCost;
}

function optimizeMultiStoreGreedy(
  requirements: IngredientRequirement[],
  candidatesByIngredient: Record<string, NormalizedProduct[]>,
  prefs: OptimizationPreferences | undefined,
  rankedByIngredient: Record<string, RankedProduct[]> | undefined,
  resolved: ResolvedObjectivePreferences,
): MultiStoreOptimizationResult {
  const stores = uniqueStoresFromCandidates(candidatesByIngredient);
  const solutions: IngredientSolution[] = [];
  const errors: OptimizationError[] = [];

  for (const req of requirements) {
    const cands = candidatesByIngredient[req.canonicalKey] ?? [];
    const ranked = rankedByIngredient?.[req.canonicalKey] ?? [];
    const frontier = buildFrontierForIngredient(req, cands, ranked, prefs, stores);
    if (frontier.length === 0) {
      const empty: IngredientSolution = {
        requirement: req,
        products: [],
        totalCost: 0,
        waste: req.quantity,
        confidence: 0,
        partial: true,
        reason: "No store-specific candidates.",
      };
      solutions.push(empty);
      continue;
    }
    let pick = frontier[0]!;
    let bestLocal = globalObjective(pick.cost, pick.waste, 1, resolved);
    for (const f of frontier.slice(1)) {
      const o = globalObjective(f.cost, f.waste, 1, resolved);
      if (o < bestLocal) {
        bestLocal = o;
        pick = f;
      }
    }
    solutions.push(pick.solution);
    errors.push(...pick.errors);
  }

  const storePlans = aggregateStorePlans(solutions);
  const storesUsed = Object.keys(storePlans).sort();
  const totalCost = solutions.reduce((a, s) => a + s.totalCost, 0);
  const totalWaste = solutions.reduce((a, s) => a + s.waste, 0);
  const obj = globalObjective(totalCost, totalWaste, storesUsed.length, resolved);
  void obj;

  return {
    storePlans,
    totalCost,
    totalWaste,
    storesUsed,
    confidence: minConfidence(solutions),
    perIngredient: solutions,
    explanations: buildExplanationsForSolutions(
      requirements,
      solutions,
      rankedByIngredient,
    ),
    errors: mergeErrors(errors),
    degraded: true,
    reason: "search_space_exceeded",
  };
}

/**
 * Global multi-store optimization with branch-and-bound over per-ingredient Pareto frontiers.
 */
export function optimizeMultiStoreCart(
  requirements: IngredientRequirement[],
  candidatesByIngredient: Record<string, NormalizedProduct[]>,
  prefs?: OptimizationPreferences,
  rankedByIngredient?: Record<string, RankedProduct[]>,
): MultiStoreOptimizationResult {
  const resolved = resolveObjectivePreferences(prefs);
  const maxStores =
    prefs?.maxStores ?? (prefs?.allowMultiStore === false ? 1 : DEFAULT_MAX_STORES);

  if (requirements.length === 0) {
    return {
      storePlans: {},
      totalCost: 0,
      totalWaste: 0,
      storesUsed: [],
      confidence: 1,
      perIngredient: [],
      explanations: [],
      errors: [],
    };
  }

  if (maxStores <= 1) {
    return optimizeSingleStoreCart(
      requirements,
      candidatesByIngredient,
      prefs,
      rankedByIngredient,
    );
  }

  const stores = uniqueStoresFromCandidates(candidatesByIngredient);
  const frontiers: FrontierOption[][] = [];

  for (const req of requirements) {
    const cands = candidatesByIngredient[req.canonicalKey] ?? [];
    const ranked = rankedByIngredient?.[req.canonicalKey] ?? [];
    const f = buildFrontierForIngredient(req, cands, ranked, prefs, stores);
    frontiers.push(f);
  }

  if (frontiers.some((f) => f.length === 0)) {
    const g = optimizeMultiStoreGreedy(
      requirements,
      candidatesByIngredient,
      prefs,
      rankedByIngredient,
      resolved,
    );
    return {
      ...g,
      degraded: true,
      reason: g.reason ?? "missing_frontier",
    };
  }

  let estNodes = 1;
  for (const f of frontiers) {
    estNodes *= f.length;
    if (estNodes > MAX_BNB_NODES) {
      const g = optimizeMultiStoreGreedy(
        requirements,
        candidatesByIngredient,
        prefs,
        rankedByIngredient,
        resolved,
      );
      return { ...g, degraded: true, reason: "search_space_exceeded" };
    }
  }

  const n = requirements.length;

  let bestObj = Number.POSITIVE_INFINITY;
  let bestPick: FrontierOption[] | null = null;
  let nodes = 0;

  function dfs(
    i: number,
    acc: FrontierOption[],
    costSoFar: number,
    wasteSoFar: number,
    storeSet: Set<string>,
  ): void {
    nodes++;
    if (nodes > MAX_BNB_NODES) {
      return;
    }
    if (i === n) {
      if (storeSet.size > maxStores) {
        return;
      }
      const obj = globalObjective(costSoFar, wasteSoFar, storeSet.size, resolved);
      if (obj < bestObj) {
        bestObj = obj;
        bestPick = [...acc];
      }
      return;
    }
    for (const opt of frontiers[i]!) {
      const nextStores = new Set(storeSet);
      nextStores.add(opt.storeId);
      if (nextStores.size > maxStores) {
        continue;
      }
      acc.push(opt);
      dfs(i + 1, acc, costSoFar + opt.cost, wasteSoFar + opt.waste, nextStores);
      acc.pop();
    }
  }

  dfs(0, [], 0, 0, new Set());

  if (!bestPick || nodes > MAX_BNB_NODES) {
    const g = optimizeMultiStoreGreedy(
      requirements,
      candidatesByIngredient,
      prefs,
      rankedByIngredient,
      resolved,
    );
    return {
      ...g,
      degraded: true,
      reason: "search_space_exceeded",
    };
  }

  // Nested `dfs` assigns `bestPick`; TS does not narrow outer `let` — assert after guard.
  const chosen: FrontierOption[] = bestPick;
  const solutions = chosen.map((o: FrontierOption) => o.solution);
  const storePlans = aggregateStorePlans(solutions);
  const storesUsed = Object.keys(storePlans).sort();
  const chosenErrors = mergeErrors(...chosen.map((o) => o.errors));
  return {
    storePlans,
    totalCost: solutions.reduce((a, s) => a + s.totalCost, 0),
    totalWaste: solutions.reduce((a, s) => a + s.waste, 0),
    storesUsed,
    confidence: minConfidence(solutions),
    perIngredient: solutions,
    explanations: buildExplanationsForSolutions(
      requirements,
      solutions,
      rankedByIngredient,
    ),
    errors: chosenErrors,
  };
}
