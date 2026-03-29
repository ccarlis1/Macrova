/**
 * Adapter boundary for TinyFish: grocery logic imports this module only,
 * never `@tiny-fish/sdk` or raw agent types directly.
 */

import type {
  ProductCandidate as TinyFishProductCandidate,
  ProductSearchResult,
} from "@nutrition-agent/tinyfish-client";

import {
  TinyFishAdapter,
  type TinyFishSearchOptions,
} from "../tinyfish/TinyFishAdapter.js";
import { TinyFishClient } from "../tinyfish/TinyFishClient.js";

export type { TinyFishSearchOptions, TinyFishProductCandidate, ProductSearchResult };

/** Minimal surface the optimizer needs for product search (extended with Phase 3 options). */
export interface TinyFishSearchAdapter {
  searchProducts(
    query: string,
    storeUrl: string,
    options?: TinyFishSearchOptions,
  ): Promise<ProductSearchResult>;
}

export function createTinyFishSearchAdapter(
  client?: TinyFishClient,
): TinyFishSearchAdapter {
  return new TinyFishAdapter(client);
}

/** In-memory adapter for tests and offline pipelines. */
export class MockTinyFishSearchAdapter implements TinyFishSearchAdapter {
  constructor(
    private readonly handler: (
      query: string,
      storeUrl: string,
    ) => TinyFishProductCandidate[],
  ) {}

  async searchProducts(
    query: string,
    storeUrl: string,
  ): Promise<ProductSearchResult> {
    const products = this.handler(query, storeUrl);
    return {
      ingredient_query: query,
      store_url: storeUrl,
      products,
      raw_result: { mock: true },
    };
  }
}

export { TinyFishAdapter, TinyFishClient };
