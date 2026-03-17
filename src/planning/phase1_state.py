"""Phase 1: Initial state S₀, pinned pre-validation, adjusted daily targets, per-meal targets.

Reference: MEALPLAN_SPECIFICATION_v1.md Section 3.4, 3.5, 3.6.
No search, backtracking, candidate selection, scoring, or full constraint engine.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.data_layer.models import NutritionProfile, MicronutrientProfile

from src.planning.phase0_models import (
    MealSlot,
    PlanningUserProfile,
    PlanningRecipe,
    DailyTracker,
    WeeklyTracker,
    Assignment,
    get_effective_nutrition,
    validate_schedule_structure,
    validate_planning_horizon,
    micronutrient_profile_to_dict,
)
from src.planning.slot_attributes import (
    activity_context,
    is_workout_slot,
    cooking_time_max,
    time_until_next_meal,
    satiety_requirement,
)


# --- Pinned pre-validation result (FM-3) ---


@dataclass(frozen=True)
class PinnedValidationResult:
    """Result of pinned assignment pre-validation. Spec Section 3.5.

    If success is True, failed_hc is None. If success is False, failed_hc
    indicates which hard constraint failed (e.g. 'HC-1', 'HC-2').
    Optional conflict location for FM-3 reporting (Section 11).
    """

    success: bool
    failed_hc: Optional[str] = None  # e.g. 'HC-1', 'HC-2', 'HC-3', 'HC-5', 'HC-8'
    failed_pin_day_1based: Optional[int] = None
    failed_pin_slot_index: Optional[int] = None
    failed_pin_recipe_id: Optional[str] = None


def _normalize_ingredient_name(name: str) -> str:
    """Normalize for HC-1 matching. Spec: matching on normalized ingredient names."""
    return name.lower().strip()


def _recipe_contains_excluded_ingredient(recipe: PlanningRecipe, excluded: List[str]) -> bool:
    """HC-1: True if recipe contains any ingredient in excluded list (normalized match)."""
    if not excluded:
        return False
    excluded_norm = {_normalize_ingredient_name(x) for x in excluded}
    for ing in recipe.ingredients:
        if _normalize_ingredient_name(ing.name) in excluded_norm:
            return True
    return False


def validate_pinned_assignments(
    profile: PlanningUserProfile,
    recipe_by_id: Dict[str, PlanningRecipe],
    D: int,
) -> PinnedValidationResult:
    """Pre-validate all pinned assignments against HC-1, HC-2, HC-3, HC-5, HC-8. Spec Section 3.5.

    Does not build state. If any pinned recipe violates a constraint, returns
    failure with the HC code (FM-3). Caller must not build state or enter search.
    """
    schedule = profile.schedule
    pinned = profile.pinned_assignments
    if not pinned:
        return PinnedValidationResult(success=True)

    validate_planning_horizon(D)
    validate_schedule_structure(schedule, D)

    # Build decision order and collect (day_1based, slot_index) -> recipe_id for pins
    # Keys in pinned are (day_1based, slot_index_0based) per Phase 0.
    for (day_1based, slot_index), recipe_id in pinned.items():
        if day_1based < 1 or day_1based > D:
            return PinnedValidationResult(success=False, failed_hc="HC-6")
        day_index = day_1based - 1
        if day_index >= len(schedule) or slot_index < 0 or slot_index >= len(schedule[day_index]):
            return PinnedValidationResult(success=False, failed_hc="HC-6", failed_pin_day_1based=day_1based, failed_pin_slot_index=slot_index, failed_pin_recipe_id=recipe_id)

        if recipe_id not in recipe_by_id:
            return PinnedValidationResult(success=False, failed_hc="HC-6", failed_pin_day_1based=day_1based, failed_pin_slot_index=slot_index, failed_pin_recipe_id=recipe_id)
        recipe = recipe_by_id[recipe_id]

        # HC-1: excluded ingredients
        if _recipe_contains_excluded_ingredient(recipe, profile.excluded_ingredients):
            return PinnedValidationResult(success=False, failed_hc="HC-1", failed_pin_day_1based=day_1based, failed_pin_slot_index=slot_index, failed_pin_recipe_id=recipe_id)

        # HC-3: cooking time
        day_slots = schedule[day_index]
        slot = day_slots[slot_index]
        max_time = cooking_time_max(slot.busyness_level)
        if max_time is not None and recipe.cooking_time_minutes > max_time:
            return PinnedValidationResult(success=False, failed_hc="HC-3", failed_pin_day_1based=day_1based, failed_pin_slot_index=slot_index, failed_pin_recipe_id=recipe_id)

        # HC-5: single recipe would exceed daily calorie ceiling (for that day)
        if profile.max_daily_calories is not None:
            if recipe.nutrition.calories > profile.max_daily_calories:
                return PinnedValidationResult(success=False, failed_hc="HC-5", failed_pin_day_1based=day_1based, failed_pin_slot_index=slot_index, failed_pin_recipe_id=recipe_id)

    # HC-2: two pinned on same day with same recipe_id
    by_day: Dict[int, List[Tuple[int, str]]] = {}
    for (day_1based, slot_index), recipe_id in pinned.items():
        by_day.setdefault(day_1based, []).append((slot_index, recipe_id))
    for day_1based, slots in by_day.items():
        recipe_ids = [rid for _, rid in slots]
        if len(recipe_ids) != len(set(recipe_ids)):
            slot_idx = slots[0][0]
            rid = slots[0][1]
            return PinnedValidationResult(success=False, failed_hc="HC-2", failed_pin_day_1based=day_1based, failed_pin_slot_index=slot_idx, failed_pin_recipe_id=rid)

    # HC-8: consecutive-day non-workout repetition among pinned
    # For each consecutive day pair, collect non-workout pinned recipe_ids per day
    activity_schedule = profile.activity_schedule or {}
    non_workout_pinned_by_day: Dict[int, set] = {}
    for day_1based in range(1, D + 1):
        day_index = day_1based - 1
        day_slots = schedule[day_index]
        next_first = schedule[day_index + 1][0] if day_index + 1 < len(schedule) else None
        ids_this_day = set()
        for (d, s), recipe_id in pinned.items():
            if d != day_1based:
                continue
            slot = day_slots[s]
            ctx = activity_context(slot, s, day_slots, next_first, activity_schedule)
            if not is_workout_slot(ctx):
                ids_this_day.add(recipe_id)
        non_workout_pinned_by_day[day_1based] = ids_this_day

    for d in range(1, D):
        for rid in non_workout_pinned_by_day.get(d, set()):
            if rid in non_workout_pinned_by_day.get(d + 1, set()):
                return PinnedValidationResult(success=False, failed_hc="HC-8", failed_pin_day_1based=d + 1, failed_pin_slot_index=0, failed_pin_recipe_id=rid)

    return PinnedValidationResult(success=True)


def _add_nutrition(a: NutritionProfile, b: NutritionProfile) -> NutritionProfile:
    """Sum two NutritionProfiles (macros and micronutrients if present)."""
    micro_a = micronutrient_profile_to_dict(a.micronutrients) if a.micronutrients else {}
    micro_b = micronutrient_profile_to_dict(b.micronutrients) if b.micronutrients else {}
    valid_fields = set(MicronutrientProfile.__dataclass_fields__.keys())
    all_keys = (set(micro_a) | set(micro_b)) & valid_fields
    micro_sum = {k: micro_a.get(k, 0.0) + micro_b.get(k, 0.0) for k in all_keys}
    micro_profile = None
    if all_keys:
        kwargs = {k: micro_sum.get(k, 0.0) for k in valid_fields}
        micro_profile = MicronutrientProfile(**kwargs)
    return NutritionProfile(
        calories=a.calories + b.calories,
        protein_g=a.protein_g + b.protein_g,
        fat_g=a.fat_g + b.fat_g,
        carbs_g=a.carbs_g + b.carbs_g,
        micronutrients=micro_profile,
    )


def _dict_sum(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    all_keys = set(a) | set(b)
    return {k: a.get(k, 0.0) + b.get(k, 0.0) for k in all_keys}


@dataclass
class InitialState:
    """Initial state S₀. Spec Section 3.5.

    assignments: pinned assignments in decision order (day_index, slot_index, recipe_id).
    daily_trackers: day_index -> DailyTracker (only for days with at least one assignment).
    weekly_tracker: single WeeklyTracker.
    """

    assignments: List[Assignment] = field(default_factory=list)
    daily_trackers: Dict[int, DailyTracker] = field(default_factory=dict)
    weekly_tracker: WeeklyTracker = field(default_factory=WeeklyTracker)


def build_initial_state(
    profile: PlanningUserProfile,
    recipe_by_id: Dict[str, PlanningRecipe],
    D: int,
) -> InitialState:
    """Build initial state S₀ from pinned assignments only. Spec Section 3.5.

    Caller must run validate_pinned_assignments first and only call this when success.
    """
    validate_planning_horizon(D)
    validate_schedule_structure(profile.schedule, D)

    schedule = profile.schedule
    pinned = profile.pinned_assignments
    activity_schedule = profile.activity_schedule or {}

    # Decision order: (day_index, slot_index) for d in 0..D-1, s in 0..len(schedule[d])-1
    assignments: List[Assignment] = []
    daily_trackers: Dict[int, DailyTracker] = {}

    for day_index in range(D):
        day_slots = schedule[day_index]
        slots_total = len(day_slots)
        next_day_first = schedule[day_index + 1][0] if day_index + 1 < D else None

        calories_d = 0.0
        protein_d = 0.0
        fat_d = 0.0
        carbs_d = 0.0
        micro_d: Dict[str, float] = {}
        used_ids: set = set()
        non_workout_ids: set = set()
        slots_assigned_d = 0

        for slot_index in range(slots_total):
            day_1based = day_index + 1
            key = (day_1based, slot_index)
            if key not in pinned:
                continue
            recipe_id = pinned[key]
            recipe = recipe_by_id[recipe_id]
            assignments.append(Assignment(day_index, slot_index, recipe_id, 0))
            nut = get_effective_nutrition(recipe, 0)
            calories_d += nut.calories
            protein_d += nut.protein_g
            fat_d += nut.fat_g
            carbs_d += nut.carbs_g
            micro_d = _dict_sum(micro_d, micronutrient_profile_to_dict(nut.micronutrients))
            used_ids.add(recipe_id)
            slot = day_slots[slot_index]
            ctx = activity_context(slot, slot_index, day_slots, next_day_first, activity_schedule)
            if not is_workout_slot(ctx):
                non_workout_ids.add(recipe_id)
            slots_assigned_d += 1

        if slots_assigned_d > 0:
            daily_trackers[day_index] = DailyTracker(
                calories_consumed=calories_d,
                protein_consumed=protein_d,
                fat_consumed=fat_d,
                carbs_consumed=carbs_d,
                micronutrients_consumed=micro_d,
                used_recipe_ids=used_ids,
                non_workout_recipe_ids=non_workout_ids,
                slots_assigned=slots_assigned_d,
                slots_total=slots_total,
            )

    # Weekly tracker: sum nutrition from all pinned; days_completed=0, days_remaining=D; carryover=0
    weekly_totals = NutritionProfile(0.0, 0.0, 0.0, 0.0)
    valid_micro_fields = list(MicronutrientProfile.__dataclass_fields__.keys())
    for day_index in range(D):
        if day_index in daily_trackers:
            t = daily_trackers[day_index]
            micro = None
            if t.micronutrients_consumed:
                kwargs = {k: t.micronutrients_consumed.get(k, 0.0) for k in valid_micro_fields}
                micro = MicronutrientProfile(**kwargs)
            day_nut = NutritionProfile(
                t.calories_consumed, t.protein_consumed, t.fat_consumed, t.carbs_consumed,
                micronutrients=micro,
            )
            weekly_totals = _add_nutrition(weekly_totals, day_nut)

    carryover = {
        n: 0.0 for n in profile.micronutrient_targets
    }
    weekly_tracker = WeeklyTracker(
        weekly_totals=weekly_totals,
        days_completed=0,
        days_remaining=D,
        carryover_needs=carryover,
    )

    return InitialState(
        assignments=assignments,
        daily_trackers=daily_trackers,
        weekly_tracker=weekly_tracker,
    )


# --- Section 3.4 Adjusted daily micronutrient targets ---


def adjusted_daily_target(
    base_daily_target: float,
    carryover_needs_n: float,
    days_remaining: int,
) -> float:
    """Adjusted daily target for one micronutrient. Spec Section 3.4.

    adjusted_daily_target(n) = base_daily_target(n) + (carryover_needs(n) / days_remaining)
    days_remaining includes the current day. Pure function; does not mutate state.
    """
    if days_remaining <= 0:
        return base_daily_target
    return base_daily_target + (carryover_needs_n / days_remaining)


# --- Section 3.6 Per-meal target distribution ---

# Normative factors from existing implementation (Appendix C resolution #4).
PRE_WORKOUT_PROTEIN_FACTOR = 0.8
PRE_WORKOUT_CARBS_FACTOR = 1.1
POST_WORKOUT_PROTEIN_FACTOR = 1.2
POST_WORKOUT_CARBS_FACTOR = 1.1
POST_WORKOUT_CALORIES_FACTOR = 1.1
HIGH_SATIETY_CALORIES_FACTOR = 1.1
HIGH_SATIETY_PROTEIN_FACTOR = 1.1
HIGH_SATIETY_FAT_FACTOR = 1.1


@dataclass
class PerMealTarget:
    """Per-meal target for one slot. Spec Section 3.6."""

    calories: float
    protein_g: float
    fat_min: float
    fat_max: float
    carbs_g: float


def per_meal_target(
    day_index: int,
    slot_index: int,
    daily_tracker: DailyTracker,
    profile: PlanningUserProfile,
    activity_context_set: frozenset,
    satiety: str,
) -> PerMealTarget:
    """Compute per-meal target for decision point (d, s). Spec Section 3.6.

    Does not modify state. Uses remaining budget and slots_left, then applies
    activity-context adjustments (pre_workout, post_workout, high satiety).
    """
    remaining_calories = profile.daily_calories - daily_tracker.calories_consumed
    remaining_protein = profile.daily_protein_g - daily_tracker.protein_consumed
    remaining_fat_max = profile.daily_fat_g[1] - daily_tracker.fat_consumed
    remaining_fat_min = profile.daily_fat_g[0] - daily_tracker.fat_consumed
    remaining_carbs = profile.daily_carbs_g - daily_tracker.carbs_consumed
    slots_left = daily_tracker.slots_total - daily_tracker.slots_assigned
    if slots_left <= 0:
        slots_left = 1

    base_cal = remaining_calories / slots_left
    base_protein = remaining_protein / slots_left
    base_fat_min = remaining_fat_min / slots_left
    base_fat_max = remaining_fat_max / slots_left
    base_carbs = remaining_carbs / slots_left

    cal, pro, fmin, fmax, carb = base_cal, base_protein, base_fat_min, base_fat_max, base_carbs

    if "pre_workout" in activity_context_set:
        pro *= PRE_WORKOUT_PROTEIN_FACTOR
        carb *= PRE_WORKOUT_CARBS_FACTOR
    if "post_workout" in activity_context_set:
        cal *= POST_WORKOUT_CALORIES_FACTOR
        pro *= POST_WORKOUT_PROTEIN_FACTOR
        carb *= POST_WORKOUT_CARBS_FACTOR
    if satiety == "high":
        cal *= HIGH_SATIETY_CALORIES_FACTOR
        pro *= HIGH_SATIETY_PROTEIN_FACTOR
        fmin *= HIGH_SATIETY_FAT_FACTOR
        fmax *= HIGH_SATIETY_FAT_FACTOR

    return PerMealTarget(
        calories=cal,
        protein_g=pro,
        fat_min=fmin,
        fat_max=fmax,
        carbs_g=carb,
    )
