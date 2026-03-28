/**
 * Canonicalize ingredient names and convert quantities to base units (g, ml, count).
 * Volume ↔ mass is only applied when density is supplied; otherwise flagged ambiguous.
 */

import type {
  IngredientMeta,
  NormalizedName,
  NormalizedQuantity,
  NormalizedUnitKind,
} from "./types.js";
import { MASS_TO_G, VOLUME_TO_ML } from "./unit_constants.js";

/** Exact synonym map (lowercased keys). */
export const INGREDIENT_SYNONYMS: Record<string, string> = {
  "chicken breasts": "chicken breast",
  "boneless skinless chicken breast": "chicken breast",
  "boneless skinless chicken breasts": "chicken breast",
  "green onion": "green onions",
  "scallion": "green onions",
  "scallions": "green onions",
};

const COUNT_UNITS = new Set([
  "unit",
  "units",
  "each",
  "ct",
  "count",
  "whole",
  "clove",
  "cloves",
  "large",
  "medium",
  "small",
  "",
]);

function normalizeUnitToken(unit: string): string {
  return unit.trim().toLowerCase().replace(/\./g, "");
}

export function buildCanonicalIngredientKey(name: string): string {
  const n = normalizeIngredientName(name).canonical;
  return n.replace(/\s+/g, " ").trim();
}

/** Lowercase, trim, strip punctuation (keep spaces and alphanumerics). */
export function normalizeIngredientName(raw: string): NormalizedName {
  const lower = raw
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "");
  const stripped = lower.replace(/[^\p{L}\p{N}\s]/gu, " ");
  const collapsed = stripped.replace(/\s+/g, " ").trim();
  const synonymHit = INGREDIENT_SYNONYMS[collapsed];
  const canonical = synonymHit ?? collapsed;
  const key = canonical.replace(/\s+/g, " ");
  return {
    canonical,
    key,
    confidence: synonymHit ? 1 : 0.95,
  };
}

/** Exported for product ranking / tests (same metric as fuzzy synonyms). */
export function jaroWinkler(a: string, b: string, p = 0.1): number {
  if (a === b) return 1;
  if (!a.length || !b.length) return 0;
  const j = jaro(a, b);
  let l = 0;
  const maxL = Math.min(4, a.length, b.length);
  for (let i = 0; i < maxL; i++) {
    if (a[i] === b[i]) l++;
    else break;
  }
  return j + l * p * (1 - j);
}

function jaro(s1: string, s2: string): number {
  const len1 = s1.length;
  const len2 = s2.length;
  const matchDist = Math.floor(Math.max(len1, len2) / 2) - 1;
  const s1Matches = new Array<boolean>(len1).fill(false);
  const s2Matches = new Array<boolean>(len2).fill(false);
  let matches = 0;
  for (let i = 0; i < len1; i++) {
    const start = Math.max(0, i - matchDist);
    const end = Math.min(i + matchDist + 1, len2);
    for (let j = start; j < end; j++) {
      if (s2Matches[j] || s1[i] !== s2[j]) continue;
      s1Matches[i] = true;
      s2Matches[j] = true;
      matches++;
      break;
    }
  }
  if (matches === 0) return 0;
  let t = 0;
  let k = 0;
  for (let i = 0; i < len1; i++) {
    if (!s1Matches[i]) continue;
    while (!s2Matches[k]) k++;
    if (s1[i] !== s2[k]) t++;
    k++;
  }
  t /= 2;
  return (
    (matches / len1 + matches / len2 + (matches - t) / matches) / 3
  );
}

/**
 * Optional fuzzy match against synonym *values* when no exact key hit.
 * Returns updated NormalizedName with fuzzyMatched + adjusted confidence.
 */
export function applyFuzzySynonym(
  name: NormalizedName,
  threshold = 0.92,
): NormalizedName {
  if (name.confidence >= 1) return name;
  let best: { canonical: string; score: number } | null = null;
  const target = name.key;
  const values = new Set(Object.values(INGREDIENT_SYNONYMS));
  for (const v of values) {
    const score = jaroWinkler(target, v);
    if (score >= threshold && (!best || score > best.score)) {
      best = { canonical: v, score };
    }
  }
  if (!best) return { ...name, confidence: name.confidence };
  return {
    canonical: best.canonical,
    key: best.canonical.replace(/\s+/g, " "),
    fuzzyMatched: true,
    confidence: best.score,
  };
}

function detectKind(
  unit: string,
): { kind: NormalizedUnitKind; factorToBase: number } | null {
  const u = normalizeUnitToken(unit);
  if (u === "to taste" || u === "totaste") {
    return { kind: "mass_g", factorToBase: 0 };
  }
  if (MASS_TO_G[u] !== undefined) {
    return { kind: "mass_g", factorToBase: MASS_TO_G[u]! };
  }
  if (VOLUME_TO_ML[u] !== undefined) {
    return { kind: "volume_ml", factorToBase: VOLUME_TO_ML[u]! };
  }
  if (COUNT_UNITS.has(u) || /^x\d+$/i.test(unit.trim())) {
    return { kind: "count", factorToBase: 1 };
  }
  return null;
}

/**
 * Convert quantity+unit to base units. Volume↔mass requires `ingredientMeta.densityGPerMl`.
 */
export function normalizeQuantity(
  quantity: number,
  unit: string,
  ingredientMeta?: IngredientMeta,
): NormalizedQuantity {
  if (!Number.isFinite(quantity)) {
    return { value: 0, kind: "mass_g", isAmbiguous: true };
  }
  const u = normalizeUnitToken(unit);
  if (u === "to taste" || u === "totaste") {
    return { value: 0, kind: "mass_g" };
  }

  const volFactor = VOLUME_TO_ML[u];
  if (volFactor !== undefined && ingredientMeta?.densityGPerMl !== undefined) {
    return {
      value: quantity * volFactor * ingredientMeta.densityGPerMl,
      kind: "mass_g",
    };
  }

  const direct = detectKind(unit);
  if (direct && direct.kind !== "count") {
    return { value: quantity * direct.factorToBase, kind: direct.kind };
  }
  if (direct?.kind === "count") {
    return { value: quantity * direct.factorToBase, kind: "count" };
  }

  const mass = MASS_TO_G[u];
  if (mass !== undefined) {
    return { value: quantity * mass, kind: "mass_g" };
  }
  if (volFactor !== undefined) {
    return { value: quantity * volFactor, kind: "volume_ml" };
  }

  return { value: quantity, kind: "count", isAmbiguous: true };
}
