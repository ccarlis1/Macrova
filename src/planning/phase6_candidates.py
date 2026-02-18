"""Phase 6: Candidate generation at (d, s). Spec Section 6.3 steps 1–7.

Generates C(d, s) by filtering the recipe pool with hard constraints and
forward feasibility. Signals backtrack when C is empty or a future slot has
zero eligible candidates. No scoring, no search, no state mutation.
Step 8 (Primary Carb Downscaling) is not implemented.
Reference: MEALPLAN_SPECIFICATION_v1.md Section 6.3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from src.data_layer.models import UpperLimits

from src.planning.phase0_models import (
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    WeeklyTracker,
)
from src.planning.phase2_constraints import (
    ConstraintStateView,
    check_hc1_excluded_ingredients,
    check_hc2_no_same_day_reuse,
    check_hc3_cooking_time_bound,
    check_hc5_max_daily_calories,
    check_hc8_cross_day_non_workout_reuse,
)
from src.planning.phase3_feasibility import (
    FeasibilityStateView,
    MacroBoundsPrecomputation,
    check_fc1_daily_calories,
    check_fc2_daily_macros,
    check_fc3_incremental_ul,
)
from src.planning.slot_attributes import activity_context, is_workout_slot


@dataclass
class CandidateGenerationResult:
    """Result of candidate generation at (d, s). Spec Section 6.3."""

    candidates: Set[str]  # recipe IDs that survive filtering
    trigger_backtrack: bool
    calorie_excess_rejections: Set[str] = field(default_factory=set)  # metadata for Phase 9


def _get_slot(
    schedule: List[List[MealSlot]],
    day_index: int,
    slot_index: int,
) -> Optional[MealSlot]:
    if day_index < 0 or day_index >= len(schedule):
        return None
    day_slots = schedule[day_index]
    if slot_index < 0 or slot_index >= len(day_slots):
        return None
    return day_slots[slot_index]


def _rejected_solely_calorie_fc1(
    recipe: PlanningRecipe,
    day_index: int,
    slot_index: int,
    state: FeasibilityStateView,
    profile: PlanningUserProfile,
) -> bool:
    """True if FC-1 would reject this recipe solely due to calorie overflow (c_used > max_daily_calories)."""
    if profile.max_daily_calories is None:
        return False
    tracker = state.daily_trackers.get(day_index)
    current_cal = tracker.calories_consumed if tracker is not None else 0.0
    recipe_cal = getattr(recipe.nutrition, "calories", 0.0)
    return (current_cal + recipe_cal) > profile.max_daily_calories


def _filter_step_1_through_7(
    recipe_pool: List[PlanningRecipe],
    day_index: int,
    slot_index: int,
    slot: MealSlot,
    constraint_state: ConstraintStateView,
    feasibility_state: FeasibilityStateView,
    profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
    macro_bounds: MacroBoundsPrecomputation,
    is_workout: bool,
) -> Tuple[Set[str], Set[str]]:
    """Apply steps 1–7. Returns (candidate_ids, calorie_excess_rejections)."""
    calorie_excess: Set[str] = set()
    # Step 1–2: HC-1, HC-2
    surviving: List[PlanningRecipe] = []
    for r in recipe_pool:
        if not check_hc1_excluded_ingredients(r, slot, day_index, constraint_state, profile, resolved_ul):
            continue
        if not check_hc2_no_same_day_reuse(r, slot, day_index, constraint_state, profile, resolved_ul):
            continue
        surviving.append(r)

    # Step 3: HC-3
    surviving = [r for r in surviving if check_hc3_cooking_time_bound(r, slot, day_index, constraint_state, profile, resolved_ul)]

    # Step 4: HC-5 (record calorie excess)
    next_surviving: List[PlanningRecipe] = []
    for r in surviving:
        if check_hc5_max_daily_calories(r, slot, day_index, constraint_state, profile, resolved_ul):
            next_surviving.append(r)
        else:
            calorie_excess.add(r.id)
    surviving = next_surviving

    # Step 5: HC-8 (when d > 1 and non-workout)
    if day_index > 0 and not is_workout:
        surviving = [
            r for r in surviving
            if check_hc8_cross_day_non_workout_reuse(r, slot, day_index, constraint_state, profile, resolved_ul, is_workout)
        ]

    # Step 6–7: FC-1, FC-2, FC-3 (record FC-1 calorie overflow only)
    candidates: List[PlanningRecipe] = []
    for r in surviving:
        fc1_ok = check_fc1_daily_calories(
            r, slot, day_index, slot_index, feasibility_state, profile, resolved_ul, macro_bounds
        )
        if not fc1_ok:
            if _rejected_solely_calorie_fc1(r, day_index, slot_index, feasibility_state, profile):
                calorie_excess.add(r.id)
            continue
        if not check_fc2_daily_macros(
            r, slot, day_index, slot_index, feasibility_state, profile, resolved_ul, macro_bounds
        ):
            continue
        if not check_fc3_incremental_ul(r, slot, day_index, feasibility_state, profile, resolved_ul):
            continue
        candidates.append(r)

    return {r.id for r in candidates}, calorie_excess


def _filter_hard_constraints_only(
    recipe_pool: List[PlanningRecipe],
    day_index: int,
    slot: MealSlot,
    constraint_state: ConstraintStateView,
    profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
    is_workout: bool,
) -> Set[str]:
    """HC-only filter for FC-5 optimistic future-slot checks. Spec Section 5, FC-5.

    Applies HC-1, HC-2, HC-3, HC-8 only. Does NOT apply HC-5, FC-1, FC-2, FC-3.
    """
    surviving: List[PlanningRecipe] = []
    for r in recipe_pool:
        if not check_hc1_excluded_ingredients(r, slot, day_index, constraint_state, profile, resolved_ul):
            continue
        if not check_hc2_no_same_day_reuse(r, slot, day_index, constraint_state, profile, resolved_ul):
            continue
        surviving.append(r)

    surviving = [r for r in surviving if check_hc3_cooking_time_bound(r, slot, day_index, constraint_state, profile, resolved_ul)]

    if day_index > 0 and not is_workout:
        surviving = [
            r for r in surviving
            if check_hc8_cross_day_non_workout_reuse(r, slot, day_index, constraint_state, profile, resolved_ul, is_workout)
        ]

    return {r.id for r in surviving}


def _future_slot_has_zero_eligible(
    recipe_pool: List[PlanningRecipe],
    day_index: int,
    slot_index: int,
    schedule: List[List[MealSlot]],
    constraint_state: ConstraintStateView,
    profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
) -> bool:
    """FC-5: True if any future slot on same day has zero HC-eligible recipes under optimistic assumptions. Spec Section 5."""
    if day_index >= len(schedule):
        return False
    day_slots = schedule[day_index]
    M = len(day_slots)
    for s_prime in range(slot_index + 1, M):
        slot_s = _get_slot(schedule, day_index, s_prime)
        if slot_s is None:
            continue
        next_first = schedule[day_index + 1][0] if day_index + 1 < len(schedule) else None
        act_ctx = activity_context(
            slot_s, s_prime, day_slots, next_first, profile.activity_schedule or {}
        )
        is_wk = is_workout_slot(act_ctx)
        cands = _filter_hard_constraints_only(
            recipe_pool,
            day_index,
            slot_s,
            constraint_state,
            profile,
            resolved_ul,
            is_wk,
        )
        if not cands:
            return True
    return False


def generate_candidates(
    recipe_pool: List[PlanningRecipe],
    day_index: int,
    slot_index: int,
    daily_trackers: Dict[int, DailyTracker],
    weekly_tracker: WeeklyTracker,
    schedule: List[List[MealSlot]],
    profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
    macro_bounds: MacroBoundsPrecomputation,
) -> CandidateGenerationResult:
    """Compute C(d, s) and backtrack signal. Spec Section 6.3 steps 1–7.

    Does not mutate state. No scoring, no Step 8.
    """
    slot = _get_slot(schedule, day_index, slot_index)
    if slot is None:
        return CandidateGenerationResult(
            candidates=set(),
            trigger_backtrack=True,
            calorie_excess_rejections=set(),
        )

    constraint_state = ConstraintStateView(daily_trackers=daily_trackers)
    feasibility_state = FeasibilityStateView(
        daily_trackers=daily_trackers,
        weekly_tracker=weekly_tracker,
        schedule=schedule,
    )
    day_slots = schedule[day_index]
    next_first = schedule[day_index + 1][0] if day_index + 1 < len(schedule) else None
    act_ctx = activity_context(slot, slot_index, day_slots, next_first, profile.activity_schedule or {})
    is_workout = is_workout_slot(act_ctx)

    candidates, calorie_excess_rejections = _filter_step_1_through_7(
        recipe_pool,
        day_index,
        slot_index,
        slot,
        constraint_state,
        feasibility_state,
        profile,
        resolved_ul,
        macro_bounds,
        is_workout,
    )

    trigger = False
    if not candidates:
        trigger = True
    elif _future_slot_has_zero_eligible(
        recipe_pool,
        day_index,
        slot_index,
        schedule,
        constraint_state,
        profile,
        resolved_ul,
    ):
        trigger = True

    return CandidateGenerationResult(
        candidates=candidates,
        trigger_backtrack=trigger,
        calorie_excess_rejections=calorie_excess_rejections,
    )
