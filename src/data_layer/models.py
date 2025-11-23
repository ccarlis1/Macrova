"""Data models for the nutrition agent."""
from dataclasses import dataclass
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
class NutritionProfile:
    """Represents nutrition information (macros and calories)."""

    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    # Micronutrients (post-MVP)
    # fiber_g: float
    # vitamin_e_mg: float
    # etc.


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

    # Future (post-MVP)
    # meal_prep_meals: List[Meal]
    # weekly_targets: Dict[str, float]

