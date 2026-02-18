"""Phase 0: Spec-compliant inputs and state structures for the meal plan algorithm.

Reference: MEALPLAN_SPECIFICATION_v1.md Section 2 (Inputs) and Section 3 (State Representation).
No search, constraint, or scoring logic — data structures and validation only.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from src.data_layer.models import NutritionProfile, MicronutrientProfile, Ingredient


# --- Section 2.1.1 Schedule Structure ---

MAX_SLOTS_PER_DAY = 8
MIN_SLOTS_PER_DAY = 1
PLANNING_DAYS_MIN = 1
PLANNING_DAYS_MAX = 7


@dataclass(frozen=True)
class MealSlot:
    """A single meal slot for one day. Spec Section 2.1.1."""

    time: str  # HH:MM
    busyness_level: int  # 1-4
    meal_type: str  # e.g. "breakfast", "lunch", "snack", "dinner"


def validate_schedule_structure(
    schedule: List[List[MealSlot]],
    D: int,
) -> None:
    """Validate schedule has exactly D days, each with 1-8 slots. Spec Section 2.1.1.

    Raises:
        ValueError: If len(schedule) != D or any day has 0 or >8 slots.
    """
    if len(schedule) != D:
        raise ValueError(
            f"Schedule must have exactly D={D} days; got {len(schedule)}"
        )
    for day_index, day_slots in enumerate(schedule):
        n = len(day_slots)
        if n < MIN_SLOTS_PER_DAY:
            raise ValueError(
                f"Day {day_index + 1} has {n} slots; minimum is {MIN_SLOTS_PER_DAY}"
            )
        if n > MAX_SLOTS_PER_DAY:
            raise ValueError(
                f"Day {day_index + 1} has {n} slots; maximum is {MAX_SLOTS_PER_DAY}"
            )


def total_decision_points(schedule: List[List[MealSlot]], D: int) -> int:
    """Total number of decision points (slots) across D days. Spec Section 2.4."""
    validate_schedule_structure(schedule, D)
    return sum(len(schedule[d]) for d in range(D))


def validate_planning_horizon(D: int) -> None:
    """Validate D is in [1, 7]. Spec Section 2.4."""
    if not isinstance(D, int) or D < PLANNING_DAYS_MIN or D > PLANNING_DAYS_MAX:
        raise ValueError(
            f"Planning horizon D must be an integer in [{PLANNING_DAYS_MIN}, {PLANNING_DAYS_MAX}]; got {D}"
        )


# --- Section 2.1 User Profile ---


@dataclass
class PlanningUserProfile:
    """User profile for the meal plan algorithm. Spec Section 2.1.

    All fields as defined in the specification. Schedule is a per-day list of
    slot lists (schedule[day_index] = slots for day day_index+1).
    """

    daily_calories: int
    daily_protein_g: float
    daily_fat_g: Tuple[float, float]  # (min, max) grams
    daily_carbs_g: float
    max_daily_calories: Optional[int] = None
    schedule: List[List[MealSlot]] = field(default_factory=list)
    excluded_ingredients: List[str] = field(default_factory=list)
    liked_foods: List[str] = field(default_factory=list)
    demographic: str = "adult_male"
    upper_limits_overrides: Optional[Dict[str, float]] = None
    pinned_assignments: Dict[Tuple[int, int], str] = field(default_factory=dict)  # (day, slot_index) -> recipe_id
    micronutrient_targets: Dict[str, float] = field(default_factory=dict)
    activity_schedule: Dict[str, str] = field(default_factory=dict)
    enable_primary_carb_downscaling: bool = False
    max_scaling_steps: int = 4
    scaling_step_fraction: float = 0.10


# --- Section 2.2 Recipe Pool ---


@dataclass
class PlanningRecipe:
    """Recipe as consumed by the planner. Spec Section 2.2.

    Nutrition is pre-computed before the planner runs. primary_carb_contribution
    is optional and used only when Primary Carb Downscaling is enabled (later phase).
    """

    id: str
    name: str
    ingredients: List[Ingredient]
    cooking_time_minutes: int
    nutrition: NutritionProfile
    primary_carb_contribution: Optional[NutritionProfile] = None


# --- Section 3.1 Assignment Sequence ---

# Assignment is (day, slot_index, recipe_id). Day and slot_index are 1-based in spec;
# we use 0-based indices internally: (day_index, slot_index, recipe_id).
Assignment = Tuple[int, int, str]


# --- Section 3.2 Daily Tracker ---


@dataclass
class DailyTracker:
    """Running state for one day during search. Spec Section 3.2.

    micronutrients_consumed keys are nutrient names (e.g. vitamin_a_ug) and must
    cover all nutrients needed for UL enforcement, not only tracked micronutrients.
    """

    calories_consumed: float = 0.0
    protein_consumed: float = 0.0
    fat_consumed: float = 0.0
    carbs_consumed: float = 0.0
    micronutrients_consumed: Dict[str, float] = field(default_factory=dict)
    used_recipe_ids: Set[str] = field(default_factory=set)
    non_workout_recipe_ids: Set[str] = field(default_factory=set)
    slots_assigned: int = 0
    slots_total: int = 0


# --- Section 3.3 Weekly Tracker ---


@dataclass
class WeeklyTracker:
    """Running state across planned days. Spec Section 3.3."""

    weekly_totals: NutritionProfile = field(default_factory=lambda: NutritionProfile(0.0, 0.0, 0.0, 0.0))
    days_completed: int = 0
    days_remaining: int = 0
    carryover_needs: Dict[str, float] = field(default_factory=dict)


def micronutrient_profile_to_dict(profile: Optional[MicronutrientProfile]) -> Dict[str, float]:
    """Convert MicronutrientProfile to Dict[str, float] for micronutrients_consumed."""
    if profile is None:
        return {}
    return {
        f.name: getattr(profile, f.name)
        for f in MicronutrientProfile.__dataclass_fields__.values()
    }
