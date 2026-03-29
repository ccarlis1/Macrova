/**
 * Structured optimization errors for propagation across pipeline stages.
 */

/**
 * Cross-cutting error taxonomy (network, retailer, parsing, schema).
 * Maps to {@link OptimizationErrorCode} where applicable.
 */
export type DomainErrorType =
  | "TRANSIENT_NETWORK"
  | "STORE_BLOCKED"
  | "PARSE_FAILURE"
  | "SCHEMA_MISMATCH"
  | "NO_CANDIDATES";

export enum OptimizationErrorCode {
  /** One store/query search failed; other queries may still have returned candidates. */
  STORE_SEARCH_QUERY_FAILED = "STORE_SEARCH_QUERY_FAILED",
  NO_CANDIDATES = "NO_CANDIDATES",
  LOW_CONFIDENCE_MATCH = "LOW_CONFIDENCE_MATCH",
  UNIT_MISMATCH = "UNIT_MISMATCH",
  PRICE_PARSE_FAILED = "PRICE_PARSE_FAILED",
  INSUFFICIENT_QUANTITY = "INSUFFICIENT_QUANTITY",
  INTERNAL_ERROR = "INTERNAL_ERROR",
}

export type OptimizationError = {
  code: OptimizationErrorCode;
  message: string;
  ingredient?: string;
  severity: "warning" | "error";
};

export function err(
  code: OptimizationErrorCode,
  message: string,
  opts?: { ingredient?: string; severity?: "warning" | "error" },
): OptimizationError {
  return {
    code,
    message,
    ingredient: opts?.ingredient,
    severity: opts?.severity ?? "error",
  };
}

export function mergeErrors(
  ...groups: (readonly OptimizationError[] | undefined)[]
): OptimizationError[] {
  const out: OptimizationError[] = [];
  for (const g of groups) {
    if (!g) continue;
    out.push(...g);
  }
  return out;
}

/** Classify a thrown error or message into {@link DomainErrorType} (best-effort). */
export function classifyDomainError(err: unknown): DomainErrorType {
  const msg =
    err instanceof Error
      ? `${err.name} ${err.message}`
      : typeof err === "string"
        ? err
        : "unknown";
  const m = msg.toLowerCase();
  if (m.includes("blocked") || m.includes("forbidden") || m.includes("403")) {
    return "STORE_BLOCKED";
  }
  if (
    m.includes("parse") ||
    m.includes("json") ||
    m.includes("price") ||
    m.includes("size")
  ) {
    return "PARSE_FAILURE";
  }
  if (m.includes("schema") || m.includes("validation") || m.includes("unexpected")) {
    return "SCHEMA_MISMATCH";
  }
  if (m.includes("fetch") || m.includes("network") || m.includes("timeout") || m.includes("econn")) {
    return "TRANSIENT_NETWORK";
  }
  if (m.includes("candidate") || m.includes("no product")) {
    return "NO_CANDIDATES";
  }
  return "TRANSIENT_NETWORK";
}

export function isTransientDomainError(t: DomainErrorType): boolean {
  return t === "TRANSIENT_NETWORK";
}

const JITTER_MS = 37;

/**
 * Exponential backoff with jitter. Only {@link isTransientDomainError} should be retried by callers.
 */
export function computeRetryDelayMs(attempt: number, baseMs = 400): number {
  const exp = baseMs * 2 ** Math.max(0, attempt);
  const cap = Math.min(exp, 30_000);
  return Math.floor(cap + Math.random() * JITTER_MS);
}
