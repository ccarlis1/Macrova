/**
 * Parse retailer size strings and normalize to comparable unit economics.
 */

import { OptimizationErrorCode, err } from "./errors.js";
import type {
  IngredientUnitContext,
  NormalizedProduct,
  NormalizedUnitKind,
  ParsedSize,
  ParseConfidence,
  ProductCandidate,
  PipelineResult,
} from "./types.js";
import { VOLUME_TO_ML, MASS_TO_G } from "./unit_constants.js";

// Re-export for tests
export { MASS_TO_G, VOLUME_TO_ML } from "./unit_constants.js";

function stripMoney(s: string): number | null {
  const cleaned = s.replace(/[^0-9.]/g, "");
  if (cleaned === "" || cleaned === ".") return null;
  const n = Number.parseFloat(cleaned);
  return Number.isFinite(n) ? n : null;
}

/**
 * Parse common pack size strings into base units (g, ml, or count).
 * Supports forms like "2 lb", "3 x 200g", "64 fl oz", "16 oz" (weight).
 */
export function parsePackSize(rawSize: string | null | undefined): ParsedSize | null {
  if (rawSize === null || rawSize === undefined) return null;
  const s = rawSize.trim().toLowerCase();
  if (!s) return null;

  const multPack = /^(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(g|kg|oz|lb|ml|l|fl\s*oz)\b/i.exec(
    s,
  );
  if (multPack) {
    const count = Number.parseInt(multPack[1]!, 10);
    const per = Number.parseFloat(multPack[2]!);
    const u = normalizeUnit(multPack[3]!);
    const base = toBaseAmount(per, u);
    if (!base) {
      return {
        totalAmount: count * per,
        kind: "count",
        multiplier: count,
        perPackAmount: per,
        confidence: "low",
        raw: rawSize,
      };
    }
    return {
      totalAmount: count * base.amount,
      kind: base.kind,
      multiplier: count,
      perPackAmount: base.amount,
      confidence: "high",
      raw: rawSize,
    };
  }

  const simple = /^(\d+(?:\.\d+)?)\s*-?\s*(g|kg|oz|lb|ml|l|cup|cups|tbsp|tsp|fl\s*oz|ct|count|pk|pack)?\b/i.exec(
    s,
  );
  if (simple) {
    const amt = Number.parseFloat(simple[1]!);
    const uRaw = simple[2] ?? "";
    const u = normalizeUnit(uRaw);
    const base = toBaseAmount(amt, u);
    if (base) {
      return {
        totalAmount: base.amount,
        kind: base.kind,
        confidence: uRaw ? "high" : "medium",
        raw: rawSize,
      };
    }
  }

  return {
    totalAmount: 1,
    kind: "count",
    confidence: "low",
    raw: rawSize,
  };
}

function normalizeUnit(u: string): string {
  return u.trim().toLowerCase().replace(/\s+/g, " ");
}

function toBaseAmount(
  amt: number,
  unit: string,
): { amount: number; kind: NormalizedUnitKind } | null {
  const u = normalizeUnit(unit);
  if (u === "g" || u === "gram" || u === "grams") {
    return { amount: amt, kind: "mass_g" };
  }
  if (u === "kg") {
    return { amount: amt * 1000, kind: "mass_g" };
  }
  if (u === "oz" || u === "ounce" || u === "ounces") {
    return { amount: amt * (MASS_TO_G["oz"] ?? 28.349523125), kind: "mass_g" };
  }
  if (u === "lb" || u === "lbs" || u === "pound" || u === "pounds") {
    return { amount: amt * (MASS_TO_G["lb"] ?? 453.59237), kind: "mass_g" };
  }
  if (u === "ml") {
    return { amount: amt, kind: "volume_ml" };
  }
  if (u === "l" || u === "liter" || u === "liters") {
    return { amount: amt * 1000, kind: "volume_ml" };
  }
  if (u === "fl oz" || u === "floz") {
    return {
      amount: amt * (VOLUME_TO_ML["fl oz"] ?? 29.5735295625),
      kind: "volume_ml",
    };
  }
  if (u === "cup" || u === "cups") {
    return { amount: amt * (VOLUME_TO_ML["cup"] ?? 236.5882365), kind: "volume_ml" };
  }
  if (u === "tbsp" || u === "tablespoon" || u === "tablespoons") {
    return { amount: amt * (VOLUME_TO_ML["tbsp"] ?? 14.78676478125), kind: "volume_ml" };
  }
  if (u === "tsp" || u === "teaspoon" || u === "teaspoons") {
    return { amount: amt * (VOLUME_TO_ML["tsp"] ?? 4.92892159375), kind: "volume_ml" };
  }
  if (u === "ct" || u === "count" || u === "pk" || u === "pack") {
    return { amount: amt, kind: "count" };
  }
  return null;
}

/**
 * `unitPrice = price / normalizedQuantity` in `targetUnit` base units.
 */
export function computeUnitPrice(
  price: number,
  parsedSize: ParsedSize,
  target: IngredientUnitContext,
): number {
  let amount = parsedSize.totalAmount;
  let kind = parsedSize.kind;

  if (kind !== target.kind) {
    if (
      kind === "volume_ml" &&
      target.kind === "mass_g" &&
      target.densityGPerMl !== undefined
    ) {
      amount = amount * target.densityGPerMl;
      kind = "mass_g";
    } else if (
      kind === "mass_g" &&
      target.kind === "volume_ml" &&
      target.densityGPerMl !== undefined &&
      target.densityGPerMl > 0
    ) {
      amount = amount / target.densityGPerMl;
      kind = "volume_ml";
    } else {
      return Number.NaN;
    }
  }

  if (amount <= 0) return Number.NaN;
  return price / amount;
}

export interface NormalizePriceOptions {
  /** For structured error messages (e.g. unit mismatch on this line). */
  ingredientKey?: string;
  ingredientDisplayName?: string;
}

export function normalizeProductPriceWithErrors(
  product: ProductCandidate,
  ingredientUnitContext: IngredientUnitContext,
  options?: NormalizePriceOptions,
): PipelineResult<NormalizedProduct> {
  const errors: PipelineResult<NormalizedProduct>["errors"] = [];
  const parsedSize = parsePackSize(product.sizeRaw);
  const priceNum = product.priceRaw ? stripMoney(product.priceRaw) : null;
  let confidence: ParseConfidence = parsedSize?.confidence ?? "low";
  let unitPrice: number | null = null;
  let normalizedPackQty: number | null = null;
  const ingLabel =
    options?.ingredientDisplayName ?? options?.ingredientKey ?? product.name;

  if (parsedSize && parsedSize.confidence === "low" && product.sizeRaw) {
    errors.push(
      err(OptimizationErrorCode.PRICE_PARSE_FAILED, `Ambiguous pack size "${product.sizeRaw}".`, {
        ingredient: ingLabel,
        severity: "warning",
      }),
    );
  }

  if (parsedSize && priceNum !== null && priceNum > 0) {
    normalizedPackQty = parsedSize.totalAmount;
    unitPrice = computeUnitPrice(priceNum, parsedSize, ingredientUnitContext);
    if (Number.isNaN(unitPrice)) {
      unitPrice = null;
      confidence = "low";
      errors.push(
        err(
          OptimizationErrorCode.UNIT_MISMATCH,
          "Pack units do not match the recipe line (volume vs mass) without a density mapping.",
          { ingredient: ingLabel, severity: "warning" },
        ),
      );
    }
  } else if (priceNum !== null && product.unitPriceRaw) {
    const up = stripMoney(product.unitPriceRaw);
    if (up !== null) {
      unitPrice = up;
      confidence = "medium";
    }
  }

  if (priceNum === null && product.priceRaw) {
    errors.push(
      err(OptimizationErrorCode.PRICE_PARSE_FAILED, "Could not parse shelf price string.", {
        ingredient: ingLabel,
        severity: "warning",
      }),
    );
  }

  const lowConfidence =
    confidence === "low" || unitPrice === null || unitPrice <= 0;

  if (lowConfidence) {
    errors.push(
      err(OptimizationErrorCode.LOW_CONFIDENCE_MATCH, "Low confidence in unit price / pack parse.", {
        ingredient: ingLabel,
        severity: "warning",
      }),
    );
  }

  const data: NormalizedProduct = {
    candidate: product,
    parsedSize,
    unitPrice,
    totalPackPrice: priceNum,
    normalizedPackQuantity: normalizedPackQty,
    confidence,
    lowConfidence,
  };

  return { data, errors };
}

export function normalizeProductPrice(
  product: ProductCandidate,
  ingredientUnitContext: IngredientUnitContext,
): NormalizedProduct {
  return normalizeProductPriceWithErrors(product, ingredientUnitContext).data!;
}
