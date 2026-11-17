"""Data models for the nutrition agent."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.models.schedule import DaySchedule


@dataclass
class Ingredient:
    """Represents an ingredient in a recipe."""

    name: str  # Normalized name (e.g., "egg", "cream of rice")
    quantity: float  # Amount (e.g., 200.0, or 0.0 for "to taste")
    unit: str  # Unit (e.g., "g", "oz", "cup", "tsp", "tbsp", "to taste")
    is_to_taste: bool = False  # True if ingredient is "to taste" (excluded from nutrition)
    normalized_unit: str = ""  # Converted to base unit (e.g., "g" for grams)
    normalized_quantity: float = 0.0  # Quantity in base unit
    # Weight in grams of one ``unit`` of this line, sent by the client (Sprint 2 BE-19).
    # Used only when the ingredient record has no conversion for the unit; never
    # written to the reference ingredient table.
    grams_per_unit: Optional[float] = None


@dataclass
class IngredientInput:
    """Structured input for ingredient validation (MVP parsing).
    
    Per SYSTEM_RULES.md:
    - All three fields are REQUIRED (no guessing)
    - This is the input format before validation
    - Ambiguous or missing fields should not reach this model
    """
    name: str       # Ingredient name (e.g., "chicken breast")
    quantity: float # Amount (e.g., 200.0)
    unit: str       # Unit (e.g., "g", "oz", "cup", "to taste")


@dataclass
class ValidatedIngredient:
    """Validated and normalized ingredient ready for nutrition lookup.
    
    Per SYSTEM_RULES.md:
    - Only validated ingredients are used for nutrition calculations
    - Normalization converts to base units (g, ml) where applicable
    - "to taste" ingredients have is_to_taste=True and are excluded from nutrition
    
    Per Step 2.1 (Ingredient Name Normalization):
    - canonical_name is the normalized name for USDA API lookup
    - Lowercased, whitespace-normalized, controlled descriptors removed
    """
    name: str                   # Original ingredient name (preserved)
    quantity: float             # Original quantity
    unit: str                   # Original unit
    normalized_quantity: float  # Quantity in base unit
    normalized_unit: str        # Base unit (g, ml, or special like "large", "scoop")
    is_to_taste: bool           # True if "to taste" (excluded from nutrition)
    canonical_name: str = ""    # Normalized name for USDA API lookup (Step 2.1)


@dataclass
class MicronutrientProfile:
    """Represents micronutrient values (vitamins, minerals, etc.).
    
    All values default to 0.0, allowing partial specification.
    Units follow standard conventions:
    - _ug: micrograms
    - _mg: milligrams
    - _g: grams
    - _iu: international units (Vitamin D)
    """

    # Vitamins
    vitamin_a_ug: float = 0.0
    vitamin_c_mg: float = 0.0
    vitamin_d_iu: float = 0.0
    vitamin_e_mg: float = 0.0
    vitamin_k_ug: float = 0.0
    b1_thiamine_mg: float = 0.0
    b2_riboflavin_mg: float = 0.0
    b3_niacin_mg: float = 0.0
    b5_pantothenic_acid_mg: float = 0.0
    b6_pyridoxine_mg: float = 0.0
    b12_cobalamin_ug: float = 0.0
    folate_ug: float = 0.0

    # Minerals
    calcium_mg: float = 0.0
    copper_mg: float = 0.0
    iron_mg: float = 0.0
    magnesium_mg: float = 0.0
    manganese_mg: float = 0.0
    phosphorus_mg: float = 0.0
    potassium_mg: float = 0.0
    selenium_ug: float = 0.0
    sodium_mg: float = 0.0
    zinc_mg: float = 0.0

    # Other
    fiber_g: float = 0.0
    omega_3_g: float = 0.0
    omega_6_g: float = 0.0


@dataclass
class UpperLimits:
    """Daily upper tolerable intake limits for micronutrients.
    
    Field names EXACTLY match MicronutrientProfile for easy comparison.
    A value of None means no UL is established (validation skipped for that nutrient).
    Values are DAILY limits (not weekly).
    
    Units follow standard conventions (same as MicronutrientProfile):
    - _ug: micrograms
    - _mg: milligrams
    - _g: grams
    - _iu: international units (Vitamin D)
    
    Source: IOM DRI / EFSA guidelines (loaded from data/reference/ul_by_demographic.json)
    """

    # Vitamins
    vitamin_a_ug: Optional[float] = None
    vitamin_c_mg: Optional[float] = None
    vitamin_d_iu: Optional[float] = None
    vitamin_e_mg: Optional[float] = None
    vitamin_k_ug: Optional[float] = None
    b1_thiamine_mg: Optional[float] = None
    b2_riboflavin_mg: Optional[float] = None
    b3_niacin_mg: Optional[float] = None
    b5_pantothenic_acid_mg: Optional[float] = None
    b6_pyridoxine_mg: Optional[float] = None
    b12_cobalamin_ug: Optional[float] = None
    folate_ug: Optional[float] = None

    # Minerals
    calcium_mg: Optional[float] = None
    copper_mg: Optional[float] = None
    iron_mg: Optional[float] = None
    magnesium_mg: Optional[float] = None
    manganese_mg: Optional[float] = None
    phosphorus_mg: Optional[float] = None
    potassium_mg: Optional[float] = None
    selenium_ug: Optional[float] = None
    sodium_mg: Optional[float] = None
    zinc_mg: Optional[float] = None

    # Other
    fiber_g: Optional[float] = None
    omega_3_g: Optional[float] = None
    omega_6_g: Optional[float] = None


@dataclass
class NutritionProfile:
    """Represents nutrition information (macros, calories, and optional micronutrients)."""

    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    # Optional micronutrients - None for backward compatibility
    micronutrients: Optional[MicronutrientProfile] = None


@dataclass
class Recipe:
    """Represents a recipe with ingredients and instructions."""

    id: str  # Unique identifier
    name: str  # Recipe name
    ingredients: List[Ingredient]  # List of ingredients
    cooking_time_minutes: int  # Total cooking time
    instructions: List[str]  # Step-by-step instructions
    default_servings: int = 1
    # Deprecated compatibility projection only. Canonical planner/filter tags live in
    # data/recipes/recipe_tags.json -> tags_by_id.
    tags: List[Dict[str, str]] = field(default_factory=list)
    # Optional provenance for generated/synced recipes: source, created_at, model,
    # cooking_time_source, resolved ingredient fdc_ids, validation version.
    provenance: Optional[Dict[str, object]] = None

    @property
    def is_meal_prep_capable(self) -> bool:
        """True when recipe serves 2+ and has a context meal-prep tag."""
        if self.default_servings < 2:
            return False
        for tag in self.tags:
            if tag.get("slug") == "meal-prep" and tag.get("type") == "context":
                return True
        return False


@dataclass
class UserProfile:
    """Represents user preferences and goals."""

    # Nutrition Goals
    daily_calories: int
    daily_protein_g: float
    daily_fat_g: Tuple[float, float]  # (min, max) range
    daily_carbs_g: float  # Calculated from remaining calories

    # Schedule Constraints
    schedule: Dict[str, int]  # {"08:00": 2, "12:00": 3, "18:00": 3}
    # Time -> busyness level (1-4)

    # Preferences
    liked_foods: List[str]  # Foods to prefer
    disliked_foods: List[str]  # Foods to avoid
    allergies: List[str]  # Allergens to avoid
    # Optional dietary flags (gluten_free, dairy_free, vegetarian, vegan).
    # Mapped into HC-1 exclusions in convert_profile; also used as tag filters.
    dietary_flags: Optional[List[str]] = None

    # Calorie Deficit Mode (optional hard constraint)
    max_daily_calories: Optional[int] = None  # Hard cap on daily calories

    # Daily micronutrient RDI targets (optional); keys = MicronutrientProfile field names
    daily_micronutrient_targets: Optional[Dict[str, float]] = None

    # τ: minimum fraction of prorated weekly RDI (daily × D) required per tracked nutrient (default strict)
    micronutrient_weekly_min_fraction: float = 1.0

    # Canonical per-day schedule (meals + workouts). When set, ``schedule`` is
    # derived meal-only (1–4) for legacy planner paths.
    schedule_days: Optional[List[DaySchedule]] = None

    # Canonical slot pins persisted in profile storage.
    pins: Optional[List["ProfilePin"]] = None

    # Optional demographic (one of ``upper_limits.DEMOGRAPHICS``). When set, the
    # planner enforces that demographic's daily upper limits. It does not set
    # micronutrient targets (Sprint 2 BE-17). None means no ULs.
    demographic: Optional[str] = None

    # Future (post-MVP)
    # meal_prep_meals: List[Meal]


@dataclass(frozen=True)
class ProfilePin:
    """Canonical persisted profile pin."""

    day_index: int
    slot_index: int
    recipe_id: str
