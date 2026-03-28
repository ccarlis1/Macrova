/**
 * Flatten meal plan recipes into raw lines, then merge by canonical ingredient key + unit kind.
 */

import {
  applyFuzzySynonym,
  buildCanonicalIngredientKey,
  normalizeIngredientName,
  normalizeQuantity,
} from "./ingredient_normalizer.js";
import type {
  AggregatedIngredient,
  MealPlanInput,
  RawIngredientLine,
  SourceRecipeRef,
} from "./types.js";

export function extractIngredientLines(mealPlan: MealPlanInput): RawIngredientLine[] {
  const out: RawIngredientLine[] = [];
  const servingsMap = mealPlan.recipeServings ?? {};
  for (const recipe of mealPlan.recipes) {
    const scale = servingsMap[recipe.id] ?? 1;
    for (const ing of recipe.ingredients) {
      out.push({
        recipeId: recipe.id,
        recipeName: recipe.name,
        name: ing.name,
        quantity: ing.quantity * scale,
        unit: ing.unit,
        isToTaste: ing.isToTaste,
      });
    }
  }
  return out;
}

export interface AggregateIngredientsOptions {
  /** Extra multiplier applied after recipe servings (default 1). */
  servingsScale?: number;
  /** If set, fuzzy synonym expansion uses this Jaro–Winkler floor. */
  fuzzyThreshold?: number;
}

export function aggregateIngredients(
  lines: RawIngredientLine[],
  options?: AggregateIngredientsOptions,
): AggregatedIngredient[] {
  const globalScale = options?.servingsScale ?? 1;
  const fuzzyThreshold = options?.fuzzyThreshold ?? 0.92;

  const buckets = new Map<
    string,
    {
      totalQuantity: number;
      kind: AggregatedIngredient["normalizedUnit"];
      displayName: string;
      sources: Map<string, SourceRecipeRef>;
      isToTaste: boolean;
      minConfidence: number;
    }
  >();

  for (const line of lines) {
    let name = normalizeIngredientName(line.name);
    name = applyFuzzySynonym(name, fuzzyThreshold);
    const nq = normalizeQuantity(line.quantity * globalScale, line.unit);
    const canonicalKey = buildCanonicalIngredientKey(name.canonical);
    const mergeKey = `${canonicalKey}::${nq.kind}`;

    const displayName = name.canonical;
    const prev = buckets.get(mergeKey);
    const sources = prev?.sources ?? new Map<string, SourceRecipeRef>();
    sources.set(line.recipeId, {
      recipeId: line.recipeId,
      recipeName: line.recipeName,
    });

    if (!prev) {
      buckets.set(mergeKey, {
        totalQuantity: nq.value,
        kind: nq.kind,
        displayName,
        sources,
        isToTaste: Boolean(line.isToTaste),
        minConfidence: name.confidence,
      });
    } else {
      prev.totalQuantity += nq.value;
      prev.isToTaste = prev.isToTaste || Boolean(line.isToTaste);
      prev.minConfidence = Math.min(prev.minConfidence, name.confidence);
      buckets.set(mergeKey, {
        ...prev,
        sources,
      });
    }
  }

  const result: AggregatedIngredient[] = [];
  for (const [mergeKey, bucket] of buckets) {
    const canonicalKey = mergeKey.split("::")[0] ?? mergeKey;
    result.push({
      canonicalKey,
      displayName: bucket.displayName,
      totalQuantity: bucket.totalQuantity,
      normalizedUnit: bucket.kind,
      sourceRecipes: [...bucket.sources.values()],
      isToTaste: bucket.isToTaste,
      nameConfidence: bucket.minConfidence,
    });
  }
  return result.sort((a, b) => a.canonicalKey.localeCompare(b.canonicalKey));
}
