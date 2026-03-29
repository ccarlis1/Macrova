/**
 * Semantic validation and confidence scoring for TinyFish search result sets.
 */

import type { ProductSearchResult } from "@nutrition-agent/tinyfish-client";

import { jaroWinkler, normalizeIngredientName } from "./ingredient_normalizer.js";
import type { AggregatedIngredient } from "./types.js";

/** Accept when dataset-level confidence is at or above this (0–1). */
export const DEFAULT_ACCEPT_CONFIDENCE = 0.45;

const MISSING_PRICE_RATIO_WARN = 0.85;
const MIN_RELEVANCE_FOR_ROW = 0.22;

function stripMoneyish(s: string | null | undefined): boolean {
  if (!s) return false;
  return /\d/.test(s);
}

export type SearchResultValidation = {
  /** True when this result set is usable without another query variant. */
  acceptable: boolean;
  /** 0–1 aggregate confidence for the response set. */
  confidence: number;
  /** Empty or effectively unusable (no rows or no usable data). */
  semanticNull: boolean;
  /** Short machine-friendly reason tags for logs. */
  tags: string[];
};

/**
 * Score a TinyFish {@link ProductSearchResult} before mapping to internal candidates.
 */
export function validateTinyFishSearchResult(
  ingredient: AggregatedIngredient,
  result: ProductSearchResult,
  options?: { acceptThreshold?: number },
): SearchResultValidation {
  const threshold = options?.acceptThreshold ?? DEFAULT_ACCEPT_CONFIDENCE;
  const products = result.products ?? [];
  const tags: string[] = [];

  if (products.length === 0) {
    return {
      acceptable: false,
      confidence: 0,
      semanticNull: true,
      tags: ["empty-set"],
    };
  }

  const target = normalizeIngredientName(ingredient.displayName).canonical.replace(/\s+/g, " ").trim();

  let named = 0;
  let priced = 0;
  let relevanceAcc = 0;
  let usableRows = 0;

  for (const p of products) {
    const name = (p.name ?? "").trim();
    if (name.length > 0) named++;

    const hasShelf = stripMoneyish(p.price ?? null);
    const hasUnit = stripMoneyish(p.unit_price ?? null);
    if (hasShelf) priced++;

    const rel =
      name.length > 0
        ? jaroWinkler(
            target,
            normalizeIngredientName(name).canonical.replace(/\s+/g, " ").trim(),
          )
        : 0;
    relevanceAcc += rel;

    if (name.length > 0 && (hasShelf || hasUnit) && rel >= MIN_RELEVANCE_FOR_ROW) {
      usableRows++;
    }
  }

  const missingPriceRatio = 1 - priced / products.length;
  if (missingPriceRatio >= MISSING_PRICE_RATIO_WARN) {
    tags.push("missing-price-heavy");
  }
  if (named === 0) {
    return {
      acceptable: false,
      confidence: 0,
      semanticNull: true,
      tags: [...tags, "no-names"],
    };
  }

  const avgRelevance = relevanceAcc / products.length;
  if (avgRelevance < 0.18) {
    tags.push("low-relevance-set");
  }

  let confidence =
    avgRelevance * 0.55 +
    (1 - Math.min(1, missingPriceRatio)) * 0.25 +
    Math.min(1, usableRows / Math.max(1, products.length)) * 0.2;

  if (usableRows === 0) {
    confidence *= 0.35;
    tags.push("no-usable-rows");
  }

  const semanticNull = priced === 0 && !products.some((p) => stripMoneyish(p.unit_price ?? null));

  const acceptable =
    !semanticNull && confidence >= threshold && usableRows > 0;

  if (semanticNull) {
    tags.push("semantic-null");
  }

  return { acceptable, confidence, semanticNull, tags };
}
