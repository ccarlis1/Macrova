/**
 * End-to-end orchestration: aggregate → normalize (via aggregator) → search → price →
 * multi-store optimize → cart plan. Used by {@link ../run.ts}.
 */

import { randomUUID } from "node:crypto";

import { productSignature, ProductParseCache } from "./caching/product_cache.js";
import { QuerySearchCache } from "./caching/query_cache.js";
import { loadGroceryOptimizerDefaults } from "./config.js";
import { mergeErrors, type OptimizationError } from "./errors.js";
import { aggregateIngredients, extractIngredientLines } from "./ingredient_aggregator.js";
import { isLowValueIngredientSkip } from "./ingredient_low_value_skip.js";
import type { TinyFishSearchAdapter } from "./integrations/tinyfish_client.js";
import { logInfo } from "./observability/logger.js";
import { MetricsCollector } from "./observability/metrics.js";
import { PipelineTrace } from "./observability/tracing.js";
import {
  computeGreedyMonetaryBaseline,
  optimizeMultiStoreCart,
} from "./optimizer_multistore.js";
import { toIngredientRequirement } from "./optimizer.js";
import { normalizeProductPriceWithErrors } from "./price_normalizer.js";
import {
  rankAndFilterCandidates,
  searchProductsForIngredientResult,
  type ProductSearchPipelineOptions,
} from "./product_search.js";
import { buildCartPlan } from "./cart_builder.js";
import type {
  AggregatedIngredient,
  GroceryOptimizeRequest,
  GroceryOptimizeResponse,
  GroceryStoreRef,
  IngredientUnitContext,
  MealPlanInput,
  MultiStoreOptimizationResult,
  NormalizedProduct,
  OptimizationPreferences,
  RankedProduct,
  SkippedSearchIngredient,
} from "./types.js";

export type GroceryPipelineDeps = {
  adapter: TinyFishSearchAdapter;
  signal?: AbortSignal;
  /** In-memory search + parse caches for this run (default: true). */
  useCaches?: boolean;
};

function parseRequest(raw: unknown): GroceryOptimizeRequest | null {
  if (typeof raw !== "object" || raw === null) return null;
  const o = raw as Record<string, unknown>;
  const sv = o.schemaVersion;
  if (typeof sv !== "string" || !sv.startsWith("1.")) return null;
  const mealPlan = o.mealPlan;
  if (typeof mealPlan !== "object" || mealPlan === null) return null;
  const mp = mealPlan as Record<string, unknown>;
  if (!Array.isArray(mp.recipes)) return null;
  for (const r of mp.recipes) {
    if (typeof r !== "object" || r === null) return null;
    const rec = r as Record<string, unknown>;
    if (typeof rec.id !== "string" || typeof rec.name !== "string") return null;
    if (!Array.isArray(rec.ingredients)) return null;
  }
  const stores = o.stores;
  if (!Array.isArray(stores)) return null;
  for (const s of stores) {
    if (typeof s !== "object" || s === null) return null;
    const st = s as Record<string, unknown>;
    if (typeof st.id !== "string" || typeof st.baseUrl !== "string") return null;
  }
  const prefs = o.preferences;
  if (prefs !== undefined && (typeof prefs !== "object" || prefs === null)) return null;

  return {
    schemaVersion: sv,
    mealPlan: mealPlan as MealPlanInput,
    preferences: prefs as OptimizationPreferences | undefined,
    stores: stores as GroceryStoreRef[],
    runId: typeof o.runId === "string" ? o.runId : undefined,
  };
}

function normalizeMealPlan(mealPlan: MealPlanInput): MealPlanInput {
  const recipes = mealPlan.recipes.map((r) => ({
    id: r.id,
    name: r.name,
    ingredients: r.ingredients.map((i) => ({
      name: i.name,
      quantity: Number(i.quantity),
      unit: i.unit,
      isToTaste: i.isToTaste ?? false,
    })),
  }));
  const recipeServings = mealPlan.recipeServings
    ? Object.fromEntries(
        Object.entries(mealPlan.recipeServings).map(([k, v]) => [k, Number(v)]),
      )
    : undefined;
  return { id: mealPlan.id, recipes, recipeServings };
}

async function mapPool<T, R>(
  items: readonly T[],
  concurrency: number,
  mapper: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  if (items.length === 0) {
    return [];
  }
  const results: R[] = new Array(items.length);
  let next = 0;
  const workers = Math.min(Math.max(1, concurrency), items.length);
  await Promise.all(
    Array.from({ length: workers }, async () => {
      while (true) {
        const i = next++;
        if (i >= items.length) {
          break;
        }
        results[i] = await mapper(items[i]!, i);
      }
    }),
  );
  return results;
}

function failResponse(message: string, code?: string): GroceryOptimizeResponse {
  return {
    schemaVersion: "1.0",
    ok: false,
    result: null,
    error: code ? { message, code } : { message },
  };
}

/**
 * Run the full optimizer pipeline for a validated {@link GroceryOptimizeRequest}-shaped body.
 */
export async function runGroceryPipeline(
  raw: unknown,
  deps: GroceryPipelineDeps,
): Promise<GroceryOptimizeResponse> {
  const t0 = performance.now();
  const metrics = new MetricsCollector();
  const trace = new PipelineTrace();

  const req = parseRequest(raw);
  if (!req) {
    return failResponse("Invalid GroceryOptimizeRequest JSON", "INVALID_REQUEST");
  }

  const defaults = loadGroceryOptimizerDefaults();
  const stores =
    req.stores.length > 0 ? req.stores : (defaults.stores ?? []);
  if (stores.length < 1) {
    return failResponse(
      "No stores: provide `stores` in the request or defaults in grocery-optimizer.defaults.json",
      "NO_STORES",
    );
  }

  const prefs = {
    ...(defaults.preferences ?? {}),
    ...(req.preferences ?? {}),
  };

  const runId = req.runId ?? randomUUID();
  const useCaches = deps.useCaches !== false;
  const queryCache = useCaches ? new QuerySearchCache() : undefined;
  const parseCache = useCaches ? new ProductParseCache() : undefined;

  logInfo({ runId, stage: "pipeline_start", message: "grocery pipeline" });

  const spanAgg = trace.begin("aggregation", runId);
  const mealPlan = normalizeMealPlan(req.mealPlan);

  const lines = extractIngredientLines(mealPlan);
  const aggregated = aggregateIngredients(lines, {
    fuzzyThreshold: prefs.fuzzyMatchThreshold ?? 0.92,
  });
  trace.end(spanAgg);

  const toOptimize = aggregated.filter((a) => !a.isToTaste);

  const candidatesByIngredient: Record<string, NormalizedProduct[]> = {};
  const rankedByIngredient: Record<string, RankedProduct[]> = {};
  const stageErrors: OptimizationError[] = [];
  const skippedIngredients: SkippedSearchIngredient[] = [];
  const toSearch: AggregatedIngredient[] = [];

  for (const a of toOptimize) {
    if (isLowValueIngredientSkip(a)) {
      skippedIngredients.push({
        canonicalKey: a.canonicalKey,
        displayName: a.displayName,
        reason: "low_value",
      });
      candidatesByIngredient[a.canonicalKey] = [];
      rankedByIngredient[a.canonicalKey] = [];
      continue;
    }
    toSearch.push(a);
  }

  const requirements = toSearch.map(toIngredientRequirement);

  const maxRanked = Math.max(16, (prefs.maxCandidatesPerQuery ?? 8) * 3);

  const searchOpts: ProductSearchPipelineOptions = {
    maxPerQuery: prefs.maxCandidatesPerQuery ?? 8,
    queryCache,
    runId,
    cacheBucketMs: 5 * 60_000,
    signal: deps.signal,
  };

  let parseOk = 0;
  let parseTotal = 0;
  let parseCacheHits = 0;

  const searchConcurrency = prefs.searchConcurrency ?? defaults.preferences?.searchConcurrency ?? 3;

  const spanSearch = trace.begin("search", runId, {
    ingredientCount: toSearch.length,
    searchConcurrency,
  });

  const searchPhase = await mapPool(
    toSearch,
    searchConcurrency,
    async (agg) => {
      const tSearch = performance.now();
      const searchRes = await searchProductsForIngredientResult(
        agg,
        stores,
        deps.adapter,
        searchOpts,
      );
      return { agg, searchRes, tSearch };
    },
  );

  for (const { agg, searchRes, tSearch } of searchPhase) {
    if (searchRes.errors.length > 0) {
      stageErrors.push(...searchRes.errors);
    }
    const set = searchRes.data;
    if (!set) {
      candidatesByIngredient[agg.canonicalKey] = [];
      rankedByIngredient[agg.canonicalKey] = [];
      logInfo({
        runId,
        stage: "search_done",
        ingredientKey: agg.canonicalKey,
        durationMs: Math.round(performance.now() - tSearch),
        resultCount: 0,
      });
      continue;
    }

    const ranked = rankAndFilterCandidates(set.candidates, agg).slice(0, maxRanked);
    rankedByIngredient[agg.canonicalKey] = ranked;

    const unitCtx: IngredientUnitContext = {
      kind: agg.normalizedUnit,
    };

    const normalized: NormalizedProduct[] = [];
    for (const r of ranked) {
      parseTotal++;
      const cacheKey = `${productSignature(r)}|${agg.canonicalKey}|${unitCtx.kind}`;
      if (parseCache) {
        const hit = parseCache.get(cacheKey);
        if (hit) {
          parseCacheHits++;
          normalized.push(hit);
          if (!hit.lowConfidence) parseOk++;
          continue;
        }
      }
      const pr = normalizeProductPriceWithErrors(r, unitCtx, {
        ingredientKey: agg.canonicalKey,
        ingredientDisplayName: agg.displayName,
      });
      if (pr.data) {
        normalized.push(pr.data);
        if (parseCache) parseCache.set(cacheKey, pr.data);
        if (!pr.data.lowConfidence) parseOk++;
      }
      if (pr.errors.length > 0) {
        stageErrors.push(...pr.errors);
      }
    }

    candidatesByIngredient[agg.canonicalKey] = normalized;

    logInfo({
      runId,
      stage: "search_done",
      ingredientKey: agg.canonicalKey,
      durationMs: Math.round(performance.now() - tSearch),
      resultCount: set.candidates.length,
    });
  }

  trace.end(spanSearch);

  if (queryCache) {
    const st = queryCache.hitStats();
    metrics.recordSearchCacheHits(st.hits, st.misses);
  }
  metrics.recordParseCacheHits(parseCacheHits);

  logInfo({
    runId,
    stage: "search_pool",
    message: "ingredient search phase complete",
    workers: searchConcurrency,
    searched: toSearch.length,
    skippedLowValue: skippedIngredients.length,
  });

  const spanOpt = trace.begin("optimization", runId);
  const multi = optimizeMultiStoreCart(
    requirements,
    candidatesByIngredient,
    prefs,
    rankedByIngredient,
  );
  trace.end(spanOpt);

  const mergedErrors = mergeErrors(multi.errors, stageErrors);
  const multiWithErrors: MultiStoreOptimizationResult = {
    ...multi,
    errors: mergedErrors,
  };

  const storeUrlById: Record<string, string> = Object.fromEntries(
    stores.map((s) => [s.id, s.baseUrl]),
  );
  const spanCart = trace.begin("cart", runId);
  const cartPlan = buildCartPlan(multiWithErrors, storeUrlById, runId);
  trace.end(spanCart);

  const elapsed = performance.now() - t0;
  metrics.recordOptimizationLatency(elapsed);

  const reqQty = requirements.reduce((a, r) => a + Math.max(0, r.quantity), 0);
  const wasteW = multiWithErrors.totalWaste;
  metrics.recordWastePercent(reqQty > 0 ? (100 * wasteW) / reqQty : 0);

  const met = requirements.length;
  const satisfied = multiWithErrors.perIngredient.filter((p) => !p.partial).length;
  metrics.recordCoverageRate(met > 0 ? satisfied / met : 1);

  metrics.recordAvgStoresPerCart(
    multiWithErrors.storesUsed.length > 0 ? multiWithErrors.storesUsed.length : 0,
  );

  metrics.recordPriceParseSuccessRate(parseTotal > 0 ? parseOk / parseTotal : 0);

  const greedyCost = computeGreedyMonetaryBaseline(
    requirements,
    candidatesByIngredient,
    prefs,
    rankedByIngredient,
  );
  const gap = Math.max(0, greedyCost - multiWithErrors.totalCost);
  metrics.recordCostGapVsGreedy(Number.isFinite(gap) ? gap : 0);

  const successResult = {
    runId,
    mealPlanId: mealPlan.id,
    multiStoreOptimization: multiWithErrors,
    cartPlan,
    metrics: metrics.snapshot(),
    stores,
    pipelineTrace: trace.spansSnapshot(),
    ...(skippedIngredients.length > 0 ? { skippedIngredients } : {}),
  };

  const finalMetrics = metrics.snapshot();
  logInfo({
    runId,
    stage: "pipeline_done",
    durationMs: Math.round(elapsed),
    message: "grocery pipeline complete",
    searchCacheHits: finalMetrics.searchCacheHits,
    searchCacheMisses: finalMetrics.searchCacheMisses,
    parseCacheHits: finalMetrics.parseCacheHits,
    skippedIngredients: skippedIngredients.length,
  });

  return {
    schemaVersion: "1.0",
    ok: true,
    result: successResult,
    error: null,
  };
}
