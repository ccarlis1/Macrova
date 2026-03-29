/**
 * Turn optimization output into executable cart plans and drive TinyFish add-to-cart flows.
 */

import { createHash } from "node:crypto";

import type { AddToCartOptions, CartLineItem } from "@nutrition-agent/tinyfish-client";

import type {
  CartExecutionProgress,
  CartExecutionResult,
  CartFailure,
  CartLinePlan,
  CartPlan,
  MultiStoreOptimizationResult,
  OptimizationResult,
  SelectedProduct,
} from "./types.js";
import type { TinyFishAdapter } from "./tinyfish/TinyFishAdapter.js";

function hashSignature(parts: string[]): string {
  return createHash("sha256").update(parts.join("|")).digest("hex").slice(0, 40);
}

/** Stable idempotency key for a selected SKU line. */
export function selectedProductSignature(sp: SelectedProduct): string {
  const c = sp.product.candidate;
  return hashSignature([
    c.storeId,
    c.id,
    c.name,
    String(sp.packCount),
    String(c.priceRaw ?? ""),
    String(c.sizeRaw ?? ""),
  ]);
}

/**
 * Build a {@link CartPlan} from a multi-store optimization result.
 * `storeUrlById` maps retailer ids to storefront origins used by TinyFish.
 */
export function buildCartPlan(
  result: MultiStoreOptimizationResult,
  storeUrlById: Record<string, string>,
  runId?: string,
): CartPlan {
  const lines: CartLinePlan[] = [];
  for (const sol of result.perIngredient) {
    const ingredientKey = sol.requirement.canonicalKey;
    for (const sp of sol.products) {
      const storeId = sp.product.candidate.storeId;
      const storeUrl = storeUrlById[storeId];
      if (!storeUrl) continue;
      lines.push({
        storeId,
        storeUrl,
        ingredientKey,
        searchQuery: sp.product.candidate.name,
        quantity: Math.max(1, Math.round(sp.packCount)),
        signatureHash: selectedProductSignature(sp),
        preferCheapest: true,
      });
    }
  }
  return { lines, runId };
}

/** Build a cart plan from a flat Phase 1/2 {@link OptimizationResult} and store URL map. */
export function buildCartPlanFromOptimization(
  result: OptimizationResult,
  storeUrlById: Record<string, string>,
  runId?: string,
): CartPlan {
  const byStore: Record<string, SelectedProduct[]> = {};
  for (const sp of result.selectedProducts) {
    const sid = sp.product.candidate.storeId;
    if (!byStore[sid]) byStore[sid] = [];
    byStore[sid]!.push(sp);
  }
  return buildCartPlan(
    {
      storePlans: byStore,
      totalCost: result.totalCost,
      totalWaste: result.perIngredient.reduce((a, s) => a + s.waste, 0),
      storesUsed: Object.keys(byStore).sort(),
      confidence: result.perIngredient.length
        ? Math.min(...result.perIngredient.map((p) => p.confidence))
        : 1,
      perIngredient: result.perIngredient,
      explanations: result.explanations,
      errors: result.errors,
    },
    storeUrlById,
    runId,
  );
}

export type CartExecutionOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
  onProgress?: (e: CartExecutionProgress) => void;
  /** Per-add-to-cart TinyFish options (browser profile, confirm cart, …). */
  addToCartOptions?: Omit<AddToCartOptions, "signal"> & { signal?: AbortSignal };
};

function withTimeout<T>(p: Promise<T>, ms: number | undefined, signal?: AbortSignal): Promise<T> {
  if (!ms || ms <= 0) return p;
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => {
      const e = new Error(`Cart execution timed out after ${ms}ms`);
      e.name = "TimeoutError";
      reject(e);
    }, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      const e = new Error("Aborted");
      e.name = "AbortError";
      reject(e);
    });
    p.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (err) => {
        clearTimeout(t);
        reject(err);
      },
    );
  });
}

/**
 * Execute a cart plan by store: one addToCart call per store with deduped line items.
 */
export async function executeCartPlan(
  cartPlan: CartPlan,
  adapter: Pick<TinyFishAdapter, "addToCart">,
  options?: CartExecutionOptions,
): Promise<CartExecutionResult> {
  const started = Date.now();
  const failures: CartFailure[] = [];
  const storesCompleted: string[] = [];
  const seenGlobal = new Set<string>();

  const byStore = new Map<string, CartLinePlan[]>();
  for (const line of cartPlan.lines) {
    const list = byStore.get(line.storeId) ?? [];
    list.push(line);
    byStore.set(line.storeId, list);
  }

  let storeIndex = 0;
  const storeTotal = byStore.size;

  for (const [storeId, lines] of byStore) {
    const storeUrl = lines[0]?.storeUrl ?? "";
    options?.onProgress?.({
      stage: "opening_store",
      store: storeId,
      progress: storeIndex / Math.max(1, storeTotal),
    });

    const items: CartLineItem[] = [];
    const seenLocal = new Set<string>();
    let lineIdx = 0;
    for (const line of lines) {
      if (seenGlobal.has(line.signatureHash)) {
        options?.onProgress?.({
          stage: "adding_item",
          store: storeId,
          ingredientKey: line.ingredientKey,
          progress: (lineIdx + 1) / lines.length,
        });
        lineIdx++;
        continue;
      }
      if (seenLocal.has(line.signatureHash)) {
        lineIdx++;
        continue;
      }
      seenLocal.add(line.signatureHash);
      seenGlobal.add(line.signatureHash);
      items.push({
        searchQuery: line.searchQuery,
        quantity: line.quantity,
        preferCheapest: line.preferCheapest ?? true,
        notes: line.notes,
      });
      options?.onProgress?.({
        stage: "adding_item",
        store: storeId,
        ingredientKey: line.ingredientKey,
        progress: (lineIdx + 1) / lines.length,
      });
      lineIdx++;
    }

    if (items.length === 0) {
      storesCompleted.push(storeId);
      storeIndex++;
      continue;
    }

    try {
      const run = adapter.addToCart(storeUrl, items, {
        ...options?.addToCartOptions,
        signal: options?.signal,
      });
      await withTimeout(run, options?.timeoutMs, options?.signal);
      storesCompleted.push(storeId);
      options?.onProgress?.({
        stage: "store_done",
        store: storeId,
        progress: 1,
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      failures.push({ storeId, message, code: (e as Error)?.name });
    }
    storeIndex++;
  }

  const durationMs = Date.now() - started;
  return {
    success: failures.length === 0,
    storesCompleted,
    failures,
    durationMs,
  };
}
