/**
 * TinyFish adapter for the nutrition / grocery optimization stack.
 * Use {@link TinyFishClient} from application code; avoid importing `@tiny-fish/sdk` elsewhere.
 */

export { TinyFishClient } from "./TinyFishClient.js";
export { TinyFishClientError } from "./errors.js";
export { streamUntilComplete } from "./stream-until-complete.js";
export {
  buildAddToCartGoal,
  buildProductSearchGoal,
  buildRecipeExtractionGoal,
} from "./goals.js";
export {
  extractProductArray,
  normalizeProductCandidate,
  toProductSearchResult,
} from "./parse-result.js";

export type {
  AddToCartOptions,
  CartAutomationResult,
  CartLineItem,
  ExtractRecipeOptions,
  ProductCandidate,
  ProductSearchResult,
  RecipeExtractionResult,
  RecipeIngredientLine,
  SearchProductsOptions,
  TinyFishAdapterRunOptions,
  TinyFishClientOptions,
} from "./types.js";

// Re-export SDK enums/types commonly needed for stealth / proxy configuration.
export {
  BrowserProfile,
  EventType,
  ProxyCountryCode,
  RunStatus,
} from "@tiny-fish/sdk";
export type { AgentRunParams, ProxyConfig, StreamOptions } from "@tiny-fish/sdk";
