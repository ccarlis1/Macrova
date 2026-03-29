import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it, beforeAll } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const pkgRoot = resolve(here, "..");

beforeAll(() => {
  execFileSync("npm", ["run", "build"], { cwd: pkgRoot, stdio: "inherit" });
});

describe("dist/run.js e2e", () => {
  it("runs the full pipeline with mock TinyFish and returns a cart plan", () => {
    const request = {
      schemaVersion: "1.0",
      mealPlan: {
        id: "p1",
        recipes: [
          {
            id: "r1",
            name: "Bowl",
            ingredients: [
              { name: "chicken breast", quantity: 1, unit: "lb" },
              { name: "olive oil", quantity: 2, unit: "tbsp" },
            ],
          },
        ],
        recipeServings: { r1: 2 },
      },
      preferences: { objective: "balanced" as const },
      stores: [{ id: "walmart", baseUrl: "https://www.walmart.com" }],
    };

    const runJs = resolve(pkgRoot, "dist/run.js");
    const out = execFileSync("node", [runJs], {
      input: `${JSON.stringify(request)}\n`,
      encoding: "utf8",
      env: { ...process.env, GROCERY_OPTIMIZER_USE_MOCK: "1" },
    });

    const parsed = JSON.parse(out.trim()) as {
      ok: boolean;
      result?: { cartPlan?: { lines: unknown[] }; metrics?: { optimizationLatencyMs: number } };
    };
    expect(parsed.ok).toBe(true);
    expect(parsed.result?.metrics?.optimizationLatencyMs).toBeGreaterThanOrEqual(0);
    expect(parsed.result?.cartPlan?.lines?.length ?? 0).toBeGreaterThan(0);
  });
});
