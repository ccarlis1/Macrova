/**
 * Thin extension of the shared TinyFish SDK wrapper: cancellation guard only.
 * Retries and telemetry belong in {@link TinyFishAdapter}.
 */

import {
  TinyFishClient as SdkTinyFishClient,
  type ProductSearchResult,
  type SearchProductsOptions,
  type TinyFishClientOptions,
} from "@nutrition-agent/tinyfish-client";

export type GroceryTinyFishClientOptions = TinyFishClientOptions;

export class TinyFishClient extends SdkTinyFishClient {
  constructor(options?: GroceryTinyFishClientOptions) {
    super(options);
  }

  override async searchProducts(
    query: string,
    storeUrl: string,
    options?: SearchProductsOptions & { signal?: AbortSignal },
  ): Promise<ProductSearchResult> {
    if (options?.signal?.aborted) {
      const e = new Error("Aborted");
      e.name = "AbortError";
      throw e;
    }
    const { signal, ...rest } = options ?? {};
    return super.searchProducts(query, storeUrl, rest);
  }
}
