/**
 * Package defaults (preferences, optional default stores) for CLI runs.
 * Merged in {@link runGroceryPipeline} when the request omits values.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import type { GroceryStoreRef, OptimizationPreferences } from "./types.js";

export type GroceryOptimizerDefaultsFile = {
  preferences?: OptimizationPreferences;
  stores?: GroceryStoreRef[];
};

let cached: GroceryOptimizerDefaultsFile | null = null;

/** Load `grocery-optimizer.defaults.json` next to the package root (resolved from `dist/`). */
export function loadGroceryOptimizerDefaults(): GroceryOptimizerDefaultsFile {
  if (cached) {
    return cached;
  }
  const path = fileURLToPath(
    new URL("../grocery-optimizer.defaults.json", import.meta.url),
  );
  try {
    const raw = readFileSync(path, "utf8");
    cached = JSON.parse(raw) as GroceryOptimizerDefaultsFile;
  } catch {
    cached = { preferences: {}, stores: [] };
  }
  return cached;
}
