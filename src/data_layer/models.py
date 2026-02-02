"""Data models for the nutrition agent."""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict


@dataclass
class Ingredient:
    """Represents an ingredient in a recipe."""

    name: str  # Normalized name (e.g., "egg", "cream of rice")
    quantity: float  # Amount (e.g., 200.0, or 0.0 for "to taste")
    unit: str  # Unit (e.g., "g", "oz", "cup", "tsp", "tbsp", "to taste")
    is_to_taste: bool = False  # True if ingredient is "to taste" (excluded from nutrition)
    normalized_unit: str = ""  # Converted to base unit (e.g., "g" for grams)
    normalized_quantity: float = 0.0  # Quantity in base unit


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
class WeeklyNutritionTargets:
    """Represents weekly RDI targets for micronutrients.
    
    Values are WEEKLY totals (daily RDI × 7).
    A value of 0.0 means no target is set for that nutrient.
    Field names match MicronutrientProfile for easy comparison.
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
class NutritionProfile:
    """Represents nutrition information (macros, calories, and optional micronutrients)."""

    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    # Optional micronutrients - None for backward compatibility
    micronutrients: Optional[MicronutrientProfile] = None


@dataclass
class NutritionGoals:
    """Represents daily nutrition goals."""

    calories: int
    protein_g: float
    fat_g_min: float
    fat_g_max: float
    carbs_g: float


@dataclass
class Recipe:
    """Represents a recipe with ingredients and instructions."""

    id: str  # Unique identifier
    name: str  # Recipe name
    ingredients: List[Ingredient]  # List of ingredients
    cooking_time_minutes: int  # Total cooking time
    instructions: List[str]  # Step-by-step instructions
    # Future fields (post-MVP):
    # cuisine_type: Optional[str]
    # tags: List[str]
    # difficulty: Optional[str]


@dataclass
class Meal:
    """Represents a meal (recipe + context)."""

    recipe: Recipe
    nutrition: NutritionProfile  # Calculated nutrition for this meal
    meal_type: str  # "breakfast", "lunch", "dinner", "snack"
    scheduled_time: Optional[str] = None  # When to eat (optional)
    busyness_level: int = 3  # 1-4 scale (1=snack, 2=15min, 3=30min, 4=30+min)


@dataclass
class DailyMealPlan:
    """Represents a full day of meals."""

    date: str  # ISO date format
    meals: List[Meal]  # List of meals for the day
    total_nutrition: NutritionProfile  # Aggregated nutrition
    goals: NutritionGoals  # Target nutrition for the day
    meets_goals: bool  # Whether goals are met


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

    # Calorie Deficit Mode (optional hard constraint)
    max_daily_calories: Optional[int] = None  # Hard cap on daily calories

    # Weekly micronutrient targets (optional)
    weekly_targets: Optional[WeeklyNutritionTargets] = None

    # Future (post-MVP)
    # meal_prep_meals: List[Meal]


@dataclass
class DailyNutritionTracker:
    """Tracks nutrition consumed for a single day.
    
    Used to accumulate nutrition as meals are added throughout the day.
    Supports both macro and micronutrient tracking.
    """

    date: str  # ISO date format (e.g., "2024-01-15")

    # Macros (accumulated totals)
    calories: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0
    carbs_g: float = 0.0

    # Micronutrients (accumulated totals)
    micronutrients: MicronutrientProfile = field(
        default_factory=MicronutrientProfile
    )

    # Recipe/meal IDs consumed this day
    meal_ids: List[str] = field(default_factory=list)


@dataclass
class WeeklyNutritionTracker:
    """Tracks weekly nutrition totals and carryover needs.
    
    Per REASONING_LOGIC.md:
    - Running totals of all nutrients consumed so far this week
    - Days remaining in week
    - Nutrients that need to be carried forward from previous days
    
    Weekly tracking allows daily flexibility while ensuring weekly RDIs are met.
    """

    week_start_date: str  # ISO date format (Monday of the week)

    # Progress tracking
    days_completed: int = 0  # 0-7

    # Accumulated macro totals
    total_calories: float = 0.0
    total_protein_g: float = 0.0
    total_fat_g: float = 0.0
    total_carbs_g: float = 0.0

    # Accumulated micronutrient totals
    total_micronutrients: MicronutrientProfile = field(
        default_factory=MicronutrientProfile
    )

    # Daily tracker history
    daily_trackers: List[DailyNutritionTracker] = field(default_factory=list)

    # Carryover tracking: nutrient name -> deficit amount to make up
    # Per KNOWLEDGE.md: If Vitamin E is 96% today, need 104%+ tomorrow
    carryover_needs: Dict[str, float] = field(default_factory=dict)

