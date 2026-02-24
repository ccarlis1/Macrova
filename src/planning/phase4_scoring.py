"""Phase 4: Cost function (scoring module). Spec Section 8.

Computes a composite score in [0, 100] from five weighted components.
No constraints, no feasibility checks, no state mutation. Pure and deterministic.
Reference: MEALPLAN_SPECIFICATION_v1.md Section 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from src.planning.phase0_models import (
    DailyTracker,
    MealSlot,
    PlanningUserProfile,
    WeeklyTracker,
    micronutrient_profile_to_dict,
)
from src.planning.phase1_state import (
    PerMealTarget,
    adjusted_daily_target,
    per_meal_target,
)
from src.planning.slot_attributes import (
    activity_context,
    cooking_time_max,
    satiety_requirement,
    time_until_next_meal,
)

# Component weights per spec Section 8.2 (total 110, normalized to 1.0)
W_NUTRITION = 40 / 110
W_MICRONUTRIENT = 30 / 110
W_SATIETY = 15 / 110
W_BALANCE = 15 / 110
W_SCHEDULE = 10 / 110

# Nutrition deviation tolerance (Section 8.3)
NUTRITION_DEVIATION_TOLERANCE = 0.10

# Schedule: busyness 4 reference cooking time (minutes) for scoring
BUSYNESS_4_REFERENCE_MINUTES = 30


# --- State view (read-only) ---


@dataclass(frozen=True)
class ScoringStateView:
    """Read-only state for scoring. Spec Section 3."""

    daily_trackers: Dict[int, DailyTracker]
    weekly_tracker: WeeklyTracker
    schedule: List[List[MealSlot]]


def get_daily_tracker(state: ScoringStateView, day_index: int) -> Optional[DailyTracker]:
    return state.daily_trackers.get(day_index)


# --- Recipe-like protocol ---


class RecipeLike(Protocol):
    id: str
    ingredients: List[Any]
    cooking_time_minutes: int
    nutrition: Any


def _clamp_score(x: float) -> float:
    """Clamp to [0, 100]."""
    return max(0.0, min(100.0, x))


# --- 8.3 Nutrition Match ---


def _macro_subscore(actual: float, target: float) -> float:
    """Calories/protein/carbs: score = max(0, 100 * (1 - deviation/0.10)). Spec 8.3."""
    if target <= 0:
        return 100.0
    deviation = abs(actual - target) / target
    return _clamp_score(100.0 * (1.0 - deviation / NUTRITION_DEVIATION_TOLERANCE))


def _fat_subscore(
    recipe_fat: float,
    meal_fat_min: float,
    meal_fat_max: float,
) -> float:
    """Fat: score highest when recipe fat is toward midpoint of per-meal range. Spec 8.3."""
    if meal_fat_max <= meal_fat_min:
        return 100.0
    midpoint = (meal_fat_min + meal_fat_max) / 2.0
    half_range = (meal_fat_max - meal_fat_min) / 2.0
    if half_range <= 0:
        return 100.0
    deviation = abs(recipe_fat - midpoint) / half_range
    return _clamp_score(100.0 * (1.0 - min(deviation, 1.0)))


def nutrition_match(
    recipe: RecipeLike,
    day_index: int,
    slot_index: int,
    state: ScoringStateView,
    profile: PlanningUserProfile,
    per_meal: PerMealTarget,
    activity_context_set: frozenset,
) -> float:
    """8.3 Nutrition Match: calories, protein, fat, carbs; activity-adjusted. Output [0, 100]."""
    cal = getattr(recipe.nutrition, "calories", 0.0)
    pro = getattr(recipe.nutrition, "protein_g", 0.0)
    fat = getattr(recipe.nutrition, "fat_g", 0.0)
    carb = getattr(recipe.nutrition, "carbs_g", 0.0)

    cal_score = _macro_subscore(cal, per_meal.calories)
    pro_score = _macro_subscore(pro, per_meal.protein_g)
    fat_score = _fat_subscore(fat, per_meal.fat_min, per_meal.fat_max)
    carb_score = _macro_subscore(carb, per_meal.carbs_g)

    return (cal_score + pro_score + fat_score + carb_score) / 4.0


# --- 8.4 Micronutrient Match ---


def _weekly_totals_micro(weekly_totals: Any) -> Dict[str, float]:
    return micronutrient_profile_to_dict(getattr(weekly_totals, "micronutrients", None))


def micronutrient_match(
    recipe: RecipeLike,
    day_index: int,
    state: ScoringStateView,
    profile: PlanningUserProfile,
) -> float:
    """8.4 Micronutrient Match: nutrients_still_needed, carryover; priority to largest gaps. [0, 100]."""
    tracked = profile.micronutrient_targets
    if not tracked:
        return 50.0

    w = state.weekly_tracker
    days_left = w.days_remaining
    if days_left <= 0:
        days_left = 1
    cumulative = _weekly_totals_micro(w.weekly_totals)
    carryover = w.carryover_needs
    tracker = get_daily_tracker(state, day_index)
    consumed = tracker.micronutrients_consumed if tracker else {}
    recipe_micro = micronutrient_profile_to_dict(
        getattr(recipe.nutrition, "micronutrients", None)
    )

    nutrients_still_needed: Dict[str, float] = {}
    nutrients_already_covered: set = set()
    for n, base_target in tracked.items():
        if base_target <= 0:
            continue
        adj = adjusted_daily_target(
            base_target,
            carryover.get(n, 0.0),
            days_left,
        )
        cur = consumed.get(n, 0.0)
        if cur < adj:
            nutrients_still_needed[n] = adj - cur
        else:
            nutrients_already_covered.add(n)

    total_contribution = 0.0
    total_weight = 0.0
    for n, gap in nutrients_still_needed.items():
        if gap <= 0:
            continue
        amount = recipe_micro.get(n, 0.0)
        if amount <= 0:
            continue
        fill_ratio = min(1.0, amount / gap)
        weight = gap + carryover.get(n, 0.0)
        total_contribution += weight * fill_ratio
        total_weight += weight

    if total_weight <= 0:
        return 50.0
    raw = 100.0 * (total_contribution / total_weight)
    return _clamp_score(raw)


# --- 8.5 Satiety Match ---


def satiety_match(recipe: RecipeLike, satiety: str) -> float:
    """8.5 Satiety Match: high = fiber, protein, calories; moderate = balanced. [0, 100]."""
    cal = getattr(recipe.nutrition, "calories", 0.0)
    pro = getattr(recipe.nutrition, "protein_g", 0.0)
    micro = getattr(recipe.nutrition, "micronutrients", None)
    fiber = getattr(micro, "fiber_g", 0.0) if micro else 0.0

    if satiety == "high":
        s_fiber = min(100.0, fiber * 6.0)
        s_pro = min(100.0, pro * 2.5)
        s_cal = min(100.0, cal / 6.0)
        return _clamp_score((s_fiber + s_pro + s_cal) / 3.0)
    return _clamp_score(70.0 - abs(pro - 25.0) * 0.5)


# --- 8.6 Balance ---


def balance(
    recipe: RecipeLike,
    day_index: int,
    state: ScoringStateView,
    profile: PlanningUserProfile,
) -> float:
    """8.6 Balance: nutrient diversity, fat diversity, macro trajectory. [0, 100]."""
    tracker = get_daily_tracker(state, day_index)
    if tracker is None:
        return 50.0
    recipe_micro = micronutrient_profile_to_dict(
        getattr(recipe.nutrition, "micronutrients", None)
    )
    consumed = tracker.micronutrients_consumed
    slots_left = max(1, tracker.slots_total - tracker.slots_assigned)
    daily_cal = profile.daily_calories
    daily_pro = profile.daily_protein_g
    daily_fat_mid = (profile.daily_fat_g[0] + profile.daily_fat_g[1]) / 2.0
    daily_carb = profile.daily_carbs_g

    rem_cal = daily_cal - tracker.calories_consumed
    rem_pro = daily_pro - tracker.protein_consumed
    rem_fat = daily_fat_mid - tracker.fat_consumed
    rem_carb = daily_carb - tracker.carbs_consumed
    need_cal = rem_cal / slots_left
    need_pro = rem_pro / slots_left
    need_fat = rem_fat / slots_left
    need_carb = rem_carb / slots_left
    cal = getattr(recipe.nutrition, "calories", 0.0)
    pro = getattr(recipe.nutrition, "protein_g", 0.0)
    fat = getattr(recipe.nutrition, "fat_g", 0.0)
    carb = getattr(recipe.nutrition, "carbs_g", 0.0)
    t_cal = _macro_subscore(cal, need_cal) if need_cal > 0 else 50.0
    t_pro = _macro_subscore(pro, need_pro) if need_pro != 0 else 50.0
    t_fat = _macro_subscore(fat, need_fat) if need_fat != 0 else 50.0
    t_carb = _macro_subscore(carb, need_carb) if need_carb > 0 else 50.0
    trajectory = (t_cal + t_pro + t_fat + t_carb) / 4.0

    novel = 0
    for n, v in recipe_micro.items():
        if v > 0 and consumed.get(n, 0.0) < 1.0:
            novel += 1
    diversity = min(100.0, novel * 10.0) if recipe_micro else 50.0

    return _clamp_score((trajectory + diversity) / 2.0)


# --- 8.7 Schedule Match ---


def schedule_match(recipe: RecipeLike, slot: MealSlot) -> float:
    """8.7 Schedule Match: within bound full 100, shorter better; busyness 4 = proximity to 30 min. [0, 100]."""
    ct = recipe.cooking_time_minutes
    max_ct = cooking_time_max(slot.busyness_level)
    if max_ct is not None:
        if ct > max_ct:
            return 0.0
        return _clamp_score(100.0 * (1.0 - ct / max(1, max_ct)))
    dist = abs(ct - BUSYNESS_4_REFERENCE_MINUTES)
    return _clamp_score(max(0.0, 100.0 - dist * 2.0))


# --- Composite ---


def composite_score(
    recipe: RecipeLike,
    day_index: int,
    slot_index: int,
    state: ScoringStateView,
    profile: PlanningUserProfile,
) -> float:
    """Composite score in [0, 100]. Spec 8.1. Deterministic; no mutation."""
    if day_index < 0 or day_index >= len(state.schedule):
        return 50.0
    day_slots = state.schedule[day_index]
    if slot_index < 0 or slot_index >= len(day_slots):
        return 50.0
    slot = day_slots[slot_index]
    next_first = state.schedule[day_index + 1][0] if day_index + 1 < len(state.schedule) else None
    activity_context_set = activity_context(
        slot, slot_index, day_slots, next_first, profile.activity_schedule or {}
    )
    hours_until = time_until_next_meal(slot, slot_index, day_slots, next_first)
    is_last = slot_index + 1 >= len(day_slots)
    satiety = satiety_requirement(hours_until, is_last)
    tracker = get_daily_tracker(state, day_index)
    per_meal = per_meal_target(
        day_index, slot_index,
        tracker or DailyTracker(slots_total=len(day_slots)),
        profile,
        activity_context_set,
        satiety,
    )

    n_match = nutrition_match(recipe, day_index, slot_index, state, profile, per_meal, activity_context_set)
    micro_match = micronutrient_match(recipe, day_index, state, profile)
    sat_match = satiety_match(recipe, satiety)
    bal = balance(recipe, day_index, state, profile)
    sched = schedule_match(recipe, slot)

    composite = (
        W_NUTRITION * n_match
        + W_MICRONUTRIENT * micro_match
        + W_SATIETY * sat_match
        + W_BALANCE * bal
        + W_SCHEDULE * sched
    )
    return _clamp_score(composite)
