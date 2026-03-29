/**
 * Structured logging for pipeline steps (ingredient, store, query, timing).
 */

export type LogFields = {
  runId?: string;
  ingredientKey?: string;
  store?: string;
  query?: string;
  attempt?: number;
  durationMs?: number;
  resultCount?: number;
  stage?: string;
  message?: string;
  [k: string]: unknown;
};

export type LogSink = (level: "debug" | "info" | "warn" | "error", fields: LogFields) => void;

const defaultSink: LogSink = (level, fields) => {
  const line = JSON.stringify({ level, ts: new Date().toISOString(), ...fields });
  if (level === "error") {
    console.error(line);
  } else if (level === "warn") {
    console.warn(line);
  } else {
    console.log(line);
  }
};

let sink: LogSink = defaultSink;

export function setLogSink(next: LogSink): void {
  sink = next;
}

export function logInfo(fields: LogFields): void {
  sink("info", fields);
}

export function logWarn(fields: LogFields): void {
  sink("warn", fields);
}

export function logError(fields: LogFields): void {
  sink("error", fields);
}

export function logDebug(fields: LogFields): void {
  sink("debug", fields);
}
