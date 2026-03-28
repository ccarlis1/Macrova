import {
  TinyFish,
  type AgentRunParams,
} from "@tiny-fish/sdk";

import { TinyFishClientError } from "./errors.js";
import {
  buildAddToCartGoal,
  buildProductSearchGoal,
  buildRecipeExtractionGoal,
} from "./goals.js";
import { toProductSearchResult } from "./parse-result.js";
import { streamUntilComplete } from "./stream-until-complete.js";
import type {
  AddToCartOptions,
  CartAutomationResult,
  CartLineItem,
  ExtractRecipeOptions,
  RecipeExtractionResult,
  RecipeIngredientLine,
  SearchProductsOptions,
  TinyFishAdapterRunOptions,
  TinyFishClientOptions,
} from "./types.js";

function toRunParams(
  url: string,
  goal: string,
  options?: { browserProfile?: AgentRunParams["browser_profile"]; proxyConfig?: AgentRunParams["proxy_config"] },
): AgentRunParams {
  return {
    url,
    goal,
    ...(options?.browserProfile !== undefined
      ? { browser_profile: options.browserProfile }
      : {}),
    ...(options?.proxyConfig !== undefined
      ? { proxy_config: options.proxyConfig }
      : {}),
  };
}

function asString(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}

function parseRecipeExtraction(
  recipe_url: string,
  raw: Record<string, unknown>,
): RecipeExtractionResult {
  const title = asString(raw["title"]);
  const servings = asString(raw["servings"]);
  const ingRaw = raw["ingredients"];
  const ingredients: RecipeIngredientLine[] = [];
  if (Array.isArray(ingRaw)) {
    for (const row of ingRaw) {
      if (typeof row !== "object" || row === null) {
        continue;
      }
      const o = row as Record<string, unknown>;
      const name = asString(o["name"]);
      if (!name) {
        continue;
      }
      ingredients.push({
        name,
        quantity: asString(o["quantity"]),
        unit: asString(o["unit"]),
        notes: asString(o["notes"]),
      });
    }
  }
  return {
    recipe_url,
    title,
    servings,
    ingredients,
    raw_result: raw,
  };
}

/**
 * Single entry point for TinyFish Web Agent in this repo.
 * Keep orchestration and goals here; nutrition math and price optimization stay outside.
 */
export class TinyFishClient {
  private readonly client: TinyFish;

  constructor(options?: TinyFishClientOptions) {
    this.client = new TinyFish({
      apiKey: options?.apiKey ?? process.env["TINYFISH_API_KEY"],
      baseURL: options?.baseURL,
      timeout: options?.timeout,
      maxRetries: options?.maxRetries,
    });
  }

  /**
   * Ingredient → product search on a specific store origin (`storeUrl`).
   * Returns normalized candidates; your layer computes $/oz, picks SKUs, etc.
   */
  async searchProducts(
    query: string,
    storeUrl: string,
    options?: SearchProductsOptions,
  ) {
    const maxResults = options?.maxResults ?? 5;
    const goal = buildProductSearchGoal(query, maxResults);
    const params = toRunParams(storeUrl, goal, options);
    const raw = await streamUntilComplete(
      this.client,
      params,
      options?.streamOptions,
    );
    return toProductSearchResult(query, storeUrl, raw);
  }

  /**
   * Recipe URL → structured ingredients for downstream meal-plan / grocery optimization.
   */
  async extractRecipe(
    recipeUrl: string,
    options?: ExtractRecipeOptions,
  ): Promise<RecipeExtractionResult> {
    const goal = buildRecipeExtractionGoal(
      options?.includeNutritionHints ?? false,
    );
    const params = toRunParams(recipeUrl, goal, options);
    const raw = await streamUntilComplete(
      this.client,
      params,
      options?.streamOptions,
    );
    return parseRecipeExtraction(recipeUrl, raw);
  }

  /**
   * Add one or more lines to the store cart. Optional cart confirmation step.
   * For heavy bot protection, pass `browserProfile: BrowserProfile.STEALTH` and optional `proxyConfig`.
   */
  async addToCart(
    storeUrl: string,
    items: CartLineItem[],
    options?: AddToCartOptions,
  ): Promise<CartAutomationResult> {
    if (items.length === 0) {
      throw new TinyFishClientError("addToCart requires at least one line item");
    }
    const goal = buildAddToCartGoal(items, options?.confirmInCart ?? true);
    const params = toRunParams(storeUrl, goal, options);
    const raw = await streamUntilComplete(
      this.client,
      params,
      options?.streamOptions,
    );
    return { store_url: storeUrl, raw_result: raw };
  }

  /** Low-level escape hatch: supply your own goal while still using streaming + shared error handling. */
  async runGoal(url: string, goal: string, options?: TinyFishAdapterRunOptions) {
    const params = toRunParams(url, goal, options);
    return streamUntilComplete(this.client, params, options?.streamOptions);
  }
}
