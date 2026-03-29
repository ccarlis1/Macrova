/**
 * Short-TTL cache for product search results keyed by store, ingredient, geo, and time bucket.
 * Supports stale-while-revalidate: serve stale entries immediately and refresh in the background.
 */

import type { ProductSearchResult } from "@nutrition-agent/tinyfish-client";

export type QueryCacheKey = {
  storeUrl: string;
  canonicalIngredient: string;
  geo?: string;
  /** Floor timestamp to a bucket (e.g. 5-minute windows). */
  timestampBucket: number;
};

function keyString(k: QueryCacheKey): string {
  return [
    k.storeUrl,
    k.canonicalIngredient,
    k.geo ?? "",
    String(k.timestampBucket),
  ].join("|");
}

export interface CacheEntry<T> {
  value: T;
  storedAtMs: number;
  ttlMs: number;
}

export type StaleWhileRevalidateOptions = {
  ttlMs: number;
  /** When set, entries may be served up to this age while a refresh runs. */
  staleMaxAgeMs?: number;
};

export class QuerySearchCache {
  private readonly map = new Map<string, CacheEntry<ProductSearchResult>>();
  private readonly defaultTtlMs: number;
  private readonly staleMaxAgeMs: number;

  constructor(options?: { ttlMs?: number; staleMaxAgeMs?: number }) {
    this.defaultTtlMs = options?.ttlMs ?? 10 * 60_000;
    this.staleMaxAgeMs = options?.staleMaxAgeMs ?? 15 * 60_000;
  }

  get(key: QueryCacheKey): ProductSearchResult | undefined {
    const e = this.map.get(keyString(key));
    if (!e) return undefined;
    const age = Date.now() - e.storedAtMs;
    if (age > e.ttlMs + this.staleMaxAgeMs) {
      this.map.delete(keyString(key));
      return undefined;
    }
    return e.value;
  }

  /**
   * Returns entry if present and not hard-expired beyond stale window.
   * `isStale` is true when past TTL but still within stale-while-revalidate window.
   */
  getWithMeta(key: QueryCacheKey): {
    value: ProductSearchResult;
    isStale: boolean;
  } | null {
    const e = this.map.get(keyString(key));
    if (!e) return null;
    const age = Date.now() - e.storedAtMs;
    if (age > e.ttlMs + this.staleMaxAgeMs) {
      this.map.delete(keyString(key));
      return null;
    }
    return { value: e.value, isStale: age > e.ttlMs };
  }

  set(
    key: QueryCacheKey,
    value: ProductSearchResult,
    ttlMs?: number,
  ): void {
    this.map.set(keyString(key), {
      value,
      storedAtMs: Date.now(),
      ttlMs: ttlMs ?? this.defaultTtlMs,
    });
  }

  /**
   * If fresh or stale hit, return value immediately. If stale, invoke `refresh` once without awaiting.
   */
  async getOrRevalidate(
    key: QueryCacheKey,
    refresh: () => Promise<ProductSearchResult>,
    opts?: StaleWhileRevalidateOptions,
  ): Promise<ProductSearchResult> {
    const ttl = opts?.ttlMs ?? this.defaultTtlMs;
    const meta = this.getWithMeta(key);
    if (meta && !meta.isStale) {
      return meta.value;
    }
    if (meta?.isStale) {
      void refresh()
        .then((v) => this.set(key, v, ttl))
        .catch(() => {
          /* keep stale */
        });
      return meta.value;
    }
    const fresh = await refresh();
    this.set(key, fresh, ttl);
    return fresh;
  }

  clear(): void {
    this.map.clear();
  }
}

/** Bucket start time for a fixed window (e.g. 5 minutes). */
export function floorToBucket(ms: number, windowMs: number): number {
  return Math.floor(ms / windowMs) * windowMs;
}
