/**
 * Internal pipeline types for the grocery optimizer.
 * Phase 0 JSON contracts (`GroceryOptimizeRequest` / `GroceryOptimizeResponse`) stay stable at the API boundary;
 * these types power deterministic stages inside the package.
 */

import type { OptimizationError } from "./errors.js";
import type { PipelineMetrics } from "./observability/metrics.js";
import type { TraceSpan } from "./observability/tracing.js";

/** Standard `{ data, errors }` envelope for deterministic pipeline stages. */
export type PipelineResult<T> = {
  data: T | null;
  errors: OptimizationError[];
};

// --- Phase 0 meal plan shapes (do not rename fields used in JSON) ---

export interface MealPlanIngredient {
  name: string;
  quantity: number;
  unit: string;
  isToTaste?: boolean;
}

export interface MealPlanRecipe {
  id: string;
  name: string;
  ingredients: MealPlanIngredient[];
}

/** Mirrors `mealPlan` in `GroceryOptimizeRequest`. */
export interface MealPlanInput {
  id?: string;
  recipes: MealPlanRecipe[];
  /** recipeId → effective servings for the plan window (default 1 each). */
  recipeServings?: Record<string, number>;
}

export interface GroceryStoreRef {
  id: string;
  baseUrl: string;
}

/** JSON body for the Node CLI / FastAPI boundary (`stdin` / POST body). */
export interface GroceryOptimizeRequest {
  schemaVersion: string;
  mealPlan: MealPlanInput;
  preferences?: OptimizationPreferences;
  stores: GroceryStoreRef[];
  /** Correlates logs; generated when omitted. */
  runId?: string;
}

/** Ingredient rows omitted from retailer search (e.g. pantry staples). */
export interface SkippedSearchIngredient {
  canonicalKey: string;
  displayName: string;
  reason: "low_value";
}

/** Successful `result` payload (camelCase JSON). */
export interface GroceryOptimizeSuccessResult {
  runId: string;
  mealPlanId?: string;
  multiStoreOptimization: MultiStoreOptimizationResult;
  cartPlan: CartPlan;
  metrics: PipelineMetrics;
  stores: GroceryStoreRef[];
  /** Stage timing spans (aggregation → search → optimization → cart). */
  pipelineTrace?: readonly TraceSpan[];
  /** Ingredients not sent to TinyFish (transparent UX / cost control). */
  skippedIngredients?: SkippedSearchIngredient[];
}

export interface GroceryOptimizeErrorBody {
  message: string;
  code?: string;
  details?: unknown;
}

export interface GroceryOptimizeResponse {
  schemaVersion: "1.0";
  ok: boolean;
  result: GroceryOptimizeSuccessResult | null;
  error: GroceryOptimizeErrorBody | null;
}

/**
 * Objective mode for the optimizer. Legacy `minimize_*` values remain accepted
 * alongside `min_cost` / `min_waste` for Phase 0 compatibility.
 */
export type OptimizationObjective =
  | "min_cost"
  | "min_waste"
  | "balanced"
  | "minimize_cost"
  | "minimize_waste";

/** Mirrors `preferences` in `GroceryOptimizeRequest` (subset used by the optimizer). */
export interface OptimizationPreferences {
  objective?: OptimizationObjective;
  /** Multiplier on `(quantityPurchased - required)` when minimizing effective cost. */
  wastePenaltyPerUnit?: number;
  /** Penalty per extra store beyond the first in a purchase scope (cart-level). */
  storeSplitPenalty?: number;
  /** Weight on low-confidence product matches / parses. */
  confidencePenalty?: number;
  maxCandidatesPerQuery?: number;
  /** Minimum Jaro–Winkler similarity to accept a fuzzy synonym match (0–1). */
  fuzzyMatchThreshold?: number;
  /** When set, caps distinct stores in a multi-store cart (Phase 3). */
  maxStores?: number;
  /** When false, single-store per-ingredient behavior is preferred (frontier collapses). */
  allowMultiStore?: boolean;
  /** Max concurrent TinyFish ingredient searches (default 3). */
  searchConcurrency?: number;
}

// --- Aggregation ---

export interface RawIngredientLine {
  recipeId: string;
  recipeName: string;
  name: string;
  quantity: number;
  unit: string;
  isToTaste?: boolean;
}

export interface SourceRecipeRef {
  recipeId: string;
  recipeName: string;
}

/** After aggregation: one row per canonical ingredient with combined need. */
export interface AggregatedIngredient {
  canonicalKey: string;
  displayName: string;
  /** Total required amount in `normalizedUnit`. */
  totalQuantity: number;
  normalizedUnit: NormalizedUnitKind;
  sourceRecipes: SourceRecipeRef[];
  isToTaste: boolean;
  /** Lowest name-normalization confidence merged into this row. */
  nameConfidence?: number;
}

// --- Normalization ---

export interface NormalizedName {
  canonical: string;
  key: string;
  /** Set when a fuzzy synonym was used instead of an exact map entry. */
  fuzzyMatched?: boolean;
  /** Lower is worse; 1 = exact / synonym hit. */
  confidence: number;
}

export type NormalizedUnitKind = "mass_g" | "volume_ml" | "count";

export interface NormalizedQuantity {
  value: number;
  kind: NormalizedUnitKind;
  /** True when volume↔mass would need unknown density. */
  isAmbiguous?: boolean;
}

export interface IngredientMeta {
  /** Grams per ml for this ingredient, when converting volume ↔ mass. */
  densityGPerMl?: number;
}

/** Target units for normalizing shelf prices against a recipe line. */
export interface IngredientUnitContext {
  kind: NormalizedUnitKind;
  densityGPerMl?: number;
}

// --- Product search ---

export interface ProductCandidate {
  id: string;
  name: string;
  priceRaw: string | null;
  sizeRaw: string | null;
  unitPriceRaw: string | null;
  brand?: string | null;
  storeId: string;
  query: string;
  raw?: Record<string, unknown>;
}

export interface ProductCandidateSet {
  ingredientKey: string;
  candidates: ProductCandidate[];
}

export interface RankedProduct extends ProductCandidate {
  rankScore: number;
  nameSimilarity: number;
  unitCompatible: boolean;
  priceComplete: boolean;
}

// --- Price normalization ---

export type ParseConfidence = "high" | "medium" | "low";

export interface ParsedSize {
  /** Total physical amount in base units (g, ml, or count). */
  totalAmount: number;
  kind: NormalizedUnitKind;
  multiplier?: number;
  perPackAmount?: number;
  confidence: ParseConfidence;
  raw: string;
}

export interface NormalizedProduct {
  candidate: ProductCandidate;
  parsedSize: ParsedSize | null;
  /** Price per `ingredientUnitContext` base unit (e.g. $/g). */
  unitPrice: number | null;
  totalPackPrice: number | null;
  normalizedPackQuantity: number | null;
  confidence: ParseConfidence;
  lowConfidence: boolean;
}

// --- Optimization ---

export interface NormalizedProductOffer {
  product: NormalizedProduct;
  /** Pack size in the same base units as the ingredient requirement. */
  packQuantity: number;
  packPrice: number;
}

export interface IngredientRequirement {
  canonicalKey: string;
  displayName: string;
  quantity: number;
  kind: NormalizedUnitKind;
}

export interface SelectedProduct {
  product: NormalizedProduct;
  /** How many packs of this SKU to buy. */
  packCount: number;
}

export interface IngredientSolution {
  requirement: IngredientRequirement;
  products: SelectedProduct[];
  totalCost: number;
  waste: number;
  confidence: number;
  partial: boolean;
  /** Why partial / no full coverage. */
  reason?: string;
}

/** Structured, human-readable rationale for one ingredient line. */
export interface Explanation {
  ingredient: string;
  reasoning: string[];
  alternativesConsidered: {
    product: string;
    rejectedReason: string;
  }[];
}

export interface OptimizationResult {
  selectedProducts: SelectedProduct[];
  totalCost: number;
  storeBreakdown: Record<string, number>;
  unmetRequirements: string[];
  perIngredient: IngredientSolution[];
  /** One entry per optimized ingredient (same order as `perIngredient` when applicable). */
  explanations: Explanation[];
  /** Non-fatal warnings and fatal issues collected across the pipeline. */
  errors: OptimizationError[];
}

/** Phase 3: global cart grouped by retailer id after multi-store optimization. */
export interface MultiStoreOptimizationResult {
  storePlans: Record<string, SelectedProduct[]>;
  totalCost: number;
  totalWaste: number;
  storesUsed: string[];
  confidence: number;
  perIngredient: IngredientSolution[];
  explanations: Explanation[];
  errors: OptimizationError[];
  /** When true, a cheaper exhaustive search was skipped or relaxed. */
  degraded?: boolean;
  reason?: string;
}

/** One cart line for execution (add-to-cart). */
export interface CartLinePlan {
  storeId: string;
  storeUrl: string;
  ingredientKey: string;
  searchQuery: string;
  quantity: number;
  /** Stable idempotency key for this line. */
  signatureHash: string;
  preferCheapest?: boolean;
  notes?: string;
}

export interface CartPlan {
  lines: CartLinePlan[];
  runId?: string;
}

export interface CartFailure {
  storeId: string;
  ingredientKey?: string;
  message: string;
  code?: string;
}

export interface CartExecutionResult {
  success: boolean;
  storesCompleted: string[];
  failures: CartFailure[];
  durationMs: number;
}

/** Progress events while executing a cart plan. */
export type CartExecutionProgress = {
  stage: "opening_store" | "adding_item" | "store_done" | "aborted";
  store: string;
  ingredientKey?: string;
  /** 0–1 within current store or overall heuristic. */
  progress: number;
};

/** Full per-ingredient outcome including errors and explanation (Phase 2). */
export interface IngredientOptimizationResult {
  solution: IngredientSolution;
  errors: OptimizationError[];
  explanation: Explanation;
}
