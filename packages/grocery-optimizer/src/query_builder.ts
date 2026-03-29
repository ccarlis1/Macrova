/**
 * Build prioritized retailer search query variants from aggregated ingredients.
 * Suppresses inappropriate modifiers (e.g. "boneless" on produce) to reduce query pollution.
 */

import { normalizeIngredientName } from "./ingredient_normalizer.js";
import type { AggregatedIngredient } from "./types.js";

export type IngredientQueryCategory =
  | "produce"
  | "poultry"
  | "red_meat"
  | "seafood"
  | "dairy"
  | "pantry"
  | "other";

/** Terms that strongly suggest fresh produce (not meat). */
const PRODUCE_HINT =
  /\b(onion|onions|shallot|garlic|tomato|tomatoes|lettuce|carrot|carrots|potato|potatoes|pepper|bell\s*pepper|jalapeno|apple|apples|banana|bananas|orange|oranges|lemon|lemons|lime|limes|celery|cucumber|spinach|kale|broccoli|cauliflower|mushroom|mushrooms|avocado|berry|berries|grape|grapes|watermelon|melon|zucchini|squash|asparagus|scallion|scallions|ginger|herbs?|cilantro|parsley|basil|mint)\b/i;

const POULTRY = /\b(chicken|turkey|duck|hen|poultry)\b/i;
const RED_MEAT = /\b(beef|steak|pork|lamb|veal|ground\s+beef|ground\s+pork|ribs?|brisket)\b/i;
const SEAFOOD = /\b(fish|salmon|tuna|cod|tilapia|shrimp|prawn|crab|lobster|scallop|mussel|clam)\b/i;
const DAIRY = /\b(milk|cheese|butter|yogurt|yoghurt|cream|sour\s*cream|half\s*and\s*half)\b/i;
const PANTRY =
  /\b(rice|pasta|flour|oats|cereal|quinoa|couscous|beans?\s*\(|canned|lentil|sugar|salt|oil|vinegar|stock|broth|spice)\b/i;

export function classifyIngredientQueryCategory(displayName: string): IngredientQueryCategory {
  const c = normalizeIngredientName(displayName).canonical.toLowerCase();
  if (PRODUCE_HINT.test(c)) return "produce";
  if (PANTRY.test(c)) return "pantry";
  if (DAIRY.test(c)) return "dairy";
  if (POULTRY.test(c)) return "poultry";
  if (RED_MEAT.test(c)) return "red_meat";
  if (SEAFOOD.test(c)) return "seafood";
  return "other";
}

function dedupePreserveOrder(queries: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const q of queries) {
    const t = q.trim();
    if (!t) continue;
    const k = t.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(t);
  }
  return out;
}

/**
 * Whether a trailing "boneless" (or similar cut) modifier is appropriate for this category.
 */
function allowBonelessModifier(cat: IngredientQueryCategory): boolean {
  return cat === "poultry" || cat === "red_meat" || cat === "seafood";
}

/**
 * Prioritized search query variants for TinyFish / retailer search.
 * Earlier entries are tried first (see quality-aware retry in product search).
 */
export function buildSearchQueryVariants(ingredient: AggregatedIngredient): string[] {
  const base = ingredient.displayName.trim();
  if (!base) return [];

  const cat = classifyIngredientQueryCategory(base);
  const lower = base.toLowerCase();
  const variants: string[] = [base];

  if (cat === "poultry") {
    if (lower.includes("chicken") && lower.includes("breast")) {
      variants.push("chicken breast boneless skinless");
    }
    if (!/\bboneless\b/i.test(base)) {
      variants.push(`${base} boneless`);
    }
  } else if (allowBonelessModifier(cat) && !/\bboneless\b/i.test(base)) {
    variants.push(`${base} boneless`);
  }

  return dedupePreserveOrder(variants);
}
