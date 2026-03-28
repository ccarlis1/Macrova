/**
 * Internal pipeline types for the grocery optimizer.
 * Phase 0 JSON contracts (`GroceryOptimizeRequest` / `GroceryOptimizeResponse`) stay stable at the API boundary;
 * these types power deterministic stages inside the package.
 */

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

export type OptimizationObjective = "minimize_cost" | "minimize_waste" | "balanced";

/** Mirrors `preferences` in `GroceryOptimizeRequest` (subset used by Phase 1). */
export interface OptimizationPreferences {
  objective?: OptimizationObjective;
  /** Multiplier on `(quantityPurchased - required)` when minimizing effective cost. */
  wastePenaltyPerUnit?: number;
  maxCandidatesPerQuery?: number;
  /** Minimum Jaro–Winkler similarity to accept a fuzzy synonym match (0–1). */
  fuzzyMatchThreshold?: number;
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

export interface OptimizationResult {
  selectedProducts: SelectedProduct[];
  totalCost: number;
  storeBreakdown: Record<string, number>;
  unmetRequirements: string[];
  perIngredient: IngredientSolution[];
}
