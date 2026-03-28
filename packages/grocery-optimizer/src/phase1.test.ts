import { describe, expect, it } from "vitest";
import { MockTinyFishSearchAdapter } from "./integrations/tinyfish_client.js";
import { searchProductsForIngredient } from "./product_search.js";
import {
  aggregateIngredients,
  extractIngredientLines,
} from "./ingredient_aggregator.js";
import {
  buildCanonicalIngredientKey,
  normalizeIngredientName,
  normalizeQuantity,
} from "./ingredient_normalizer.js";
import {
  buildOffersFromNormalizedLenient,
  optimizeIngredient,
  toIngredientRequirement,
} from "./optimizer.js";
import { parsePackSize, computeUnitPrice } from "./price_normalizer.js";
import type { IngredientUnitContext, NormalizedProduct, ProductCandidate } from "./types.js";

describe("ingredient normalization", () => {
  it('maps "chicken breasts" to canonical chicken breast', () => {
    const n = normalizeIngredientName("Chicken Breasts");
    expect(n.canonical).toBe("chicken breast");
    expect(buildCanonicalIngredientKey("Chicken Breasts")).toBe("chicken breast");
  });
});

describe("unit conversion", () => {
  it("converts 1 lb to grams", () => {
    const q = normalizeQuantity(1, "lb");
    expect(q.kind).toBe("mass_g");
    expect(q.value).toBeCloseTo(453.59237, 4);
  });
});

describe("price parsing", () => {
  it('parses "3 x 200g" as 600 g total', () => {
    const p = parsePackSize("3 x 200g");
    expect(p).not.toBeNull();
    expect(p!.kind).toBe("mass_g");
    expect(p!.totalAmount).toBeCloseTo(600, 5);
    expect(p!.confidence).toBe("high");
  });

  it('parses "64 fl oz" as volume', () => {
    const p = parsePackSize("64 fl oz");
    expect(p!.kind).toBe("volume_ml");
    expect(p!.totalAmount).toBeGreaterThan(1800);
  });
});

describe("computeUnitPrice", () => {
  it("computes $/g for a pack", () => {
    const parsed = parsePackSize("2 lb")!;
    const ctx: IngredientUnitContext = { kind: "mass_g" };
    const up = computeUnitPrice(10, parsed, ctx);
    expect(up).toBeCloseTo(10 / (2 * 453.59237), 6);
  });
});

describe("DP optimization", () => {
  function candidate(
    id: string,
    packG: number,
    price: number,
  ): NormalizedProduct {
    const c: ProductCandidate = {
      id,
      name: "test",
      priceRaw: String(price),
      sizeRaw: `${packG} g`,
      unitPriceRaw: null,
      storeId: "s1",
      query: "q",
    };
    return {
      candidate: c,
      parsedSize: {
        totalAmount: packG,
        kind: "mass_g",
        confidence: "high",
        raw: `${packG} g`,
      },
      unitPrice: price / packG,
      totalPackPrice: price,
      normalizedPackQuantity: packG,
      confidence: "high",
      lowConfidence: false,
    };
  }

  it("prefers a cheaper combination over a greedy unit-price choice", () => {
    // Need 200 g. SKUs: 150g@$1, 100g@$0.8 — best is 150+100 = $1.8 vs 150+150 = $2 vs 100*2 = $1.6? 100*2 = 200g exactly $1.6 — DP should pick two 100g packs.
    const products = [candidate("a", 150, 1), candidate("b", 100, 0.8)];
    const req = {
      canonicalKey: "k",
      displayName: "x",
      quantity: 200,
      kind: "mass_g" as const,
    };
    const sol = optimizeIngredient(req, products, { wastePenaltyPerUnit: 0 });
    expect(sol.partial).toBe(false);
    expect(sol.totalCost).toBeCloseTo(1.6, 5);
    const counts = Object.fromEntries(
      sol.products.map((p) => [p.product.candidate.id, p.packCount]),
    );
    expect(counts["b"]).toBe(2);
  });

  it("chooses a single large pack over several small ones when it is cheaper overall", () => {
    const products = [
      candidate("small", 100, 1.2),
      candidate("large", 300, 2.5),
    ];
    const req = {
      canonicalKey: "k",
      displayName: "x",
      quantity: 250,
      kind: "mass_g" as const,
    };
    const sol = optimizeIngredient(req, products, { wastePenaltyPerUnit: 0 });
    expect(sol.partial).toBe(false);
    expect(sol.products.some((p) => p.product.candidate.id === "large")).toBe(
      true,
    );
    expect(sol.totalCost).toBeCloseTo(2.5, 5);
  });
});

describe("aggregation + requirement", () => {
  it("merges duplicate canonical ingredients across recipes", () => {
    const lines = extractIngredientLines({
      recipes: [
        {
          id: "r1",
          name: "A",
          ingredients: [{ name: "chicken breasts", quantity: 1, unit: "lb" }],
        },
        {
          id: "r2",
          name: "B",
          ingredients: [{ name: "chicken breast", quantity: 0.5, unit: "lb" }],
        },
      ],
      recipeServings: { r1: 1, r2: 1 },
    });
    const agg = aggregateIngredients(lines);
    expect(agg).toHaveLength(1);
    expect(agg[0]!.totalQuantity).toBeCloseTo(1.5 * 453.59237, 3);
  });

  it("builds ingredient requirements", () => {
    const lines = extractIngredientLines({
      recipes: [
        {
          id: "r1",
          name: "Soup",
          ingredients: [{ name: "salt", quantity: 1, unit: "tsp" }],
        },
      ],
    });
    const agg = aggregateIngredients(lines);
    const req = toIngredientRequirement(agg[0]!);
    expect(req.quantity).toBeGreaterThan(0);
  });
});

describe("product search (adapter)", () => {
  it("dedupes across queries and stores using the mock adapter", async () => {
    const adapter = new MockTinyFishSearchAdapter((query) => [
      {
        name: `${query} SKU`,
        price: "3.00",
        quantity_or_size: "1 lb",
        unit_price: null,
      },
    ]);
    const ingredient = {
      canonicalKey: "chicken breast",
      displayName: "chicken breast",
      totalQuantity: 400,
      normalizedUnit: "mass_g" as const,
      sourceRecipes: [],
      isToTaste: false,
    };
    const set = await searchProductsForIngredient(
      ingredient,
      [{ id: "walmart", baseUrl: "https://www.walmart.com" }],
      adapter,
      { maxPerQuery: 3 },
    );
    expect(set.candidates.length).toBeGreaterThan(0);
  });
});

describe("buildOffersFromNormalizedLenient", () => {
  it("falls back to low-confidence SKUs when strict offers are empty", () => {
    const low: NormalizedProduct = {
      candidate: {
        id: "1",
        name: "x",
        priceRaw: "5",
        sizeRaw: "500 g",
        unitPriceRaw: null,
        storeId: "s",
        query: "q",
      },
      parsedSize: null,
      unitPrice: null,
      totalPackPrice: 5,
      normalizedPackQuantity: 500,
      confidence: "low",
      lowConfidence: true,
    };
    const offers = buildOffersFromNormalizedLenient([low]);
    expect(offers.length).toBe(1);
  });
});
