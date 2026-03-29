import { describe, expect, it } from "vitest";
import { OptimizationErrorCode } from "./errors.js";
import { optimizeCart, optimizeIngredientDetailed } from "./optimizer.js";
import { normalizeProductPriceWithErrors } from "./price_normalizer.js";
import { searchProductsForIngredientResult } from "./product_search.js";
import type {
  IngredientRequirement,
  NormalizedProduct,
  ProductCandidate,
  RankedProduct,
} from "./types.js";
import type { TinyFishSearchAdapter } from "./integrations/tinyfish_client.js";
import { MockTinyFishSearchAdapter } from "./integrations/tinyfish_client.js";
import type { ProductSearchResult } from "@nutrition-agent/tinyfish-client";

function np(
  id: string,
  packG: number,
  price: number,
  conf: "high" | "medium" | "low" = "high",
): NormalizedProduct {
  const c: ProductCandidate = {
    id,
    name: `SKU ${id}`,
    priceRaw: String(price),
    sizeRaw: `${packG} g`,
    unitPriceRaw: null,
    storeId: "s1",
    query: "q",
  };
  const low = conf === "low";
  return {
    candidate: c,
    parsedSize: {
      totalAmount: packG,
      kind: "mass_g",
      confidence: conf === "high" ? "high" : "medium",
      raw: `${packG} g`,
    },
    unitPrice: price / packG,
    totalPackPrice: price,
    normalizedPackQuantity: packG,
    confidence: conf,
    lowConfidence: low,
  };
}

function rankFrom(products: NormalizedProduct[]): RankedProduct[] {
  return products.map((p, i) => ({
    ...p.candidate,
    rankScore: 1 - i * 0.01,
    nameSimilarity: 0.9,
    unitCompatible: true,
    priceComplete: true,
  }));
}

describe("objective tuning", () => {
  it("changes the chosen pack mix between min_cost and min_waste", () => {
    const req: IngredientRequirement = {
      canonicalKey: "k",
      displayName: "x",
      quantity: 200,
      kind: "mass_g",
    };
    const products = [np("100g", 100, 0.99), np("220g", 220, 1.0)];
    const ranked = rankFrom(products);

    const minCost = optimizeIngredientDetailed(
      req,
      products,
      ranked,
      { objective: "min_cost", wastePenaltyPerUnit: 0.0001, confidencePenalty: 0 },
    );
    const minWaste = optimizeIngredientDetailed(
      req,
      products,
      ranked,
      { objective: "min_waste", wastePenaltyPerUnit: 8, confidencePenalty: 0 },
    );

    const minCostIds = minCost.solution.products.map((p) => p.product.candidate.id);
    const minWasteIds = minWaste.solution.products.map(
      (p) => p.product.candidate.id,
    );

    expect(minCostIds).toContain("220g");
    expect(minWasteIds.every((id) => id === "100g")).toBe(true);
    expect(minWaste.solution.products[0]!.packCount).toBe(2);
  });
});

describe("explainability", () => {
  it("returns reasoning and at least two rejected alternatives when possible", () => {
    const req: IngredientRequirement = {
      canonicalKey: "k",
      displayName: "x",
      quantity: 200,
      kind: "mass_g",
    };
    const products = [np("a", 150, 1), np("b", 100, 0.8), np("c", 500, 5)];
    const ranked = rankFrom(products);
    const detail = optimizeIngredientDetailed(req, products, ranked, {
      wastePenaltyPerUnit: 0,
      confidencePenalty: 0,
    });
    expect(detail.explanation.reasoning.length).toBeGreaterThan(0);
    expect(detail.explanation.alternativesConsidered.length).toBeGreaterThanOrEqual(2);
  });

  it("includes an explanation per ingredient in optimizeCart", () => {
    const r1: IngredientRequirement = {
      canonicalKey: "a",
      displayName: "A",
      quantity: 100,
      kind: "mass_g",
    };
    const r2: IngredientRequirement = {
      canonicalKey: "b",
      displayName: "B",
      quantity: 50,
      kind: "mass_g",
    };
    const products = [np("p1", 100, 2), np("p2", 50, 1)];
    const cart = optimizeCart(
      [r1, r2],
      {
        a: [products[0]!],
        b: [products[1]!],
      },
      { wastePenaltyPerUnit: 0, confidencePenalty: 0 },
      {
        a: rankFrom([products[0]!]),
        b: rankFrom([products[1]!]),
      },
    );
    expect(cart.explanations).toHaveLength(2);
    expect(cart.errors.length).toBeGreaterThanOrEqual(0);
  });
});

describe("structured errors", () => {
  it("emits NO_CANDIDATES when search returns nothing", async () => {
    const adapter = new MockTinyFishSearchAdapter(() => []);
    const ingredient = {
      canonicalKey: "x",
      displayName: "x",
      totalQuantity: 1,
      normalizedUnit: "mass_g" as const,
      sourceRecipes: [],
      isToTaste: false,
    };
    const res = await searchProductsForIngredientResult(
      ingredient,
      [{ id: "s", baseUrl: "https://example.com" }],
      adapter,
    );
    expect(res.data?.candidates).toHaveLength(0);
    expect(res.errors.some((e) => e.code === OptimizationErrorCode.NO_CANDIDATES)).toBe(
      true,
    );
  });

  it("continues with partial candidates when one store query throws", async () => {
    let calls = 0;
    const adapter: TinyFishSearchAdapter = {
      async searchProducts(query: string, storeUrl: string): Promise<ProductSearchResult> {
        calls++;
        if (calls === 1) {
          throw new Error("simulated network failure");
        }
        return {
          ingredient_query: query,
          store_url: storeUrl,
          products: [
            {
              name: `${query} ok`,
              price: "$2",
              quantity_or_size: "16 oz",
              unit_price: null,
            },
          ],
          raw_result: {},
        };
      },
    };
    const ingredient = {
      canonicalKey: "x",
      displayName: "x",
      totalQuantity: 1,
      normalizedUnit: "mass_g" as const,
      sourceRecipes: [],
      isToTaste: false,
    };
    const res = await searchProductsForIngredientResult(
      ingredient,
      [{ id: "s", baseUrl: "https://example.com" }],
      adapter,
    );
    expect(res.data?.candidates.length).toBeGreaterThan(0);
    expect(
      res.errors.some((e) => e.code === OptimizationErrorCode.STORE_SEARCH_QUERY_FAILED),
    ).toBe(true);
  });

  it("emits PRICE_PARSE_FAILED for an ambiguous size string", () => {
    const c: ProductCandidate = {
      id: "1",
      name: "x",
      priceRaw: "5",
      sizeRaw: "???",
      unitPriceRaw: null,
      storeId: "s",
      query: "q",
    };
    const r = normalizeProductPriceWithErrors(c, { kind: "mass_g" }, {
      ingredientDisplayName: "test ing",
    });
    expect(r.errors.some((e) => e.code === OptimizationErrorCode.PRICE_PARSE_FAILED)).toBe(
      true,
    );
  });
});
