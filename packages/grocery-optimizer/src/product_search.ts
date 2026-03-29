/**
 * Build retailer search queries, fetch candidates through the TinyFish adapter,
 * dedupe, and rank for downstream price normalization.
 */

import { floorToBucket, QuerySearchCache } from "./caching/query_cache.js";
import { OptimizationErrorCode, err } from "./errors.js";
import { jaroWinkler, normalizeIngredientName } from "./ingredient_normalizer.js";
import { buildSearchQueryVariants } from "./query_builder.js";
import { logInfo } from "./observability/logger.js";
import {
  DEFAULT_ACCEPT_CONFIDENCE,
  validateTinyFishSearchResult,
} from "./result_validator.js";
import type {
  ProductSearchResult,
  TinyFishProductCandidate,
  TinyFishSearchAdapter,
} from "./integrations/tinyfish_client.js";
import type {
  AggregatedIngredient,
  GroceryStoreRef,
  PipelineResult,
  ProductCandidate,
  ProductCandidateSet,
  RankedProduct,
} from "./types.js";

function normalizeSig(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "")
    .trim();
}

function extractBrand(raw: Record<string, unknown> | undefined): string | null {
  if (!raw) return null;
  const b = raw["brand"] ?? raw["Brand"];
  return typeof b === "string" ? b : null;
}

function mapTinyFishProduct(
  row: TinyFishProductCandidate,
  storeId: string,
  query: string,
  seq: number,
): ProductCandidate {
  const raw = row.raw;
  return {
    id: `${storeId}:${seq}:${normalizeSig(query)}`,
    name: row.name,
    priceRaw: row.price,
    sizeRaw: row.quantity_or_size,
    unitPriceRaw: row.unit_price,
    brand: extractBrand(raw),
    storeId,
    query,
    raw,
  };
}

/**
 * @deprecated Prefer {@link buildSearchQueryVariants} from `./query_builder.js`.
 * Kept for backward compatibility — delegates to the sanitizer-aware builder.
 */
export function buildSearchQueries(ingredient: AggregatedIngredient): string[] {
  return buildSearchQueryVariants(ingredient);
}

function dedupeCandidates(candidates: ProductCandidate[]): ProductCandidate[] {
  const seen = new Map<string, ProductCandidate>();
  for (const c of candidates) {
    const key = `${c.storeId}|${normalizeSig(c.name)}|${normalizeSig(c.sizeRaw ?? "")}|${normalizeSig(c.brand ?? "")}`;
    if (!seen.has(key)) {
      seen.set(key, c);
    }
  }
  return [...seen.values()];
}

export interface ProductSearchPipelineOptions {
  maxPerQuery?: number;
  queryCache?: QuerySearchCache;
  /** Window for {@link floorToBucket} (default 5 minutes). */
  cacheBucketMs?: number;
  runId?: string;
  signal?: AbortSignal;
  /** Max query variants to try per store when results fail semantic validation (default 6). */
  maxQueryAttempts?: number;
  /** Minimum validator confidence to accept a result set without trying another variant (default {@link DEFAULT_ACCEPT_CONFIDENCE}). */
  validationAcceptThreshold?: number;
}

export async function searchProductsForIngredientResult(
  ingredient: AggregatedIngredient,
  stores: GroceryStoreRef[],
  adapter: TinyFishSearchAdapter,
  options?: ProductSearchPipelineOptions,
): Promise<PipelineResult<ProductCandidateSet>> {
  const errors: PipelineResult<ProductCandidateSet>["errors"] = [];
  const variants = buildSearchQueryVariants(ingredient);
  const maxResults = options?.maxPerQuery ?? 8;
  const collected: ProductCandidate[] = [];
  let seq = 0;
  const cacheBucketMs = options?.cacheBucketMs ?? 5 * 60_000;
  const queryCache = options?.queryCache;
  const runId = options?.runId;
  const maxAttempts = Math.min(
    variants.length,
    options?.maxQueryAttempts ?? 6,
  );
  const acceptThreshold =
    options?.validationAcceptThreshold ?? DEFAULT_ACCEPT_CONFIDENCE;

  for (const store of stores) {
    let acceptedForStore = false;
    let best: {
      res: ProductSearchResult;
      query: string;
      validation: ReturnType<typeof validateTinyFishSearchResult>;
    } | null = null;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const q = variants[attempt]!;
      const t0 = performance.now();
      const searchOpts = {
        maxResults,
        signal: options?.signal,
      };

      const fetchOnce = async (): Promise<{
        res: ProductSearchResult;
        validation: ReturnType<typeof validateTinyFishSearchResult>;
      }> => {
        let res: ProductSearchResult;
        if (queryCache) {
          res = await queryCache.getOrRevalidateWithQualityPolicy(
            {
              storeUrl: store.baseUrl,
              canonicalIngredient: `${ingredient.canonicalKey}::${normalizeSig(q)}`,
              timestampBucket: floorToBucket(Date.now(), cacheBucketMs),
            },
            async () => {
              const r = await adapter.searchProducts(q, store.baseUrl, searchOpts);
              const v = validateTinyFishSearchResult(ingredient, r, {
                acceptThreshold,
              });
              return { value: r, qualityScore: v.confidence };
            },
            { ttlMs: 10 * 60_000 },
          );
        } else {
          res = await adapter.searchProducts(q, store.baseUrl, searchOpts);
        }
        const validation = validateTinyFishSearchResult(ingredient, res, {
          acceptThreshold,
        });
        return { res, validation };
      };

      let payload: Awaited<ReturnType<typeof fetchOnce>>;
      try {
        payload = await fetchOnce();
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        if (runId !== undefined) {
          logInfo({
            runId,
            stage: "search",
            ingredientKey: ingredient.canonicalKey,
            store: store.id,
            query: q,
            durationMs: Math.round(performance.now() - t0),
            resultCount: 0,
            error: msg,
          });
        }
        errors.push(
          err(
            OptimizationErrorCode.STORE_SEARCH_QUERY_FAILED,
            `Store search failed for "${q}" at ${store.id}: ${msg}`,
            {
              ingredient: ingredient.displayName,
              severity: "warning",
            },
          ),
        );
        continue;
      }

      const { res, validation } = payload;

      if (runId !== undefined) {
        logInfo({
          runId,
          stage: "search",
          ingredientKey: ingredient.canonicalKey,
          store: store.id,
          query: q,
          durationMs: Math.round(performance.now() - t0),
          resultCount: res.products.length,
          validatorTags: validation.tags.join(","),
          validatorConfidence: validation.confidence,
        });
      }

      if (!best || validation.confidence > best.validation.confidence) {
        best = { res, query: q, validation };
      }

      if (validation.acceptable) {
        for (const p of res.products) {
          collected.push(mapTinyFishProduct(p, store.id, q, seq++));
        }
        acceptedForStore = true;
        break;
      }
    }

    if (!acceptedForStore && best && best.res.products.length > 0) {
      const { res, query: q, validation } = best;
      for (const p of res.products) {
        collected.push(mapTinyFishProduct(p, store.id, q, seq++));
      }
      if (validation.semanticNull) {
        errors.push(
          err(
            OptimizationErrorCode.SEMANTIC_NULL_RESULT,
            `Store search for "${ingredient.displayName}" at ${store.id} returned no priced products.`,
            { ingredient: ingredient.displayName, severity: "warning" },
          ),
        );
      } else if (!validation.acceptable) {
        const code = validation.tags.includes("low-relevance-set")
          ? OptimizationErrorCode.QUERY_POLLUTION
          : OptimizationErrorCode.LOW_RELEVANCE_SET;
        errors.push(
          err(
            code,
            `Low relevance matches for "${ingredient.displayName}" at ${store.id} after query variants.`,
            { ingredient: ingredient.displayName, severity: "warning" },
          ),
        );
      }
    }
  }

  const data: ProductCandidateSet = {
    ingredientKey: ingredient.canonicalKey,
    candidates: dedupeCandidates(collected),
  };

  if (data.candidates.length === 0) {
    errors.push(
      err(OptimizationErrorCode.NO_CANDIDATES, "No store products returned for this ingredient.", {
        ingredient: ingredient.displayName,
        severity: "error",
      }),
    );
  }

  return { data, errors };
}

export async function searchProductsForIngredient(
  ingredient: AggregatedIngredient,
  stores: GroceryStoreRef[],
  adapter: TinyFishSearchAdapter,
  options?: ProductSearchPipelineOptions,
): Promise<ProductCandidateSet> {
  const r = await searchProductsForIngredientResult(
    ingredient,
    stores,
    adapter,
    options,
  );
  return r.data ?? {
    ingredientKey: ingredient.canonicalKey,
    candidates: [],
  };
}

function unitCompatible(
  ingredient: AggregatedIngredient,
  product: ProductCandidate,
): boolean {
  const size = (product.sizeRaw ?? "").toLowerCase();
  if (ingredient.normalizedUnit === "mass_g") {
    return /\b(g|kg|oz|lb|lb\.|gram|ounce|pound)\b/i.test(size) || size.includes("lb");
  }
  if (ingredient.normalizedUnit === "volume_ml") {
    return /\b(ml|l|fl|oz|cup|tbsp|tsp)\b/i.test(size);
  }
  return /\b(ct|count|pack|each)\b/i.test(size) || size.length === 0;
}

export function rankAndFilterCandidates(
  candidates: ProductCandidate[],
  ingredient: AggregatedIngredient,
): RankedProduct[] {
  const target = normalizeIngredientName(ingredient.displayName).canonical;
  const ranked: RankedProduct[] = candidates.map((c) => {
    const nameSimilarity = jaroWinkler(
      target.replace(/\s+/g, " ").trim(),
      normalizeIngredientName(c.name).canonical.replace(/\s+/g, " ").trim(),
    );
    const priceComplete = Boolean(c.priceRaw && c.priceRaw.length > 0);
    const uCompat = unitCompatible(ingredient, c);
    let rankScore =
      nameSimilarity * 0.55 +
      (uCompat ? 0.25 : 0) +
      (priceComplete ? 0.2 : 0);
    if (!uCompat) rankScore *= 0.5;
    return {
      ...c,
      rankScore,
      nameSimilarity,
      unitCompatible: uCompat,
      priceComplete,
    };
  });
  ranked.sort((a, b) => b.rankScore - a.rankScore);
  return ranked;
}
