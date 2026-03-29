/**
 * Deterministic TinyFish stand-in for tests: replay fixture JSON, simulate failures and odd SKUs.
 */

import type {
  CartAutomationResult,
  CartLineItem,
  ProductCandidate,
  ProductSearchResult,
} from "@nutrition-agent/tinyfish-client";

import type { TinyFishSearchOptions } from "../tinyfish/TinyFishAdapter.js";

export type FakeSearchFixture = {
  query: string;
  storeUrl: string;
  result: ProductSearchResult;
};

function key(query: string, storeUrl: string): string {
  return `${storeUrl}::${query}`;
}

export class FakeTinyFishAdapter {
  private readonly map = new Map<string, ProductSearchResult>();
  readonly failSearch = new Set<string>();
  readonly failCart = new Set<string>();
  /** When set, drops every other product row to simulate sparse shelves. */
  sparseResults = false;

  constructor(fixtures?: Iterable<FakeSearchFixture>) {
    if (fixtures) {
      for (const f of fixtures) {
        this.map.set(key(f.query, f.storeUrl), f.result);
      }
    }
  }

  addFixture(f: FakeSearchFixture): void {
    this.map.set(key(f.query, f.storeUrl), f.result);
  }

  async searchProducts(
    query: string,
    storeUrl: string,
    options?: TinyFishSearchOptions,
  ): Promise<ProductSearchResult> {
    if (options?.signal?.aborted) {
      const e = new Error("Aborted");
      e.name = "AbortError";
      throw e;
    }
    options?.onProgress?.({
      stage: "search_start",
      query,
      storeUrl,
      attempt: 0,
      progress: 0,
    });
    if (this.failSearch.has(storeUrl)) {
      throw new Error("fetch failed: ECONNRESET");
    }
    let base =
      this.map.get(key(query, storeUrl)) ?? {
        ingredient_query: query,
        store_url: storeUrl,
        products: [],
        raw_result: { fake: true },
      };
    if (this.sparseResults && base.products.length > 1) {
      const products = base.products.filter((_, i) => i % 2 === 0);
      base = { ...base, products };
    }
    options?.onProgress?.({
      stage: "search_done",
      query,
      storeUrl,
      attempt: 0,
      progress: 1,
    });
    return base;
  }

  async addToCart(
    storeUrl: string,
    items: CartLineItem[],
    options?: { signal?: AbortSignal },
  ): Promise<CartAutomationResult> {
    if (options?.signal?.aborted) {
      const e = new Error("Aborted");
      e.name = "AbortError";
      throw e;
    }
    if (this.failCart.has(storeUrl)) {
      throw new Error("STORE_BLOCKED");
    }
    return {
      store_url: storeUrl,
      raw_result: { ok: true, lines: items },
    };
  }
}

/** Build {@link ProductCandidate} rows usable in fixtures. */
export function fakeProduct(
  name: string,
  price: string | null,
  size: string | null,
): ProductCandidate {
  return {
    name,
    price,
    quantity_or_size: size,
    unit_price: null,
    raw: {},
  };
}
