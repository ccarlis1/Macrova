/**
 * TinyFish search adapter selection for the CLI (real SDK vs deterministic mock for e2e).
 */

import type { ProductCandidate } from "@nutrition-agent/tinyfish-client";

import {
  createTinyFishSearchAdapter,
  MockTinyFishSearchAdapter,
  type TinyFishSearchAdapter,
} from "./integrations/tinyfish_client.js";

function mockProductsForQuery(query: string, storeUrl: string): ProductCandidate[] {
  const q = query.toLowerCase();
  const size =
    q.includes("oil") || q.includes("olive")
      ? "8 fl oz"
      : q.includes("chicken") || q.includes("breast")
        ? "32 oz"
        : "16 oz";
  const price = q.includes("oil") ? "$4.99" : "$9.99";
  return [
    {
      name: `${query} (mock)`,
      price,
      quantity_or_size: size,
      unit_price: null,
      raw: { brand: "Mock", mock: true, storeUrl },
    },
  ];
}

export function createSearchAdapterFromEnv(): TinyFishSearchAdapter {
  if (process.env.GROCERY_OPTIMIZER_USE_MOCK === "1") {
    return new MockTinyFishSearchAdapter(mockProductsForQuery);
  }
  return createTinyFishSearchAdapter();
}
