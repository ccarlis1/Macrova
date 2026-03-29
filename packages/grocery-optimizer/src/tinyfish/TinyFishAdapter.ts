/**
 * Grocery-facing TinyFish boundary: navigation/search/cart only — no optimizer math.
 * Retries (transient), backoff, streaming progress hooks, and cancellation signals live here.
 */

import {
  TinyFishClient as SdkTinyFishClient,
  type AddToCartOptions,
  type CartAutomationResult,
  type CartLineItem,
  type ProductSearchResult,
  type SearchProductsOptions,
} from "@nutrition-agent/tinyfish-client";

import {
  classifyDomainError,
  computeRetryDelayMs,
  isTransientDomainError,
} from "../errors.js";
import { logWarn } from "../observability/logger.js";

import { TinyFishClient } from "./TinyFishClient.js";

export type SearchProgressEvent = {
  stage: "search_start" | "stream" | "search_done" | "retry";
  query: string;
  storeUrl: string;
  attempt: number;
  /** 0–1 best-effort. */
  progress: number;
};

export type TinyFishSearchOptions = SearchProductsOptions & {
  signal?: AbortSignal;
  onProgress?: (ev: SearchProgressEvent) => void;
  maxRetries?: number;
};

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    const e = new Error("Aborted");
    e.name = "AbortError";
    throw e;
  }
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      const e = new Error("Aborted");
      e.name = "AbortError";
      reject(e);
      return;
    }
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        const e = new Error("Aborted");
        e.name = "AbortError";
        reject(e);
      },
      { once: true },
    );
  });
}

export class TinyFishAdapter {
  private readonly client: SdkTinyFishClient;

  constructor(client?: SdkTinyFishClient) {
    this.client = client ?? new TinyFishClient();
  }

  async searchProducts(
    query: string,
    storeUrl: string,
    options?: TinyFishSearchOptions,
  ): Promise<ProductSearchResult> {
    const maxRetries = options?.maxRetries ?? 3;
    let attempt = 0;

    for (;;) {
      throwIfAborted(options?.signal);
      options?.onProgress?.({
        stage: "search_start",
        query,
        storeUrl,
        attempt,
        progress: 0,
      });

      const { signal, onProgress, maxRetries: _mr, ...rest } = options ?? {};
      const merged: SearchProductsOptions = {
        ...rest,
        streamOptions: {
          ...rest.streamOptions,
          onProgress: (ev) => {
            rest.streamOptions?.onProgress?.(ev);
            onProgress?.({
              stage: "stream",
              query,
              storeUrl,
              attempt,
              progress: 0.4,
            });
          },
        },
      };

      try {
        const res = await this.client.searchProducts(query, storeUrl, merged);
        onProgress?.({
          stage: "search_done",
          query,
          storeUrl,
          attempt,
          progress: 1,
        });
        return res;
      } catch (err) {
        const kind = classifyDomainError(err);
        const transient = isTransientDomainError(kind);
        attempt += 1;
        if (attempt > maxRetries || !transient) {
          throw err;
        }
        logWarn({
          message: "TinyFish search retry",
          query,
          store: storeUrl,
          attempt,
        });
        onProgress?.({
          stage: "retry",
          query,
          storeUrl,
          attempt,
          progress: 0.2,
        });
        const delayMs = computeRetryDelayMs(attempt - 1);
        await sleep(delayMs, signal);
      }
    }
  }

  async addToCart(
    storeUrl: string,
    items: CartLineItem[],
    options?: AddToCartOptions & { signal?: AbortSignal; maxRetries?: number },
  ): Promise<CartAutomationResult> {
    const maxRetries = options?.maxRetries ?? 2;
    let attempt = 0;
    for (;;) {
      throwIfAborted(options?.signal);
      try {
        const { signal, maxRetries: _m, ...rest } = options ?? {};
        return await this.client.addToCart(storeUrl, items, rest);
      } catch (err) {
        const kind = classifyDomainError(err);
        attempt += 1;
        if (attempt > maxRetries || !isTransientDomainError(kind)) {
          throw err;
        }
        await sleep(computeRetryDelayMs(attempt - 1), options?.signal);
      }
    }
  }
}
