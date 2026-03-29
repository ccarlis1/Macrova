import { describe, expect, it, vi } from "vitest";

import { executeCartPlan, selectedProductSignature } from "./cart_builder.js";
import { floorToBucket, QuerySearchCache } from "./caching/query_cache.js";
import { productSignature, ProductParseCache } from "./caching/product_cache.js";
import { optimizeMultiStoreCart } from "./optimizer_multistore.js";
import { optimizeCart, optimizeIngredientDetailed } from "./optimizer.js";
import type {
  IngredientRequirement,
  NormalizedProduct,
  OptimizationPreferences,
  ProductCandidate,
} from "./types.js";
import { FakeTinyFishAdapter, fakeProduct } from "./testing/fake_tinyfish_adapter.js";

function cand(
  storeId: string,
  name: string,
  price: string,
  size: string,
  id: string,
): ProductCandidate {
  return {
    id,
    name,
    priceRaw: price,
    sizeRaw: size,
    unitPriceRaw: null,
    storeId,
    query: "q",
    raw: {},
  };
}

function norm(
  c: ProductCandidate,
  packQty: number,
  packPrice: number,
  low = false,
): NormalizedProduct {
  return {
    candidate: c,
    parsedSize: {
      totalAmount: packQty,
      kind: "mass_g",
      confidence: "high",
      raw: c.sizeRaw ?? "",
    },
    unitPrice: packPrice / packQty,
    totalPackPrice: packPrice,
    normalizedPackQuantity: packQty,
    confidence: low ? "low" : "high",
    lowConfidence: low,
  };
}

describe("multi-store optimization", () => {
  it("prefers two stores when cheaper than single-store cover", () => {
    const requirements: IngredientRequirement[] = [
      { canonicalKey: "a", displayName: "A", quantity: 100, kind: "mass_g" },
      { canonicalKey: "b", displayName: "B", quantity: 100, kind: "mass_g" },
    ];

    const cA1 = cand("s1", "A cheap", "$10", "200 g", "1");
    const cA2 = cand("s2", "A alt", "$50", "200 g", "2");
    const cB1 = cand("s1", "B expensive", "$50", "200 g", "3");
    const cB2 = cand("s2", "B cheap", "$10", "200 g", "4");

    const candidatesByIngredient: Record<string, NormalizedProduct[]> = {
      a: [norm(cA1, 200, 10), norm(cA2, 200, 50)],
      b: [norm(cB1, 200, 50), norm(cB2, 200, 10)],
    };

    const prefs: OptimizationPreferences = {
      maxStores: 2,
      wastePenaltyPerUnit: 0.001,
      storeSplitPenalty: 0.5,
    };

    const r = optimizeMultiStoreCart(requirements, candidatesByIngredient, prefs);
    expect(r.storesUsed.sort()).toEqual(["s1", "s2"]);
    expect(r.totalCost).toBeLessThan(40);
    expect(r.degraded).toBeFalsy();
  });

  it("prefers one store when split savings are smaller than store penalty", () => {
    const requirements: IngredientRequirement[] = [
      { canonicalKey: "a", displayName: "A", quantity: 100, kind: "mass_g" },
      { canonicalKey: "b", displayName: "B", quantity: 100, kind: "mass_g" },
    ];
    // Crossing cost/waste so each store stays Pareto-efficient for at least one ingredient.
    const aS1 = cand("s1", "A exact", "$12", "100 g", "1");
    const aS2 = cand("s2", "A bulk", "$10", "200 g", "2");
    const bS1 = cand("s1", "B bulk", "$10", "200 g", "3");
    const bS2 = cand("s2", "B exact", "$12", "100 g", "4");
    const candidatesByIngredient: Record<string, NormalizedProduct[]> = {
      a: [norm(aS1, 100, 12), norm(aS2, 200, 10)],
      b: [norm(bS1, 200, 10), norm(bS2, 100, 12)],
    };

    const prefs: OptimizationPreferences = {
      maxStores: 2,
      wastePenaltyPerUnit: 0.0001,
      storeSplitPenalty: 5,
    };

    const r = optimizeMultiStoreCart(requirements, candidatesByIngredient, prefs);
    expect(r.storesUsed).toHaveLength(1);
    expect(r.totalCost).toBeCloseTo(22, 5);
  });
});

describe("cart execution", () => {
  it("dedupes by signature and handles partial store failures", async () => {
    const adapter = new FakeTinyFishAdapter();
    adapter.failCart.add("https://bad.example");

    const plan = {
      lines: [
        {
          storeId: "good",
          storeUrl: "https://good.example",
          ingredientKey: "a",
          searchQuery: "milk",
          quantity: 1,
          signatureHash: "h1",
        },
        {
          storeId: "good",
          storeUrl: "https://good.example",
          ingredientKey: "b",
          searchQuery: "milk",
          quantity: 1,
          signatureHash: "h1",
        },
        {
          storeId: "bad",
          storeUrl: "https://bad.example",
          ingredientKey: "c",
          searchQuery: "eggs",
          quantity: 1,
          signatureHash: "h2",
        },
      ],
      runId: "r1",
    };

    const progress = vi.fn();
    const res = await executeCartPlan(plan, adapter, {
      onProgress: progress,
    });
    expect(res.success).toBe(false);
    expect(res.storesCompleted).toContain("good");
    expect(res.failures.some((f) => f.storeId === "bad")).toBe(true);
    expect(progress).toHaveBeenCalled();
  });
});

describe("caching", () => {
  it("query cache hit avoids duplicate payload until TTL", () => {
    const c = new QuerySearchCache({ ttlMs: 60_000 });
    const key = {
      storeUrl: "https://walmart.com",
      canonicalIngredient: "milk",
      timestampBucket: floorToBucket(Date.now(), 300_000),
    };
    const payload = {
      ingredient_query: "milk",
      store_url: key.storeUrl,
      products: [fakeProduct("m", "$3", "1 gal")],
      raw_result: {},
    };
    c.set(key, payload);
    expect(c.get(key)).toEqual(payload);
  });

  it("stale-while-revalidate returns stale immediately", async () => {
    const c = new QuerySearchCache({ ttlMs: 1, staleMaxAgeMs: 10_000 });
    const key = {
      storeUrl: "https://x.com",
      canonicalIngredient: "x",
      timestampBucket: 0,
    };
    const v1 = {
      ingredient_query: "x",
      store_url: key.storeUrl,
      products: [],
      raw_result: {},
    };
    c.set(key, v1, 1);
    const refresh = vi.fn().mockResolvedValue({
      ...v1,
      raw_result: { v: 2 },
    });
    await new Promise((r) => setTimeout(r, 5));
    const out = await c.getOrRevalidate(key, refresh, { ttlMs: 1 });
    expect(out).toEqual(v1);
    await vi.waitFor(() => expect(refresh).toHaveBeenCalled(), { timeout: 2000 });
  });

  it("product cache avoids re-parse by signature", () => {
    const pc = new ProductParseCache();
    const c = cand("s", "n", "$1", "1 lb", "id");
    const np = norm(c, 454, 1);
    const sig = productSignature(c);
    pc.set(sig, np);
    expect(pc.get(sig)?.candidate.id).toBe("id");
  });
});

describe("selectedProductSignature idempotency", () => {
  it("is stable for same selection", () => {
    const c = cand("s", "n", "$1", "1 lb", "id");
    const sp = { product: norm(c, 454, 1), packCount: 2 };
    expect(selectedProductSignature(sp)).toBe(selectedProductSignature(sp));
  });
});

describe("Phase 1/2 parity", () => {
  it("single-ingredient DP unchanged vs optimizeCart one row", () => {
    const req: IngredientRequirement = {
      canonicalKey: "k",
      displayName: "K",
      quantity: 100,
      kind: "mass_g",
    };
    const c = cand("s", "K", "$5", "200 g", "id");
    const n = norm(c, 200, 5);
    const prefs: OptimizationPreferences = { wastePenaltyPerUnit: 0.02 };
    const a = optimizeIngredientDetailed(req, [n], [], prefs).solution;
    const b = optimizeCart([req], { k: [n] }, prefs).perIngredient[0]!;
    expect(a.totalCost).toBe(b.totalCost);
    expect(a.waste).toBe(b.waste);
  });
});
