/**
 * Lightweight pipeline tracing (aggregation → normalization → search → optimization → cart).
 */

export type TraceStage =
  | "aggregation"
  | "normalization"
  | "search"
  | "price_normalization"
  | "optimization"
  | "cart";

export type TraceSpan = {
  stage: TraceStage;
  startedAtMs: number;
  endedAtMs?: number;
  runId?: string;
  meta?: Record<string, unknown>;
};

export class PipelineTrace {
  private readonly spans: TraceSpan[] = [];

  begin(stage: TraceStage, runId?: string, meta?: Record<string, unknown>): TraceSpan {
    const s: TraceSpan = {
      stage,
      startedAtMs: Date.now(),
      runId,
      meta,
    };
    this.spans.push(s);
    return s;
  }

  end(span: TraceSpan): void {
    span.endedAtMs = Date.now();
  }

  spansSnapshot(): readonly TraceSpan[] {
    return this.spans;
  }

  totalDurationMs(): number {
    if (this.spans.length === 0) return 0;
    const first = this.spans[0]!;
    const last = this.spans[this.spans.length - 1]!;
    const end = last.endedAtMs ?? last.startedAtMs;
    return Math.max(0, end - first.startedAtMs);
  }
}
