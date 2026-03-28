import type {
  BrowserProfile,
  ProxyConfig,
  StreamOptions,
} from "@tiny-fish/sdk";

/** One product candidate returned from a grocery search (normalized downstream). */
export interface ProductCandidate {
  name: string;
  price: string | null;
  quantity_or_size: string | null;
  unit_price: string | null;
  /** Raw row from the agent when useful for debugging. */
  raw?: Record<string, unknown>;
}

/** Structured outcome for ingredient → product search. */
export interface ProductSearchResult {
  ingredient_query: string;
  store_url: string;
  products: ProductCandidate[];
  /** Unstructured payload from TinyFish (for debugging or custom parsers). */
  raw_result: Record<string, unknown>;
}

/** One line to add to a cart (your optimizer picks which products map here). */
export interface CartLineItem {
  /** Search phrase as the shopper would type it (e.g. "2L whole milk"). */
  searchQuery: string;
  /** Number of units to add (default 1). */
  quantity?: number;
  /** Prefer lowest unit price when multiple SKUs match. */
  preferCheapest?: boolean;
  /** Extra constraints for the agent (brand, organic, etc.). */
  notes?: string;
}

export interface CartAutomationResult {
  store_url: string;
  raw_result: Record<string, unknown>;
}

export interface RecipeIngredientLine {
  name: string;
  quantity: string | null;
  unit: string | null;
  notes?: string | null;
}

export interface RecipeExtractionResult {
  recipe_url: string;
  title: string | null;
  ingredients: RecipeIngredientLine[];
  servings: string | null;
  raw_result: Record<string, unknown>;
}

/** Shared options for adapter methods (streaming + anti-detection). */
export interface TinyFishAdapterRunOptions {
  /** Defaults to `BrowserProfile.LITE`; use `STEALTH` on protected storefronts. */
  browserProfile?: BrowserProfile;
  proxyConfig?: ProxyConfig;
  /** Forwarded to `client.agent.stream` for progress / live URL hooks. */
  streamOptions?: StreamOptions;
}

export interface SearchProductsOptions extends TinyFishAdapterRunOptions {
  /** How many top matches to return (default 5). */
  maxResults?: number;
}

export interface ExtractRecipeOptions extends TinyFishAdapterRunOptions {
  /** When true, ask for nutrition panel if visible (best-effort). */
  includeNutritionHints?: boolean;
}

export interface AddToCartOptions extends TinyFishAdapterRunOptions {
  /**
   * When true, the goal includes opening the cart and confirming items.
   * Set false only if you want a lighter-weight smoke run.
   */
  confirmInCart?: boolean;
}

export interface TinyFishClientOptions {
  /** Defaults to `process.env.TINYFISH_API_KEY`. */
  apiKey?: string;
  baseURL?: string;
  timeout?: number;
  maxRetries?: number;
}
