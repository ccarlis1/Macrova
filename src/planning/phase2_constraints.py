"""Phase 2: Hard constraints as pure predicates. Spec Section 4.

This module is the single authoritative place that answers:
"Does this assignment violate any hard constraint?"

No search, feasibility logic, scoring, or state mutation.
Reference: MEALPLAN_SPECIFICATION_v1.md Section 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple, Union

from src.data_layer.models import UpperLimits

from src.planning.phase0_models import (
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    micronutrient_profile_to_dict,
)
from src.planning.slot_attributes import cooking_time_max, is_workout_slot


# --- State view for predicates (read-only) ---


@dataclass(frozen=True)
class ConstraintStateView:
    """Read-only view of state for hard constraint evaluation. Spec Section 3.2.

    daily_trackers[day_index] = tracker for that day (0-based).
    """

    daily_trackers: Dict[int, DailyTracker]


def get_daily_tracker(state: ConstraintStateView, day_index: int) -> Optional[DailyTracker]:
    """Return the daily tracker for day_index, or None."""
    return state.daily_trackers.get(day_index)


# --- Recipe-like protocol (recipe or scaled variant; same .id for HC-2/HC-8) ---


class RecipeLike(Protocol):
    """Recipe or scaled variant. Variants use same id as base recipe. Spec Section 6.7.6."""

    id: str
    ingredients: List[Any]  # List[Ingredient]
    cooking_time_minutes: int
    nutrition: Any  # NutritionProfile


def _normalize_ingredient_name(name: str) -> str:
    """Normalize for HC-1 matching. Spec Section 4: matching on normalized ingredient names."""
    return name.lower().strip()


def _recipe_contains_excluded_ingredient(recipe: RecipeLike, excluded: List[str]) -> bool:
    """HC-1: True if recipe contains any ingredient matching excluded list (normalized)."""
    if not excluded:
        return False
    excluded_norm = {_normalize_ingredient_name(x) for x in excluded}
    for ing in recipe.ingredients:
        ing_name = getattr(ing, "name", str(ing))
        if _normalize_ingredient_name(ing_name) in excluded_norm:
            return True
    return False


# --- HC-1: Excluded ingredients ---


def check_hc1_excluded_ingredients(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    state: ConstraintStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
) -> bool:
    """HC-1: Recipe must contain no ingredient matching user_profile.excluded_ingredients. Spec Section 4.

    Matching is normalized (case-insensitive, trimmed).
    Returns True if allowed, False if violation.
    """
    return not _recipe_contains_excluded_ingredient(
        recipe_or_variant, user_profile.excluded_ingredients
    )


# --- HC-2: No same-day recipe reuse ---


def check_hc2_no_same_day_reuse(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    state: ConstraintStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
) -> bool:
    """HC-2: Recipe ID may appear at most once per day. Spec Section 4.

    Uses daily_tracker.used_recipe_ids. Variants use same recipe ID.
    Returns True if allowed, False if violation.
    """
    tracker = get_daily_tracker(state, day_index)
    if tracker is None:
        return True
    return recipe_or_variant.id not in tracker.used_recipe_ids


# --- HC-3: Cooking time bound ---


def check_hc3_cooking_time_bound(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    state: ConstraintStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
) -> bool:
    """HC-3: recipe.cooking_time_minutes <= slot.cooking_time_max. Spec Section 4.

    busyness_level == 4 has no upper bound (any cooking time permitted).
    Returns True if allowed, False if violation.
    """
    max_minutes = cooking_time_max(slot.busyness_level)
    if max_minutes is None:
        return True  # busyness 4
    return recipe_or_variant.cooking_time_minutes <= max_minutes


# --- HC-4: Daily UL enforcement ---


def _ul_violation(
    daily_tracker: DailyTracker,
    recipe_micro: Dict[str, float],
    resolved_ul: UpperLimits,
) -> bool:
    """True if adding recipe_micro to daily_tracker would strictly exceed any non-null UL."""
    for fname, ul_value in resolved_ul.__dataclass_fields__.items():
        ul = getattr(resolved_ul, fname)
        if ul is None:
            continue
        current = daily_tracker.micronutrients_consumed.get(fname, 0.0)
        recipe_val = recipe_micro.get(fname, 0.0)
        if current + recipe_val > ul:
            return True
    return False


def check_hc4_daily_ul(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    state: ConstraintStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
) -> bool:
    """HC-4: For each micronutrient with non-null resolved UL, T_d.micronutrients_consumed[n] <= resolved_UL[n]. Spec Section 4.

    Only strict excess (>) is a violation; equality at UL is allowed.
    When no tracker exists for the day, current consumption is treated as zero.
    Returns True if allowed, False if violation.
    """
    if resolved_ul is None:
        return True
    tracker = get_daily_tracker(state, day_index)
    if tracker is None:
        tracker = DailyTracker(micronutrients_consumed={})
    recipe_micro = micronutrient_profile_to_dict(
        getattr(recipe_or_variant.nutrition, "micronutrients", None)
    )
    return not _ul_violation(tracker, recipe_micro, resolved_ul)


# --- HC-5: Max daily calories ---


def check_hc5_max_daily_calories(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    state: ConstraintStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
) -> bool:
    """HC-5: If user_profile.max_daily_calories is set, T_d.calories_consumed + recipe <= max_daily_calories. Spec Section 4.

    Equality allowed. When no tracker exists for the day, current consumption is treated as zero.
    Returns True if allowed, False if violation.
    """
    if user_profile.max_daily_calories is None:
        return True
    tracker = get_daily_tracker(state, day_index)
    current_calories = tracker.calories_consumed if tracker is not None else 0.0
    calories = getattr(recipe_or_variant.nutrition, "calories", 0.0)
    return (current_calories + calories) <= user_profile.max_daily_calories


# --- HC-6: Pinned assignments ---


def check_hc6_pinned_assignment(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    state: ConstraintStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
    slot_index: int,
) -> bool:
    """HC-6: If slot is pinned, recipe_id must match pinned recipe. Spec Section 4.

    Enforced structurally via state and pre-validation; this is the minimal runtime check.
    Returns True if allowed, False if violation.
    """
    day_1based = day_index + 1
    key = (day_1based, slot_index)
    pinned_recipe_id = user_profile.pinned_assignments.get(key)
    if pinned_recipe_id is None:
        return True
    return recipe_or_variant.id == pinned_recipe_id


# --- HC-8: Cross-day non-workout reuse restriction ---


def check_hc8_cross_day_non_workout_reuse(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    state: ConstraintStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
    is_workout_slot: bool,
) -> bool:
    """HC-8: For day d > 1, if slot is non-workout, recipe_id must not be in T_{d-1}.non_workout_recipe_ids. Spec Section 4.

    Workout slots exempt. Day 1 has no restriction.
    Returns True if allowed, False if violation.
    """
    if day_index <= 0:
        return True
    if is_workout_slot:
        return True
    prev_tracker = get_daily_tracker(state, day_index - 1)
    if prev_tracker is None:
        return True
    return recipe_or_variant.id not in prev_tracker.non_workout_recipe_ids


# --- Combined check ---

HC_IDENTIFIERS = ("HC-1", "HC-2", "HC-3", "HC-4", "HC-5", "HC-6", "HC-8")


def check_all(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    slot_index: int,
    day_index: int,
    state: ConstraintStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
    is_workout_slot: bool,
) -> Union[bool, List[str]]:
    """Evaluate all hard constraints for this assignment. Spec Section 4.

    Returns True if all pass, or a list of violated HC identifiers (e.g. ["HC-1", "HC-3"]).
    No scoring. No feasibility reasoning.
    """
    violated: List[str] = []
    if not check_hc1_excluded_ingredients(
        recipe_or_variant, slot, day_index, state, user_profile, resolved_ul
    ):
        violated.append("HC-1")
    if not check_hc2_no_same_day_reuse(
        recipe_or_variant, slot, day_index, state, user_profile, resolved_ul
    ):
        violated.append("HC-2")
    if not check_hc3_cooking_time_bound(
        recipe_or_variant, slot, day_index, state, user_profile, resolved_ul
    ):
        violated.append("HC-3")
    if not check_hc4_daily_ul(
        recipe_or_variant, slot, day_index, state, user_profile, resolved_ul
    ):
        violated.append("HC-4")
    if not check_hc5_max_daily_calories(
        recipe_or_variant, slot, day_index, state, user_profile, resolved_ul
    ):
        violated.append("HC-5")
    if not check_hc6_pinned_assignment(
        recipe_or_variant, slot, day_index, state, user_profile, resolved_ul, slot_index
    ):
        violated.append("HC-6")
    if not check_hc8_cross_day_non_workout_reuse(
        recipe_or_variant, slot, day_index, state, user_profile, resolved_ul, is_workout_slot
    ):
        violated.append("HC-8")
    if not violated:
        return True
    return violated
