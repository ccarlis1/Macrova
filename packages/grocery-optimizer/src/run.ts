/**
 * Phase 0 entry: read `GroceryOptimizeRequest` JSON from stdin, write `GroceryOptimizeResponse` to stdout.
 */

import { readFileSync } from "node:fs";

import { runGroceryPipeline } from "./grocery_pipeline.js";
import { setLogSink } from "./observability/logger.js";
import { createSearchAdapterFromEnv } from "./run_adapter.js";

/** Keep stdout JSON-only for FastAPI subprocess contract. */
setLogSink((_level, fields) => {
  const line = JSON.stringify({ ts: new Date().toISOString(), ...fields });
  console.error(line);
});

function readStdinUtf8(): string {
  return readFileSync(0, "utf8");
}

void (async () => {
  const raw = readStdinUtf8().trim();
  if (!raw) {
    const err = {
      schemaVersion: "1.0" as const,
      ok: false,
      result: null,
      error: { message: "Empty stdin" },
    };
    process.stdout.write(`${JSON.stringify(err)}\n`);
    process.exitCode = 1;
    return;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw) as unknown;
  } catch {
    const err = {
      schemaVersion: "1.0" as const,
      ok: false,
      result: null,
      error: { message: "Invalid JSON on stdin" },
    };
    process.stdout.write(`${JSON.stringify(err)}\n`);
    process.exitCode = 1;
    return;
  }

  try {
    const response = await runGroceryPipeline(parsed, {
      adapter: createSearchAdapterFromEnv(),
    });
    process.stdout.write(`${JSON.stringify(response)}\n`);
    process.exitCode = response.ok ? 0 : 1;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    const err = {
      schemaVersion: "1.0" as const,
      ok: false,
      result: null,
      error: {
        message: `Pipeline error: ${msg}`,
        code: "INTERNAL_ERROR",
      },
    };
    process.stdout.write(`${JSON.stringify(err)}\n`);
    process.exitCode = 1;
  }
})();
