/**
 * In-memory metrics for optimization quality and pipeline health.
 */

export type PipelineMetrics = {
  optimizationLatencyMs: number;
  costGapVsGreedy: number;
  wastePercent: number;
  coverageRate: number;
  avgStoresPerCart: number;
  priceParseSuccessRate: number;
  /** TinyFish query-cache hits (fresh or stale-while-revalidate served). */
  searchCacheHits: number;
  /** TinyFish query-cache paths that awaited live fetch. */
  searchCacheMisses: number;
  /** Parse cache hits for normalized price rows. */
  parseCacheHits: number;
};

export class MetricsCollector {
  optimizationLatencyMs = 0;
  costGapVsGreedy = 0;
  wastePercent = 0;
  coverageRate = 0;
  avgStoresPerCart = 0;
  priceParseSuccessRate = 0;
  searchCacheHits = 0;
  searchCacheMisses = 0;
  parseCacheHits = 0;

  recordOptimizationLatency(ms: number): void {
    this.optimizationLatencyMs = ms;
  }

  recordCostGapVsGreedy(gap: number): void {
    this.costGapVsGreedy = gap;
  }

  recordWastePercent(pct: number): void {
    this.wastePercent = pct;
  }

  recordCoverageRate(rate: number): void {
    this.coverageRate = rate;
  }

  recordAvgStoresPerCart(n: number): void {
    this.avgStoresPerCart = n;
  }

  recordPriceParseSuccessRate(rate: number): void {
    this.priceParseSuccessRate = rate;
  }

  recordSearchCacheHits(hits: number, misses: number): void {
    this.searchCacheHits = hits;
    this.searchCacheMisses = misses;
  }

  recordParseCacheHits(n: number): void {
    this.parseCacheHits = n;
  }

  snapshot(): PipelineMetrics {
    return {
      optimizationLatencyMs: this.optimizationLatencyMs,
      costGapVsGreedy: this.costGapVsGreedy,
      wastePercent: this.wastePercent,
      coverageRate: this.coverageRate,
      avgStoresPerCart: this.avgStoresPerCart,
      priceParseSuccessRate: this.priceParseSuccessRate,
      searchCacheHits: this.searchCacheHits,
      searchCacheMisses: this.searchCacheMisses,
      parseCacheHits: this.parseCacheHits,
    };
  }

  reset(): void {
    this.optimizationLatencyMs = 0;
    this.costGapVsGreedy = 0;
    this.wastePercent = 0;
    this.coverageRate = 0;
    this.avgStoresPerCart = 0;
    this.priceParseSuccessRate = 0;
    this.searchCacheHits = 0;
    this.searchCacheMisses = 0;
    this.parseCacheHits = 0;
  }
}
