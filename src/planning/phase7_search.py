"""Phase 7: Backtracking and search orchestration. Spec Sections 6.1–6.6, 9, 10, 11.

Orchestrates decision order, pinned handling, candidate generation (Phase 6),
scoring (Phase 4), ordering (Phase 5), daily/weekly validation, and backtracking.
No Primary Carb Downscaling. No reimplementation of constraints, feasibility, or scoring.
Reference: MEALPLAN_SPECIFICATION_v1.md.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.data_layer.models import MicronutrientProfile, NutritionProfile
from src.data_layer.upper_limits import validate_daily_upper_limits

from src.planning.phase0_models import (
    Assignment,
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    WeeklyTracker,
    micronutrient_profile_to_dict,
)
from src.planning.phase1_state import (
    InitialState,
    build_initial_state,
    validate_pinned_assignments,
    PinnedValidationResult,
    _add_nutrition,
)
from src.planning.phase3_feasibility import (
    FeasibilityStateView,
    MacroBoundsPrecomputation,
    check_fc4_cross_day_rdi,
    precompute_macro_bounds,
    precompute_max_daily_achievable,
)
from src.planning.phase4_scoring import ScoringStateView, composite_score
from src.planning.phase5_ordering import OrderingStateView, order_scored_candidates
from src.planning.phase6_candidates import generate_candidates, CandidateGenerationResult
from src.planning.slot_attributes import activity_context, is_workout_slot

from src.data_layer.models import UpperLimits

# Attempt limit: configurable, sensible default. Spec Section 9.4.
DEFAULT_ATTEMPT_LIMIT = 50_000


# --- Optional instrumentation (observational only) ---


@dataclass
class SearchStats:
    """Optional stats collection. All updates guarded by stats.enabled. Does not affect search behavior."""

    enabled: bool = False
    total_attempts: int = 0
    attempts_per_slot: Dict[Tuple[int, int], int] = field(default_factory=dict)
    attempts_per_day: Dict[int, int] = field(default_factory=dict)
    branching_factors: Dict[Tuple[int, int], int] = field(default_factory=dict)
    _backtrack_depths: List[int] = field(default_factory=list, repr=False)
    _start_time: Optional[float] = field(default=None, repr=False)
    _end_time: Optional[float] = field(default=None, repr=False)
    _day_starts: Dict[int, float] = field(default_factory=dict, repr=False)
    day_runtimes: Dict[int, float] = field(default_factory=dict)

    def total_runtime(self) -> float:
        if self._start_time is not None and self._end_time is not None:
            return self._end_time - self._start_time
        return 0.0

    @property
    def max_depth(self) -> int:
        return max(self._backtrack_depths, default=0)

    @property
    def average_backtrack_depth(self) -> float:
        if not self._backtrack_depths:
            return 0.0
        return sum(self._backtrack_depths) / len(self._backtrack_depths)

    def time_per_attempt(self) -> float:
        if self.total_attempts <= 0:
            return 0.0
        return self.total_runtime() / self.total_attempts


# --- Result types ---


@dataclass
class PlanSuccess:
    """TC-1: Full plan found."""
    assignments: List[Assignment]
    daily_trackers: Dict[int, DailyTracker]
    weekly_tracker: WeeklyTracker
    sodium_advisory: Optional[str] = None


@dataclass
class PlanFailure:
    """TC-2 or TC-3: Failure report. Spec Section 11."""
    failure_mode: str  # FM-1 .. FM-5
    day_index: Optional[int] = None
    slot_index: Optional[int] = None
    constraint_detail: Optional[str] = None
    best_partial_assignments: List[Assignment] = field(default_factory=list)
    best_partial_daily_trackers: Dict[int, DailyTracker] = field(default_factory=dict)
    attempt_count: int = 0
    sodium_advisory: Optional[str] = None


def _is_pinned(profile: PlanningUserProfile, day_index: int, slot_index: int) -> bool:
    key = (day_index + 1, slot_index)
    return key in profile.pinned_assignments


def _get_pinned_recipe_id(profile: PlanningUserProfile, day_index: int, slot_index: int) -> Optional[str]:
    return profile.pinned_assignments.get((day_index + 1, slot_index))


def _recipe_to_nutrition_profile(recipe: PlanningRecipe) -> NutritionProfile:
    micro = getattr(recipe.nutrition, "micronutrients", None)
    micro_dict = micronutrient_profile_to_dict(micro)
    valid = list(MicronutrientProfile.__dataclass_fields__.keys())
    kwargs = {k: micro_dict.get(k, 0.0) for k in valid}
    micro_profile = MicronutrientProfile(**kwargs) if micro_dict else None
    return NutritionProfile(
        recipe.nutrition.calories,
        recipe.nutrition.protein_g,
        recipe.nutrition.fat_g,
        recipe.nutrition.carbs_g,
        micronutrients=micro_profile,
    )


def _subtract_nutrition(a: NutritionProfile, b: NutritionProfile) -> NutritionProfile:
    """a - b for macros and micronutrients."""
    micro_a = micronutrient_profile_to_dict(a.micronutrients) if a.micronutrients else {}
    micro_b = micronutrient_profile_to_dict(b.micronutrients) if b.micronutrients else {}
    valid = set(MicronutrientProfile.__dataclass_fields__.keys())
    all_keys = (set(micro_a) | set(micro_b)) & valid
    micro_diff = {k: micro_a.get(k, 0.0) - micro_b.get(k, 0.0) for k in all_keys}
    micro_profile = MicronutrientProfile(**{k: micro_diff.get(k, 0.0) for k in valid}) if all_keys else None
    return NutritionProfile(
        a.calories - b.calories,
        a.protein_g - b.protein_g,
        a.fat_g - b.fat_g,
        a.carbs_g - b.carbs_g,
        micronutrients=micro_profile,
    )


def _dict_subtract(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    all_keys = set(a) | set(b)
    return {k: a.get(k, 0.0) - b.get(k, 0.0) for k in all_keys}


def _daily_tracker_to_micro_profile(tracker: DailyTracker) -> MicronutrientProfile:
    valid = list(MicronutrientProfile.__dataclass_fields__.keys())
    kwargs = {k: tracker.micronutrients_consumed.get(k, 0.0) for k in valid}
    return MicronutrientProfile(**kwargs)


# --- Apply assignment (forward) ---


def _apply_assignment(
    daily_trackers: Dict[int, DailyTracker],
    assignments: List[Assignment],
    day_index: int,
    slot_index: int,
    recipe_id: str,
    recipe: PlanningRecipe,
    is_workout: bool,
    schedule: List[List[MealSlot]],
) -> None:
    """Update state with one assignment. Mutates daily_trackers and assignments."""
    day_slots = schedule[day_index]
    slots_total = len(day_slots)
    tracker = daily_trackers.get(day_index)
    if tracker is None:
        tracker = DailyTracker(slots_total=slots_total)
        daily_trackers[day_index] = tracker

    n = _recipe_to_nutrition_profile(recipe)
    micro = micronutrient_profile_to_dict(n.micronutrients) if n.micronutrients else {}

    new_cal = tracker.calories_consumed + n.calories
    new_pro = tracker.protein_consumed + n.protein_g
    new_fat = tracker.fat_consumed + n.fat_g
    new_carbs = tracker.carbs_consumed + n.carbs_g
    new_micro = _dict_subtract(tracker.micronutrients_consumed, {})  # copy
    for k, v in micro.items():
        new_micro[k] = new_micro.get(k, 0.0) + v
    new_used = set(tracker.used_recipe_ids) | {recipe_id}
    new_non_workout = set(tracker.non_workout_recipe_ids)
    if not is_workout:
        new_non_workout = new_non_workout | {recipe_id}
    daily_trackers[day_index] = DailyTracker(
        calories_consumed=new_cal,
        protein_consumed=new_pro,
        fat_consumed=new_fat,
        carbs_consumed=new_carbs,
        micronutrients_consumed=new_micro,
        used_recipe_ids=new_used,
        non_workout_recipe_ids=new_non_workout,
        slots_assigned=tracker.slots_assigned + 1,
        slots_total=slots_total,
    )
    assignments.append((day_index, slot_index, recipe_id))


# --- Remove assignment (unwind) ---


def _remove_assignment(
    daily_trackers: Dict[int, DailyTracker],
    weekly_tracker: WeeklyTracker,
    assignments: List[Assignment],
    day_index: int,
    slot_index: int,
    recipe_id: str,
    recipe: PlanningRecipe,
    is_workout: bool,
    schedule: List[List[MealSlot]],
    profile: PlanningUserProfile,
    completed_days: Optional[Set[int]] = None,
) -> None:
    """Remove one assignment from state. Handles day-boundary: subtract day from weekly only if day was completed."""
    tracker = daily_trackers[day_index]
    n = _recipe_to_nutrition_profile(recipe)
    micro = micronutrient_profile_to_dict(n.micronutrients) if n.micronutrients else {}
    slots_total = tracker.slots_total
    new_slots_assigned = tracker.slots_assigned - 1

    if new_slots_assigned == 0:
        if completed_days is not None and day_index in completed_days:
            day_totals_before = NutritionProfile(
                tracker.calories_consumed,
                tracker.protein_consumed,
                tracker.fat_consumed,
                tracker.carbs_consumed,
                micronutrients=_daily_tracker_to_micro_profile(tracker) if tracker.micronutrients_consumed else None,
            )
            weekly_tracker.weekly_totals = _subtract_nutrition(weekly_tracker.weekly_totals, day_totals_before)
            completed_days.discard(day_index)
        weekly_tracker.days_completed = max(0, weekly_tracker.days_completed - 1)
        weekly_tracker.days_remaining = len(schedule) - weekly_tracker.days_completed
        _recompute_carryover(weekly_tracker, profile, len(schedule))
        if day_index in daily_trackers:
            del daily_trackers[day_index]
    else:
        new_cal = tracker.calories_consumed - n.calories
        new_pro = tracker.protein_consumed - n.protein_g
        new_fat = tracker.fat_consumed - n.fat_g
        new_carbs = tracker.carbs_consumed - n.carbs_g
        new_micro = {k: tracker.micronutrients_consumed.get(k, 0.0) - micro.get(k, 0.0) for k in set(tracker.micronutrients_consumed) | set(micro)}
        new_used = set(tracker.used_recipe_ids) - {recipe_id}
        new_non_workout = set(tracker.non_workout_recipe_ids)
        if not is_workout:
            new_non_workout = new_non_workout - {recipe_id}
        daily_trackers[day_index] = DailyTracker(
            calories_consumed=new_cal,
            protein_consumed=new_pro,
            fat_consumed=new_fat,
            carbs_consumed=new_carbs,
            micronutrients_consumed=new_micro,
            used_recipe_ids=new_used,
            non_workout_recipe_ids=new_non_workout,
            slots_assigned=new_slots_assigned,
            slots_total=slots_total,
        )

    try:
        assignments.remove((day_index, slot_index, recipe_id))
    except ValueError:
        pass


def _recompute_carryover(weekly_tracker: WeeklyTracker, profile: PlanningUserProfile, D: int) -> None:
    """Set carryover_needs from weekly_totals and days_completed. Spec Section 3.3."""
    tracked = profile.micronutrient_targets
    if not tracked:
        weekly_tracker.carryover_needs = {}
        return
    micro = micronutrient_profile_to_dict(getattr(weekly_tracker.weekly_totals, "micronutrients", None))
    days_done = weekly_tracker.days_completed
    carryover = {}
    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        needed = daily_rdi * days_done
        consumed = micro.get(n, 0.0)
        carryover[n] = max(0.0, needed - consumed)
    weekly_tracker.carryover_needs = carryover


# --- Daily validation (Section 6.5) ---


DAILY_TOLERANCE = 0.10


def _daily_validation(
    day_index: int,
    tracker: DailyTracker,
    profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
) -> Tuple[bool, Optional[str]]:
    """Returns (pass, failure_reason)."""
    if abs(tracker.calories_consumed - profile.daily_calories) > DAILY_TOLERANCE * profile.daily_calories:
        return False, "calories"
    if abs(tracker.protein_consumed - profile.daily_protein_g) > DAILY_TOLERANCE * profile.daily_protein_g:
        return False, "protein"
    if abs(tracker.carbs_consumed - profile.daily_carbs_g) > DAILY_TOLERANCE * profile.daily_carbs_g:
        return False, "carbs"
    fat_min, fat_max = profile.daily_fat_g
    if tracker.fat_consumed < fat_min or tracker.fat_consumed > fat_max:
        return False, "fat"
    if profile.max_daily_calories is not None and tracker.calories_consumed > profile.max_daily_calories:
        return False, "calorie_ceiling"
    if resolved_ul is not None:
        micro_profile = _daily_tracker_to_micro_profile(tracker)
        violations = validate_daily_upper_limits(micro_profile, resolved_ul)
        if violations:
            return False, f"UL:{violations[0].nutrient}"
    return True, None


# --- Weekly validation (Section 6.6) ---


def _weekly_validation(
    D: int,
    weekly_tracker: WeeklyTracker,
    profile: PlanningUserProfile,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Returns (pass, failure_reason, sodium_advisory)."""
    tracked = profile.micronutrient_targets
    micro = micronutrient_profile_to_dict(getattr(weekly_tracker.weekly_totals, "micronutrients", None))
    sodium_adv = None
    if "sodium_mg" in micro and "sodium_mg" in tracked:
        daily_rdi = tracked["sodium_mg"]
        if daily_rdi > 0:
            total_sodium = micro.get("sodium_mg", 0.0)
            if total_sodium > 2.0 * daily_rdi * D:
                sodium_adv = "Weekly sodium exceeds 200% of prorated RDI."
    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        needed = daily_rdi * D
        consumed = micro.get(n, 0.0)
        if consumed < needed:
            return False, f"weekly_deficit:{n}", sodium_adv
    return True, None, sodium_adv


# --- Update weekly after day completion ---


def _update_weekly_after_day(
    daily_trackers: Dict[int, DailyTracker],
    weekly_tracker: WeeklyTracker,
    day_index: int,
    schedule: List[List[MealSlot]],
    profile: PlanningUserProfile,
    D: int,
) -> None:
    """Add day's totals to weekly; increment days_completed; recompute carryover."""
    tracker = daily_trackers[day_index]
    valid = list(MicronutrientProfile.__dataclass_fields__.keys())
    kwargs = {k: tracker.micronutrients_consumed.get(k, 0.0) for k in valid}
    micro = MicronutrientProfile(**kwargs) if tracker.micronutrients_consumed else None
    day_nut = NutritionProfile(
        tracker.calories_consumed,
        tracker.protein_consumed,
        tracker.fat_consumed,
        tracker.carbs_consumed,
        micronutrients=micro,
    )
    weekly_tracker.weekly_totals = _add_nutrition(weekly_tracker.weekly_totals, day_nut)
    weekly_tracker.days_completed += 1
    weekly_tracker.days_remaining = D - weekly_tracker.days_completed
    _recompute_carryover(weekly_tracker, profile, D)


# --- Search state and candidate cache ---


@dataclass
class _CandidateCacheEntry:
    ordered: List[PlanningRecipe]  # ordered by score then tie-break
    pointer: int


def _decision_order(schedule: List[List[MealSlot]], D: int) -> List[Tuple[int, int]]:
    """List of (day_index, slot_index) in spec order."""
    out: List[Tuple[int, int]] = []
    for day_index in range(D):
        for slot_index in range(len(schedule[day_index])):
            out.append((day_index, slot_index))
    return out


def run_meal_plan_search(
    profile: PlanningUserProfile,
    recipe_pool: List[PlanningRecipe],
    D: int,
    resolved_ul: Optional[UpperLimits],
    attempt_limit: int = DEFAULT_ATTEMPT_LIMIT,
    stats: Optional[SearchStats] = None,
) -> Tuple[bool, Any]:
    """
    Run the full meal plan search. Returns (success, PlanSuccess | PlanFailure).
    Spec Sections 6.1–6.6, 9, 10, 11. Deterministic.
    If stats is provided and stats.enabled, observational metrics are recorded.
    """
    if stats is not None and stats.enabled:
        stats._start_time = time.perf_counter()
    schedule = profile.schedule
    if len(schedule) != D:
        if stats is not None and stats.enabled:
            stats._end_time = time.perf_counter()
            stats.total_attempts = 0
        return False, PlanFailure(failure_mode="FM-3", constraint_detail="Schedule length != D")
    recipe_by_id = {r.id: r for r in recipe_pool}

    # Pinned pre-validation (Section 3.5)
    pin_result = validate_pinned_assignments(profile, recipe_by_id, D)
    if not pin_result.success:
        if stats is not None and stats.enabled:
            stats._end_time = time.perf_counter()
            stats.total_attempts = 0
        return False, PlanFailure(
            failure_mode="FM-3",
            constraint_detail=pin_result.failed_hc,
        )

    # Initial state: pinned only; zero weekly totals for search (we add on day completion)
    initial = build_initial_state(profile, recipe_by_id, D)
    daily_trackers = {k: _copy_tracker(v) for k, v in initial.daily_trackers.items()}
    weekly_tracker = WeeklyTracker(
        weekly_totals=NutritionProfile(0.0, 0.0, 0.0, 0.0),
        days_completed=0,
        days_remaining=D,
        carryover_needs={n: 0.0 for n in profile.micronutrient_targets},
    )
    assignments: List[Assignment] = list(initial.assignments)

    macro_bounds = precompute_macro_bounds(recipe_pool, max_slots=8)
    slot_counts: Set[int] = set()
    for d in range(D):
        slot_counts.add(len(schedule[d]))
    nutrient_names = list(profile.micronutrient_targets.keys()) or list(MicronutrientProfile.__dataclass_fields__.keys())
    max_daily_achievable = precompute_max_daily_achievable(recipe_pool, nutrient_names, slot_counts)

    order = _decision_order(schedule, D)
    cache: Dict[Tuple[int, int], _CandidateCacheEntry] = {}
    completed_days: Set[int] = set()
    attempt_count = 0
    i = 0
    best_assignments: List[Assignment] = list(assignments)
    best_daily_trackers: Dict[int, DailyTracker] = dict(daily_trackers)
    sodium_advisory: Optional[str] = None

    while i < len(order):
        day_index, slot_index = order[i]
        if attempt_count >= attempt_limit:
            if stats is not None and stats.enabled:
                stats._end_time = time.perf_counter()
                stats.total_attempts = attempt_count
            return False, PlanFailure(
                failure_mode="FM-5",
                best_partial_assignments=best_assignments,
                best_partial_daily_trackers=best_daily_trackers,
                attempt_count=attempt_count,
                sodium_advisory=sodium_advisory,
            )

        if stats is not None and stats.enabled and slot_index == 0:
            stats._day_starts[day_index] = time.perf_counter()

        # FC-4 at start of day d > 1 (Section 6, BT-4)
        if day_index > 0 and slot_index == 0:
            feas_state = FeasibilityStateView(
                daily_trackers=dict(daily_trackers),
                weekly_tracker=weekly_tracker,
                schedule=schedule,
            )
            if not check_fc4_cross_day_rdi(day_index, feas_state, profile, D, max_daily_achievable):
                # BT-4: backtrack
                target = _find_backtrack_target(order, i, cache, profile)
                if target is None:
                    if stats is not None and stats.enabled:
                        stats._end_time = time.perf_counter()
                        stats.total_attempts = attempt_count
                    return False, PlanFailure(
                        failure_mode="FM-4",
                        day_index=day_index,
                        constraint_detail="FC-4 irrecoverable deficit",
                        best_partial_assignments=list(assignments),
                        best_partial_daily_trackers=dict(daily_trackers),
                        attempt_count=attempt_count,
                    )
                if stats is not None and stats.enabled:
                    stats._backtrack_depths.append(i - target)
                i, daily_trackers, weekly_tracker, assignments, cache = _unwind_to(
                    target, order, daily_trackers, weekly_tracker, assignments, cache,
                    completed_days, recipe_by_id, schedule, profile,
                )
                continue

        if _is_pinned(profile, day_index, slot_index):
            assigned_slots = {(a[0], a[1]) for a in assignments}
            if (day_index, slot_index) in assigned_slots:
                i += 1
                continue
            recipe_id = _get_pinned_recipe_id(profile, day_index, slot_index)
            recipe = recipe_by_id[recipe_id]
            day_slots = schedule[day_index]
            next_first = schedule[day_index + 1][0] if day_index + 1 < D else None
            act_ctx = activity_context(day_slots[slot_index], slot_index, day_slots, next_first, profile.activity_schedule or {})
            is_w = is_workout_slot(act_ctx)
            _apply_assignment(daily_trackers, assignments, day_index, slot_index, recipe_id, recipe, is_w, schedule)
            i += 1
            attempt_count += 1
            if stats is not None and stats.enabled:
                stats.attempts_per_slot[(day_index, slot_index)] = stats.attempts_per_slot.get((day_index, slot_index), 0) + 1
                stats.attempts_per_day[day_index] = stats.attempts_per_day.get(day_index, 0) + 1
            if _update_best(assignments, daily_trackers, best_assignments, best_daily_trackers):
                pass
            continue

        # Non-pinned: use cache or generate
        key = (day_index, slot_index)
        if key not in cache:
            cg = generate_candidates(
                recipe_pool, day_index, slot_index,
                dict(daily_trackers), copy.deepcopy(weekly_tracker), schedule,
                profile, resolved_ul, macro_bounds,
            )
            if cg.trigger_backtrack:
                target = _find_backtrack_target(order, i, cache, profile)
                if target is None:
                    if stats is not None and stats.enabled:
                        stats._end_time = time.perf_counter()
                        stats.total_attempts = attempt_count
                    return False, PlanFailure(
                        failure_mode="FM-1",
                        day_index=day_index,
                        slot_index=slot_index,
                        constraint_detail="Empty candidate set or FC-5",
                        best_partial_assignments=list(assignments),
                        best_partial_daily_trackers=dict(daily_trackers),
                        attempt_count=attempt_count,
                    )
                if stats is not None and stats.enabled:
                    stats._backtrack_depths.append(i - target)
                i, daily_trackers, weekly_tracker, assignments, cache = _unwind_to(
                    target, order, daily_trackers, weekly_tracker, assignments, cache,
                    completed_days, recipe_by_id, schedule, profile,
                )
                continue
            scored = []
            for rid in sorted(cg.candidates):
                r = recipe_by_id[rid]
                state_view = ScoringStateView(daily_trackers=dict(daily_trackers), weekly_tracker=weekly_tracker, schedule=schedule)
                sc = composite_score(r, day_index, slot_index, state_view, profile)
                scored.append((r, sc))
            ord_state = OrderingStateView(daily_trackers=dict(daily_trackers), weekly_tracker=weekly_tracker)
            ordered = order_scored_candidates(scored, ord_state, profile, day_index)
            cache[key] = _CandidateCacheEntry(ordered=[r for r, _ in ordered], pointer=0)
            if stats is not None and stats.enabled:
                stats.branching_factors[key] = len(cache[key].ordered)

        entry = cache[key]
        if entry.pointer >= len(entry.ordered):
            target = _find_backtrack_target(order, i, cache, profile)
            if target is None:
                if stats is not None and stats.enabled:
                    stats._end_time = time.perf_counter()
                    stats.total_attempts = attempt_count
                return False, PlanFailure(
                    failure_mode="FM-2",
                    best_partial_assignments=list(best_assignments),
                    best_partial_daily_trackers=dict(best_daily_trackers),
                    attempt_count=attempt_count,
                    sodium_advisory=sodium_advisory,
                )
            if stats is not None and stats.enabled:
                stats._backtrack_depths.append(i - target)
            i, daily_trackers, weekly_tracker, assignments, cache = _unwind_to(
                target, order, daily_trackers, weekly_tracker, assignments, cache,
                completed_days, recipe_by_id, schedule, profile,
            )
            continue

        recipe = entry.ordered[entry.pointer]
        recipe_id = recipe.id
        day_slots = schedule[day_index]
        next_first = schedule[day_index + 1][0] if day_index + 1 < D else None
        act_ctx = activity_context(day_slots[slot_index], slot_index, day_slots, next_first, profile.activity_schedule or {})
        is_w = is_workout_slot(act_ctx)
        _apply_assignment(daily_trackers, assignments, day_index, slot_index, recipe_id, recipe, is_w, schedule)
        entry.pointer += 1
        i += 1
        attempt_count += 1
        if stats is not None and stats.enabled:
            stats.attempts_per_slot[(day_index, slot_index)] = stats.attempts_per_slot.get((day_index, slot_index), 0) + 1
            stats.attempts_per_day[day_index] = stats.attempts_per_day.get(day_index, 0) + 1
        if _update_best(assignments, daily_trackers, best_assignments, best_daily_trackers):
            pass

        # Day completion (Section 6.5)
        tracker = daily_trackers.get(day_index)
        if tracker is not None and tracker.slots_assigned == tracker.slots_total:
            ok, reason = _daily_validation(day_index, tracker, profile, resolved_ul)
            if not ok:
                target = _find_backtrack_target(order, i, cache, profile)
                if target is None:
                    if stats is not None and stats.enabled:
                        stats._end_time = time.perf_counter()
                        stats.total_attempts = attempt_count
                    return False, PlanFailure(
                        failure_mode="FM-2",
                        day_index=day_index,
                        constraint_detail=reason or "daily_validation",
                        best_partial_assignments=list(assignments),
                        best_partial_daily_trackers=dict(daily_trackers),
                        attempt_count=attempt_count,
                    )
                if stats is not None and stats.enabled:
                    stats._backtrack_depths.append(i - target)
                i, daily_trackers, weekly_tracker, assignments, cache = _unwind_to(
                    target, order, daily_trackers, weekly_tracker, assignments, cache,
                    completed_days, recipe_by_id, schedule, profile,
                )
                continue
            if stats is not None and stats.enabled:
                stats.day_runtimes[day_index] = time.perf_counter() - stats._day_starts.get(day_index, stats._start_time or 0)
            _update_weekly_after_day(daily_trackers, weekly_tracker, day_index, schedule, profile, D)
            completed_days.add(day_index)

        # Weekly completion (Section 6.6) or single-day success (TC-4)
        if day_index == D - 1:
            last_tracker = daily_trackers.get(day_index)
            if last_tracker is not None and last_tracker.slots_assigned == last_tracker.slots_total:
                if D == 1:
                    if stats is not None and stats.enabled:
                        stats._end_time = time.perf_counter()
                        stats.total_attempts = attempt_count
                        if day_index in stats._day_starts:
                            stats.day_runtimes[day_index] = stats._end_time - stats._day_starts[day_index]
                    return True, PlanSuccess(
                        assignments=list(assignments),
                        daily_trackers=dict(daily_trackers),
                        weekly_tracker=weekly_tracker,
                        sodium_advisory=sodium_advisory,
                    )
                ok, reason, sodium_adv = _weekly_validation(D, weekly_tracker, profile)
                if sodium_adv:
                    sodium_advisory = sodium_adv
                if not ok:
                    target = _find_backtrack_target(order, i, cache, profile)
                    if target is None:
                        if stats is not None and stats.enabled:
                            stats._end_time = time.perf_counter()
                            stats.total_attempts = attempt_count
                        return False, PlanFailure(
                            failure_mode="FM-4",
                            constraint_detail=reason or "weekly_validation",
                            best_partial_assignments=list(assignments),
                            best_partial_daily_trackers=dict(daily_trackers),
                            attempt_count=attempt_count,
                            sodium_advisory=sodium_advisory,
                        )
                    if stats is not None and stats.enabled:
                        stats._backtrack_depths.append(i - target)
                    i, daily_trackers, weekly_tracker, assignments, cache = _unwind_to(
                        target, order, daily_trackers, weekly_tracker, assignments, cache,
                        completed_days, recipe_by_id, schedule, profile,
                    )
                    continue
                if stats is not None and stats.enabled:
                    stats._end_time = time.perf_counter()
                    stats.total_attempts = attempt_count
                return True, PlanSuccess(
                    assignments=list(assignments),
                    daily_trackers=dict(daily_trackers),
                    weekly_tracker=weekly_tracker,
                    sodium_advisory=sodium_advisory,
                )

    if stats is not None and stats.enabled:
        stats._end_time = time.perf_counter()
        stats.total_attempts = attempt_count
    return False, PlanFailure(
        failure_mode="FM-2",
        best_partial_assignments=list(best_assignments),
        best_partial_daily_trackers=best_daily_trackers,
        attempt_count=attempt_count,
        sodium_advisory=sodium_advisory,
    )


def _copy_tracker(t: DailyTracker) -> DailyTracker:
    return DailyTracker(
        calories_consumed=t.calories_consumed,
        protein_consumed=t.protein_consumed,
        fat_consumed=t.fat_consumed,
        carbs_consumed=t.carbs_consumed,
        micronutrients_consumed=dict(t.micronutrients_consumed),
        used_recipe_ids=set(t.used_recipe_ids),
        non_workout_recipe_ids=set(t.non_workout_recipe_ids),
        slots_assigned=t.slots_assigned,
        slots_total=t.slots_total,
    )


def _update_best(
    assignments: List[Assignment],
    daily_trackers: Dict[int, DailyTracker],
    best_assignments: List[Assignment],
    best_daily_trackers: Dict[int, DailyTracker],
) -> bool:
    if len(assignments) > len(best_assignments):
        best_assignments.clear()
        best_assignments.extend(assignments)
        best_daily_trackers.clear()
        for k, v in daily_trackers.items():
            best_daily_trackers[k] = _copy_tracker(v)
        return True
    return False


def _find_backtrack_target(
    order: List[Tuple[int, int]],
    current_i: int,
    cache: Dict[Tuple[int, int], _CandidateCacheEntry],
    profile: PlanningUserProfile,
) -> Optional[int]:
    """Index into order of the last non-pinned decision point with untried candidates, or None."""
    for j in range(current_i - 1, -1, -1):
        day_index, slot_index = order[j]
        if _is_pinned(profile, day_index, slot_index):
            continue
        key = (day_index, slot_index)
        if key in cache:
            entry = cache[key]
            if entry.pointer < len(entry.ordered):
                return j
    return None


def _unwind_to(
    target_i: int,
    order: List[Tuple[int, int]],
    daily_trackers: Dict[int, DailyTracker],
    weekly_tracker: WeeklyTracker,
    assignments: List[Assignment],
    cache: Dict[Tuple[int, int], _CandidateCacheEntry],
    completed_days: Set[int],
    recipe_by_id: Dict[str, PlanningRecipe],
    schedule: List[List[MealSlot]],
    profile: PlanningUserProfile,
) -> Tuple[int, Dict[int, DailyTracker], WeeklyTracker, List[Assignment], Dict[Tuple[int, int], _CandidateCacheEntry]]:
    """Unwind state to target_i by value: remove target (non-pinned) and all later non-pinned assignments. Pinned never removed."""
    target_day, target_slot = order[target_i]
    to_remove: List[Tuple[int, int, str]] = [
        (d, s, rid)
        for (d, s, rid) in assignments
        if (d, s) >= (target_day, target_slot) and not _is_pinned(profile, d, s)
    ]
    to_remove.sort(key=lambda x: (x[0], x[1]), reverse=True)

    for di, si, rid in to_remove:
        recipe = recipe_by_id.get(rid)
        if recipe is None:
            continue
        day_slots = schedule[di]
        next_first = schedule[di + 1][0] if di + 1 < len(schedule) else None
        act_ctx = activity_context(day_slots[si], si, day_slots, next_first, profile.activity_schedule or {})
        is_w = is_workout_slot(act_ctx)
        _remove_assignment(
            daily_trackers, weekly_tracker, assignments, di, si, rid, recipe, is_w, schedule, profile, completed_days
        )

    current_day = to_remove[0][0] if to_remove else target_day
    crossed_day_boundary = target_day < current_day
    cache_cleaned: Dict[Tuple[int, int], _CandidateCacheEntry] = {}
    for (d, s), entry in cache.items():
        if (d, s) < (target_day, target_slot):
            cache_cleaned[(d, s)] = entry
        elif (d, s) == (target_day, target_slot) and not crossed_day_boundary:
            entry.pointer += 1
            cache_cleaned[(d, s)] = entry

    return target_i, daily_trackers, weekly_tracker, assignments, cache_cleaned
