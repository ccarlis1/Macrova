/**
 * Human-readable explanations for optimizer decisions (deterministic strings).
 */

import type { Explanation } from "./types.js";
import type { NormalizedProduct } from "./types.js";
import type { IngredientRequirement, SelectedProduct } from "./types.js";
import type { RankedProduct } from "./types.js";

function fmtMoney(n: number): string {
  return n.toFixed(2);
}

function fmtQty(n: number, kind: string): string {
  if (kind === "mass_g") return `${fmtMoney(n)} g`;
  if (kind === "volume_ml") return `${fmtMoney(n)} ml`;
  return `${fmtMoney(n)} units`;
}

export interface BuildExplanationInput {
  requirement: IngredientRequirement;
  selected: SelectedProduct[];
  totalMonetaryCost: number;
  waste: number;
  rankedConsidered: RankedProduct[];
  rejected: { product: string; rejectedReason: string }[];
}

export function buildIngredientExplanation(input: BuildExplanationInput): Explanation {
  const lines: string[] = [];
  const req = input.requirement;
  if (input.selected.length === 0) {
    lines.push(`No purchasable SKU could be selected for "${req.displayName}".`);
    return {
      ingredient: req.displayName,
      reasoning: lines,
      alternativesConsidered: input.rejected.slice(0, 5),
    };
  }

  for (const sp of input.selected) {
    const p = sp.product;
    const label = p.candidate.name;
    const size = p.candidate.sizeRaw ?? "unknown size";
    const price = p.totalPackPrice ?? 0;
    const up = p.unitPrice;
    lines.push(
      `Selected ${sp.packCount}× "${label}" (${size}) for $${fmtMoney(price * sp.packCount)} total.`,
    );
    if (up !== null && Number.isFinite(up)) {
      lines.push(`Implied unit economics ≈ $${fmtMoney(up)} per base unit (${req.kind}).`);
    }
  }
  lines.push(`Total monetary cost for this ingredient: $${fmtMoney(input.totalMonetaryCost)}.`);
  if (input.waste > 1e-6) {
    lines.push(
      `Overbuy (waste): ${fmtQty(input.waste, req.kind)} beyond the recipe need of ${fmtQty(req.quantity, req.kind)}.`,
    );
  } else {
    lines.push("No meaningful overbuy versus the recipe quantity.");
  }

  return {
    ingredient: req.displayName,
    reasoning: lines,
    alternativesConsidered: input.rejected.slice(0, 5),
  };
}

export function pickRejectedAlternatives(
  ranked: RankedProduct[],
  selectedIds: Set<string>,
  minCount = 2,
): { product: string; rejectedReason: string }[] {
  const out: { product: string; rejectedReason: string }[] = [];
  for (const r of ranked) {
    if (selectedIds.has(r.id)) continue;
    let rejectedReason = "Not part of the minimum-cost effective plan for this ingredient.";
    if (!r.unitCompatible) {
      rejectedReason = "Incompatible or unclear units versus the recipe line.";
    } else if (!r.priceComplete) {
      rejectedReason = "Missing or incomplete shelf price.";
    } else if (r.rankScore < 0.35) {
      rejectedReason = "Low name match versus the recipe ingredient.";
    } else {
      rejectedReason = "Higher effective cost or worse unit economics in the DP evaluation.";
    }
    out.push({ product: r.name, rejectedReason });
    if (out.length >= minCount) break;
  }
  return out;
}

export function productLabel(np: NormalizedProduct): string {
  const s = np.candidate.sizeRaw ? ` (${np.candidate.sizeRaw})` : "";
  return `${np.candidate.name}${s}`;
}
