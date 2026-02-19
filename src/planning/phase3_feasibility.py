"""Phase 3: Forward-looking feasibility constraints. Spec Section 5.

This module answers: "If we tentatively place this recipe, is it still feasible
to complete the plan?" No search, no scoring, no state mutation.
Reference: MEALPLAN_SPECIFICATION_v1.md Section 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple

from src.data_layer.models import NutritionProfile, MicronutrientProfile, UpperLimits

from src.planning.phase0_models import (
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    WeeklyTracker,
    micronutrient_profile_to_dict,
)

# Section 6.5: ±10% daily tolerance for calories, protein, carbs
DAILY_TOLERANCE_FRACTION = 0.10


# --- Recipe-like protocol (recipe or scaled variant) ---


class RecipeLike(Protocol):
    id: str
    ingredients: List[Any]
    cooking_time_minutes: int
    nutrition: Any  # NutritionProfile


# --- Precomputation: macro min/max per slot count (FC-1, FC-2) ---


@dataclass(frozen=True)
class MacroBoundsPrecomputation:
    """For each slot_count M: min and max sum of macro over M distinct recipes. Spec Section 5."""

    # [slot_count] -> min sum, max sum (slot_count 1..8)
    calories_min: Dict[int, float] = field(default_factory=dict)
    calories_max: Dict[int, float] = field(default_factory=dict)
    protein_min: Dict[int, float] = field(default_factory=dict)
    protein_max: Dict[int, float] = field(default_factory=dict)
    fat_min: Dict[int, float] = field(default_factory=dict)
    fat_max: Dict[int, float] = field(default_factory=dict)
    carbs_min: Dict[int, float] = field(default_factory=dict)
    carbs_max: Dict[int, float] = field(default_factory=dict)


def _sorted_values_by_recipe(recipes: List[PlanningRecipe], attr: str) -> List[float]:
    """One value per distinct recipe (by id); values sorted ascending."""
    by_id: Dict[str, float] = {}
    for r in recipes:
        if r.id in by_id:
            continue
        val = getattr(r.nutrition, attr, 0.0)
        by_id[r.id] = val
    return sorted(by_id.values())


def precompute_macro_bounds(
    recipes: List[PlanningRecipe],
    max_slots: int = 8,
) -> MacroBoundsPrecomputation:
    """Precompute min/max sum of each macro over M distinct recipes (M=1..max_slots)."""
    cal = _sorted_values_by_recipe(recipes, "calories")
    pro = _sorted_values_by_recipe(recipes, "protein_g")
    fat = _sorted_values_by_recipe(recipes, "fat_g")
    carb = _sorted_values_by_recipe(recipes, "carbs_g")

    def min_max_for(values: List[float]) -> Tuple[Dict[int, float], Dict[int, float]]:
        min_d: Dict[int, float] = {}
        max_d: Dict[int, float] = {}
        for m in range(1, max_slots + 1):
            if m > len(values):
                min_d[m] = sum(values) if values else 0.0
                max_d[m] = sum(values) if values else 0.0
            else:
                min_d[m] = sum(values[:m])
                max_d[m] = sum(values[-m:])
        return min_d, max_d

    cal_min, cal_max = min_max_for(cal)
    pro_min, pro_max = min_max_for(pro)
    fat_min, fat_max = min_max_for(fat)
    carb_min, carb_max = min_max_for(carb)

    return MacroBoundsPrecomputation(
        calories_min=cal_min,
        calories_max=cal_max,
        protein_min=pro_min,
        protein_max=pro_max,
        fat_min=fat_min,
        fat_max=fat_max,
        carbs_min=carb_min,
        carbs_max=carb_max,
    )


# --- Precomputation: max_daily_achievable for micronutrients (FC-4) ---


def precompute_max_daily_achievable(
    recipes: List[PlanningRecipe],
    nutrient_names: List[str],
    slot_counts: Set[int],
) -> Dict[str, Dict[int, float]]:
    """Precompute max_daily_achievable(nutrient, slot_count). Spec Section 5 FC-4.

    For each nutrient n and slot_count M: sum of the M largest values of n across distinct recipes.
    """
    result: Dict[str, Dict[int, float]] = {n: {} for n in nutrient_names}
    micro_fields = list(MicronutrientProfile.__dataclass_fields__.keys())
    for n in nutrient_names:
        if n not in micro_fields:
            continue
        by_id: Dict[str, float] = {}
        for r in recipes:
            if r.id in by_id:
                continue
            micro = getattr(r.nutrition, "micronutrients", None)
            val = getattr(micro, n, 0.0) if micro is not None else 0.0
            by_id[r.id] = val
        vals = sorted(by_id.values(), reverse=True)
        for m in slot_counts:
            if m <= 0:
                result[n][m] = 0.0
            else:
                result[n][m] = sum(vals[:m])
    return result


# --- Feasibility state view (read-only) ---


@dataclass(frozen=True)
class FeasibilityStateView:
    """Read-only view for feasibility evaluation. Spec Section 3."""

    daily_trackers: Dict[int, DailyTracker]
    weekly_tracker: WeeklyTracker
    schedule: List[List[MealSlot]]  # schedule[day_index] = list of slots


def get_daily_tracker(state: FeasibilityStateView, day_index: int) -> Optional[DailyTracker]:
    return state.daily_trackers.get(day_index)


def slots_remaining_after_assigning(
    state: FeasibilityStateView,
    day_index: int,
    slot_index: int,
) -> int:
    """Slots still unassigned on day after assigning (day_index, slot_index)."""
    tracker = get_daily_tracker(state, day_index)
    if tracker is None:
        if day_index >= len(state.schedule):
            return 0
        return max(0, len(state.schedule[day_index]) - 1 - slot_index)
    # After assigning current slot: slots_total - slots_assigned - 1
    return max(0, tracker.slots_total - tracker.slots_assigned - 1)


# --- FC-1: Daily calorie feasibility ---


def check_fc1_daily_calories(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    slot_index: int,
    state: FeasibilityStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
    macro_bounds: MacroBoundsPrecomputation,
) -> bool:
    """FC-1: After tentatively adding recipe, reject if over cap; else verify remaining slots can reach daily ±10%. Spec Section 5."""
    daily_cal = user_profile.daily_calories
    tracker = get_daily_tracker(state, day_index)
    current_cal = tracker.calories_consumed if tracker is not None else 0.0
    recipe_cal = getattr(recipe_or_variant.nutrition, "calories", 0.0)
    c_used = current_cal + recipe_cal
    c_remaining = daily_cal - c_used

    if user_profile.max_daily_calories is not None and c_used > user_profile.max_daily_calories:
        return False

    k = slots_remaining_after_assigning(state, day_index, slot_index)
    if k == 0:
        if abs(c_remaining) > DAILY_TOLERANCE_FRACTION * daily_cal:
            return False
        return True

    low = c_remaining - DAILY_TOLERANCE_FRACTION * daily_cal
    high = c_remaining + DAILY_TOLERANCE_FRACTION * daily_cal
    min_achievable = macro_bounds.calories_min.get(k, 0.0)
    max_achievable = macro_bounds.calories_max.get(k, 0.0)
    if min_achievable > high or max_achievable < low:
        return False
    return True


# --- FC-2: Macro feasibility ---


def check_fc2_daily_macros(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    slot_index: int,
    state: FeasibilityStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
    macro_bounds: MacroBoundsPrecomputation,
) -> bool:
    """FC-2: Protein/carbs ±10%; fat within [min,max] for remaining slots. Spec Section 5."""
    tracker = get_daily_tracker(state, day_index)
    k = slots_remaining_after_assigning(state, day_index, slot_index)

    def current(attr: str) -> float:
        if tracker is None:
            return 0.0
        return getattr(tracker, attr, 0.0)

    recipe_pro = getattr(recipe_or_variant.nutrition, "protein_g", 0.0)
    recipe_fat = getattr(recipe_or_variant.nutrition, "fat_g", 0.0)
    recipe_carbs = getattr(recipe_or_variant.nutrition, "carbs_g", 0.0)

    # Protein ±10%
    target_pro = user_profile.daily_protein_g
    used_pro = current("protein_consumed") + recipe_pro
    rem_pro = target_pro - used_pro
    if k > 0:
        low_pro = rem_pro - DAILY_TOLERANCE_FRACTION * target_pro
        high_pro = rem_pro + DAILY_TOLERANCE_FRACTION * target_pro
        min_p = macro_bounds.protein_min.get(k, 0.0)
        max_p = macro_bounds.protein_max.get(k, 0.0)
        if min_p > high_pro or max_p < low_pro:
            return False
    else:
        if abs(rem_pro) > DAILY_TOLERANCE_FRACTION * target_pro:
            return False

    # Carbs ±10%
    target_carbs = user_profile.daily_carbs_g
    used_carbs = current("carbs_consumed") + recipe_carbs
    rem_carbs = target_carbs - used_carbs
    if k > 0:
        low_c = rem_carbs - DAILY_TOLERANCE_FRACTION * target_carbs
        high_c = rem_carbs + DAILY_TOLERANCE_FRACTION * target_carbs
        min_c = macro_bounds.carbs_min.get(k, 0.0)
        max_c = macro_bounds.carbs_max.get(k, 0.0)
        if min_c > high_c or max_c < low_c:
            return False
    else:
        if abs(rem_carbs) > DAILY_TOLERANCE_FRACTION * target_carbs:
            return False

    # Fat within [min, max]
    fat_min, fat_max = user_profile.daily_fat_g
    used_fat = current("fat_consumed") + recipe_fat
    rem_fat_min = fat_min - used_fat
    rem_fat_max = fat_max - used_fat
    if k > 0:
        min_f = macro_bounds.fat_min.get(k, 0.0)
        max_f = macro_bounds.fat_max.get(k, 0.0)
        if min_f > rem_fat_max or max_f < rem_fat_min:
            return False
    else:
        if used_fat < fat_min or used_fat > fat_max:
            return False

    return True


# --- FC-3: Incremental UL feasibility ---


def check_fc3_incremental_ul(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    state: FeasibilityStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
) -> bool:
    """FC-3: T_d.micronutrients_consumed + recipe <= resolved_UL for each non-null UL. Spec Section 5."""
    if resolved_ul is None:
        return True
    tracker = get_daily_tracker(state, day_index)
    current_micro = tracker.micronutrients_consumed if tracker is not None else {}
    recipe_micro = micronutrient_profile_to_dict(
        getattr(recipe_or_variant.nutrition, "micronutrients", None)
    )
    for fname in resolved_ul.__dataclass_fields__:
        ul_val = getattr(resolved_ul, fname)
        if ul_val is None:
            continue
        cur = current_micro.get(fname, 0.0)
        rec = recipe_micro.get(fname, 0.0)
        if cur + rec > ul_val:
            return False
    return True


# --- FC-4: Cross-day RDI irrecoverability ---


def _weekly_totals_micro_dict(weekly_totals: NutritionProfile) -> Dict[str, float]:
    return micronutrient_profile_to_dict(getattr(weekly_totals, "micronutrients", None))


def check_fc4_cross_day_rdi(
    day_index: int,
    state: FeasibilityStateView,
    user_profile: PlanningUserProfile,
    D: int,
    max_daily_achievable: Dict[str, Dict[int, float]],
) -> bool:
    """FC-4: At start of day d (d>1), if deficit(n) > days_left * max_daily_achievable(n, M), reject. Spec Section 5."""
    if day_index <= 0:
        return True
    w = state.weekly_tracker
    days_left = w.days_remaining
    if days_left <= 0:
        return True
    cumulative = _weekly_totals_micro_dict(w.weekly_totals)
    tracked = user_profile.micronutrient_targets
    if not tracked:
        return True
    if day_index >= len(state.schedule):
        return True
    slot_count = len(state.schedule[day_index])
    mda = max_daily_achievable

    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        total_needed = daily_rdi * D
        consumed = cumulative.get(n, 0.0)
        deficit = total_needed - consumed
        if deficit <= 0:
            continue
        max_achievable = mda.get(n, {}).get(slot_count, 0.0)
        if deficit > days_left * max_achievable:
            return False
    return True


# --- FC-5: Candidate set and future-slot feasibility ---


def check_fc5_candidate_set(
    candidate_recipe_ids: Set[str],
    tentative_recipe_id: str,
    used_recipe_ids_today: Set[str],
    future_slot_eligible_recipe_ids: List[Set[str]],
) -> bool:
    """FC-5: Candidate set non-empty; each future slot has at least one eligible recipe. Spec Section 5."""
    if not candidate_recipe_ids:
        return False
    used_after = used_recipe_ids_today | {tentative_recipe_id}
    for eligible in future_slot_eligible_recipe_ids:
        remaining = eligible - used_after
        if not remaining:
            return False
    return True


# --- Combined FC-1/FC-2/FC-3 (per-candidate) ---


def check_fc1_fc2_fc3(
    recipe_or_variant: RecipeLike,
    slot: MealSlot,
    day_index: int,
    slot_index: int,
    state: FeasibilityStateView,
    user_profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
    macro_bounds: MacroBoundsPrecomputation,
) -> bool:
    """Run FC-1, FC-2, FC-3. Returns True only if all pass."""
    if not check_fc1_daily_calories(
        recipe_or_variant, slot, day_index, slot_index, state, user_profile, resolved_ul, macro_bounds
    ):
        return False
    if not check_fc2_daily_macros(
        recipe_or_variant, slot, day_index, slot_index, state, user_profile, resolved_ul, macro_bounds
    ):
        return False
    if not check_fc3_incremental_ul(
        recipe_or_variant, slot, day_index, state, user_profile, resolved_ul
    ):
        return False
    return True
