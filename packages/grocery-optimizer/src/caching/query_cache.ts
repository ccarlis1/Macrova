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
  /** Validator confidence 0–1 when set; omitted entries are treated as low-confidence for policy. */
  qualityScore?: number;
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
  private _hits = 0;
  private _misses = 0;

  constructor(options?: { ttlMs?: number; staleMaxAgeMs?: number }) {
    this.defaultTtlMs = options?.ttlMs ?? 10 * 60_000;
    this.staleMaxAgeMs = options?.staleMaxAgeMs ?? 15 * 60_000;
  }

  /** Fresh or stale hits where cached TinyFish-shaped payload was returned without awaiting refresh. */
  hitStats(): { hits: number; misses: number } {
    return { hits: this._hits, misses: this._misses };
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
    qualityScore: number;
  } | null {
    const e = this.map.get(keyString(key));
    if (!e) return null;
    const age = Date.now() - e.storedAtMs;
    if (age > e.ttlMs + this.staleMaxAgeMs) {
      this.map.delete(keyString(key));
      return null;
    }
    const qs = e.qualityScore ?? 0;
    return { value: e.value, isStale: age > e.ttlMs, qualityScore: qs };
  }

  set(
    key: QueryCacheKey,
    value: ProductSearchResult,
    ttlMs?: number,
    qualityScore?: number,
  ): void {
    this.map.set(keyString(key), {
      value,
      storedAtMs: Date.now(),
      ttlMs: ttlMs ?? this.defaultTtlMs,
      qualityScore,
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

  /**
   * SWR with quality policy: fresh high-confidence hits return immediately;
   * stale high-confidence hits return stale and refresh in the background;
   * low-confidence (or unknown) hits always await a full refresh.
   */
  async getOrRevalidateWithQualityPolicy(
    key: QueryCacheKey,
    refresh: () => Promise<{ value: ProductSearchResult; qualityScore: number }>,
    opts?: StaleWhileRevalidateOptions & { highQualityThreshold?: number },
  ): Promise<ProductSearchResult> {
    const ttl = opts?.ttlMs ?? this.defaultTtlMs;
    const hi = opts?.highQualityThreshold ?? 0.55;
    const meta = this.getWithMeta(key);
    if (meta) {
      const high = meta.qualityScore >= hi;
      if (!meta.isStale && high) {
        this._hits += 1;
        return meta.value;
      }
      if (meta.isStale && high) {
        this._hits += 1;
        void refresh()
          .then((r) => this.set(key, r.value, ttl, r.qualityScore))
          .catch(() => {
            /* keep stale */
          });
        return meta.value;
      }
    }
    this._misses += 1;
    const fresh = await refresh();
    this.set(key, fresh.value, ttl, fresh.qualityScore);
    return fresh.value;
  }

  clear(): void {
    this.map.clear();
  }
}

/** Bucket start time for a fixed window (e.g. 5 minutes). */
export function floorToBucket(ms: number, windowMs: number): number {
  return Math.floor(ms / windowMs) * windowMs;
}
