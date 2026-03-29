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
};

export class MetricsCollector {
  optimizationLatencyMs = 0;
  costGapVsGreedy = 0;
  wastePercent = 0;
  coverageRate = 0;
  avgStoresPerCart = 0;
  priceParseSuccessRate = 0;

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

  snapshot(): PipelineMetrics {
    return {
      optimizationLatencyMs: this.optimizationLatencyMs,
      costGapVsGreedy: this.costGapVsGreedy,
      wastePercent: this.wastePercent,
      coverageRate: this.coverageRate,
      avgStoresPerCart: this.avgStoresPerCart,
      priceParseSuccessRate: this.priceParseSuccessRate,
    };
  }

  reset(): void {
    this.optimizationLatencyMs = 0;
    this.costGapVsGreedy = 0;
    this.wastePercent = 0;
    this.coverageRate = 0;
    this.avgStoresPerCart = 0;
    this.priceParseSuccessRate = 0;
  }
}
