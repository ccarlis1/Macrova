/**
 * Heuristic skip list for ingredients that rarely need a TinyFish product search.
 */

import type { AggregatedIngredient } from "./types.js";

/** Normalized tokens (alphanumeric only, lowercased). */
const EXACT_SKIP = new Set([
  "water",
  "salt",
  "seasalt",
  "koshersalt",
  "tablesalt",
  "blackpepper",
  "whitepepper",
  "ice",
]);

/** Only when the full display name suggests garnish / non-shoppable quantity lines. */
const PHRASE_HINTS = ["to taste", "for garnish"];

function normalizeToken(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "")
    .trim();
}

/**
 * Returns true when this aggregated row should skip retailer search (still excluded from MILP need).
 */
export function isLowValueIngredientSkip(agg: AggregatedIngredient): boolean {
  const key = normalizeToken(agg.canonicalKey);
  const display = agg.displayName.toLowerCase().trim();
  if (key && EXACT_SKIP.has(key)) return true;
  const compactDisplay = normalizeToken(agg.displayName);
  if (compactDisplay && EXACT_SKIP.has(compactDisplay)) return true;
  for (const frag of PHRASE_HINTS) {
    if (display.includes(frag)) return true;
  }
  return false;
}
