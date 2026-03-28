/**
 * Phase 0 entry: read GroceryOptimizeRequest JSON from stdin, write GroceryOptimizeResponse to stdout.
 * Optimization logic lives in later phases; this stub validates the wiring.
 */

import { readFileSync } from "node:fs";

function readStdinUtf8(): string {
  return readFileSync(0, "utf8");
}

function main(): void {
  const raw = readStdinUtf8().trim();
  if (!raw) {
    const err = {
      schemaVersion: "1.0",
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
      schemaVersion: "1.0",
      ok: false,
      result: null,
      error: { message: "Invalid JSON on stdin" },
    };
    process.stdout.write(`${JSON.stringify(err)}\n`);
    process.exitCode = 1;
    return;
  }

  if (typeof parsed !== "object" || parsed === null) {
    const err = {
      schemaVersion: "1.0",
      ok: false,
      result: null,
      error: { message: "Request JSON must be an object" },
    };
    process.stdout.write(`${JSON.stringify(err)}\n`);
    process.exitCode = 1;
    return;
  }

  const response = {
    schemaVersion: "1.0",
    ok: true,
    result: {
      message: "stub response",
    },
    error: null,
  };

  process.stdout.write(`${JSON.stringify(response)}\n`);
}

main();
