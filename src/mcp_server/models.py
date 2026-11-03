"""Pydantic models for the MCP tools' inputs and ``structuredContent``.

The SDK builds each tool's ``inputSchema`` from its parameters and its
``outputSchema`` from the result model here. Days and meals are 1-based
(see :mod:`src.mcp_server.indexing`).
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from src.mcp_server.nutrients import Demographic


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Shared ------------------------------------------------------------------


class RecipeIngredient(_Input):
    name: str = Field(min_length=1)
    quantity: float = Field(ge=0)
    unit: str = Field(min_length=1, description='g, oz, cup, tbsp, tsp, large, scoop, … or "to taste".')


class Recipe(_Input):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    ingredients: List[RecipeIngredient] = Field(
        min_length=1,
        description="Quantities for ONE serving: the planner counts the whole list as one meal.",
    )
    cooking_time_minutes: int = Field(default=0, ge=0)
    instructions: List[str] = Field(default_factory=list)
    tags: List[str] = Field(
        default_factory=list,
        description="Flat list of tag slugs from macrova_list_tags; the server sorts them into tag types.",
    )


# --- macrova_plan_meals: input ------------------------------------------------


class Targets(_Input):
    daily_calories: int = Field(ge=800, le=6000)
    daily_protein_g: float = Field(ge=0)
    daily_fat_g_min: float = Field(ge=0)
    daily_fat_g_max: float = Field(ge=0)
    max_daily_calories: Optional[int] = Field(
        default=None, gt=0, description="Optional hard daily ceiling (deficit mode)."
    )
    demographic: Optional[Demographic] = Field(
        default=None,
        description=(
            "Selects the recommended daily intakes (met as weekly totals) and the daily upper "
            "limits for micronutrients. Omit to skip micronutrients."
        ),
    )


class Preferences(_Input):
    excluded_ingredients: List[str] = Field(
        default_factory=list, description="Allergies and dislikes; never used."
    )
    liked_foods: List[str] = Field(default_factory=list, description="Tie-breaker only.")


class ShorthandSchedule(_Input):
    """The same meals every day."""

    meals_per_day: int = Field(ge=1, le=8)
    busyness: Optional[int] = Field(
        default=None,
        ge=1,
        le=4,
        description="Applied to every meal. If omitted: 2 for the first meal, 3 for the rest.",
    )


class ScheduledMeal(_Input):
    meal: int = Field(ge=1)
    busyness: int = Field(ge=1, le=4, description="1 snack/quick · 2 ≤15 min · 3 ≤30 min · 4 30+ min/meal prep")
    label: Optional[str] = Field(default=None, description="breakfast, lunch, dinner, snack…")
    time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    required_tags: List[str] = Field(default_factory=list, description="Slugs from macrova_list_tags.")
    preferred_tags: List[str] = Field(default_factory=list)


class Workout(_Input):
    after_meal: int = Field(ge=1)
    type: Literal["AM", "PM", "general"]
    intensity: Optional[Literal["low", "moderate", "high"]] = None


class ScheduledDay(_Input):
    day: int = Field(ge=1)
    meals: List[ScheduledMeal] = Field(min_length=1, max_length=8)
    workouts: List[Workout] = Field(default_factory=list)


class FullSchedule(_Input):
    """A schedule per day."""

    days: List[ScheduledDay] = Field(min_length=1)


Schedule = Union[ShorthandSchedule, FullSchedule]


class Pin(_Input):
    day: int = Field(ge=1)
    meal: int = Field(ge=1)
    recipe_id: str = Field(min_length=1)


class MealPrepAssignment(_Input):
    day: int = Field(ge=1)
    meal: int = Field(ge=1)
    servings: float = Field(default=1.0, gt=0)


class MealPrep(_Input):
    recipe_id: str = Field(min_length=1)
    total_servings: int = Field(ge=1)
    assignments: List[MealPrepAssignment] = Field(min_length=1)


# --- macrova_plan_meals: output -----------------------------------------------


class Where(BaseModel):
    day: Optional[int] = None
    meal: Optional[int] = None


class PlannedMeal(BaseModel):
    meal: int
    label: Optional[str] = None
    recipe_id: str
    name: Optional[str] = None
    servings: float = 1.0
    source: Literal["planner", "pin", "meal_prep"]


class DayTotals(BaseModel):
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float


class PlannedDay(BaseModel):
    day: int
    meals: List[PlannedMeal]
    totals: Optional[DayTotals] = None


class NutrientProgress(BaseModel):
    total: float
    target: float
    met: bool


class RecipeGap(BaseModel):
    """What a new recipe would need to fill the gap."""

    per_meal_calories: Optional[float] = None
    per_meal_protein_g: Optional[float] = None
    per_meal_fat_g_max: Optional[float] = None
    per_meal_carbs_g: Optional[float] = None
    max_cooking_minutes: Optional[int] = None
    excluded_ingredients: List[str] = Field(default_factory=list)
    nutrient_minimums: Dict[str, float] = Field(
        default_factory=dict, description='Per-recipe minimums keyed by plain name, e.g. "Fiber (g)".'
    )
    meal_types: List[str] = Field(default_factory=list)
    meals: List[Where] = Field(default_factory=list, description="The meals the recipe would fill.")


class Failure(BaseModel):
    explanation: str
    fix: Optional[str] = None
    where: Where
    a_new_recipe_could_help: bool
    recipe_gap: Optional[RecipeGap] = None
    code: str = Field(description="Planner failure code, for debugging. Not the headline.")


class PlanResult(BaseModel):
    status: Literal["success", "partial", "failed"]
    summary: str = Field(description="One plain-language sentence for the assistant to relay.")
    requested_targets: Targets
    days: List[PlannedDay]
    weekly_micronutrients: Dict[str, NutrientProgress] = Field(
        default_factory=dict, description='Keyed by plain name, e.g. "Vitamin C (mg)".'
    )
    warnings: List[str] = Field(default_factory=list)
    failure: Optional[Failure] = Field(default=None, description="Present only when status isn't success.")


# --- macrova_analyze_recipe ---------------------------------------------------


class PerServing(BaseModel):
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    micronutrients: Dict[str, float] = Field(
        default_factory=dict, description='Keyed by plain name, e.g. "Iron (mg)".'
    )


class MatchedIngredient(BaseModel):
    input: str
    matched_to: str
    source: Literal["usda", "local"]
    grams: float


class UnmatchedIngredient(BaseModel):
    input: str
    reason: str


class RecipeAnalysis(BaseModel):
    per_serving: PerServing
    servings: int
    matched: List[MatchedIngredient]
    unmatched: List[UnmatchedIngredient]
    skipped: List[str] = Field(
        default_factory=list, description='"To taste" ingredients; they count as zero.'
    )
    ready_for_planning: bool = Field(description="False whenever any ingredient is unmatched.")


# --- macrova_get_sample_recipes / macrova_list_tags ---------------------------


class SampleRecipe(Recipe):
    per_serving_calories: Optional[float] = Field(description="Null when an ingredient can't be converted to grams.")
    per_serving_protein_g: Optional[float] = None
    ready_for_planning: bool = Field(description="False when the planner would drop the recipe (see unmatched).")
    unmatched: List[str] = Field(default_factory=list, description="Ingredients the planner can't convert to grams.")


class SampleRecipes(BaseModel):
    recipes: List[SampleRecipe]


class Tag(BaseModel):
    slug: str
    type: Literal["context", "time", "nutrition", "constraint"]
    description: str
    can_require: bool = Field(
        description="True if the tag works in required_tags; every tag works in preferred_tags."
    )


class TagList(BaseModel):
    tags: List[Tag]
