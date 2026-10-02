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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.data_layer.models import MicronutrientProfile, NutritionProfile

from src.planning.phase0_models import (
    Assignment,
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    WeeklyTracker,
    get_effective_nutrition,
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
    candidate_passes_micro_floor,
    check_fc4_cross_day_rdi,
    check_structural_feasibility,
    floor_bounds_to_slot_mda,
    precompute_macro_bounds,
    precompute_micro_floor_bounds,
)
from src.planning.phase4_scoring import ScoringStateView, composite_score
from src.planning.phase5_ordering import OrderingStateView, ordering_key
from src.planning.phase6_candidates import (
    CandidateGenerationResult,
    check_slot_statically,
    generate_candidates,
)
from src.planning.phase9_carb_scaling import compute_variant_nutrition, load_scalable_carb_sources
from src.planning.micronutrient_policy import (
    MICRONUTRIENT_EPSILON as EPSILON,
    cumulative_minimum_total,
    is_below_weekly_minimum,
    sodium_weekly_advisory_max_mg,
    tau_from_profile,
)
from src.planning.failure_attribution import (
    Attribution,
    DAILY_TOLERANCE,
    diagnose_exhausted_search,
    daily_tracker_to_micro_profile as _daily_tracker_to_micro_profile,
    daily_validation as _daily_validation,
    weekly_tracker_from_best_micro,
)
from src.planning.phase10_reporting import (
    MealPlanResult,
    build_failure,
    build_plan_snapshot,
    build_report_fm1,
    build_report_fm_tag_empty,
    build_report_fm2,
    build_report_fm3,
    build_report_fm4,
    build_report_fm5,
    build_sodium_warning,
    ensure_report_failures,
    HC8_SEQUENCE_FIX_HINT,
    PIN_VIOLATION_DIRECT,
    PIN_VIOLATION_DOWNSTREAM,
    result_from_failure,
    result_from_success,
)
from src.planning.slot_attributes import activity_context_for_profile, is_workout_slot

from src.data_layer.models import UpperLimits

# Attempt limit: configurable, sensible default. Spec Section 9.4.
DEFAULT_ATTEMPT_LIMIT = 50_000

# Debug logging gate: when True, emit structured logs for assign/remove/backtrack. No behavior change.
DEBUG_SEARCH = False

def _debug_log(event: str, **kwargs: Any) -> None:
    """Emit structured debug log when DEBUG_SEARCH is True. No-op otherwise."""
    if DEBUG_SEARCH:
        payload = {"event": event, **kwargs}
        print(f"[phase7_debug] {payload}")


def _normalize_fp(value: float) -> float:
    """Clamp near-zero values to exact zero to absorb floating-point cancellation drift."""
    if abs(value) < EPSILON:
        return 0.0
    return value


def _normalize_nutrition_profile(profile: NutritionProfile) -> None:
    """Normalize weekly_totals in place so tiny residuals become zero. Mutates profile."""
    for attr in ("calories", "protein_g", "fat_g", "carbs_g"):
        val = getattr(profile, attr)
        new_val = _normalize_fp(val)
        if new_val != val and DEBUG_SEARCH:
            _debug_log("fp_normalize", nutrient=attr, before=val, after=new_val)
        setattr(profile, attr, new_val)
    if profile.micronutrients is not None:
        for fname in MicronutrientProfile.__dataclass_fields__:
            val = getattr(profile.micronutrients, fname)
            new_val = _normalize_fp(val)
            if new_val != val and DEBUG_SEARCH:
                _debug_log("fp_normalize", nutrient=fname, before=val, after=new_val)
            setattr(profile.micronutrients, fname, new_val)


class PlannerStateError(Exception):
    """Raised when planner state invariants are violated (e.g. weekly vs completed_days mismatch)."""


def _validate_planner_state(
    daily_trackers: Dict[int, DailyTracker],
    weekly_tracker: WeeklyTracker,
    completed_days: Set[int],
    D: int,
    schedule: List[List[MealSlot]],
) -> None:
    """Validate planner state invariants. Raises PlannerStateError on violation."""
    if not (0 <= weekly_tracker.days_completed <= D):
        raise PlannerStateError(
            f"days_completed={weekly_tracker.days_completed} not in [0, {D}]"
        )
    if weekly_tracker.days_remaining != D - weekly_tracker.days_completed:
        raise PlannerStateError(
            f"days_remaining={weekly_tracker.days_remaining} != D - days_completed = {D - weekly_tracker.days_completed}"
        )
    if len(completed_days) != weekly_tracker.days_completed:
        raise PlannerStateError(
            f"len(completed_days)={len(completed_days)} != days_completed={weekly_tracker.days_completed}"
        )
    wt = weekly_tracker.weekly_totals
    if wt.calories < -EPSILON or wt.protein_g < -EPSILON or wt.fat_g < -EPSILON or wt.carbs_g < -EPSILON:
        raise PlannerStateError(
            f"negative weekly macro: cal={wt.calories} pro={wt.protein_g} fat={wt.fat_g} carbs={wt.carbs_g}"
        )
    micro = micronutrient_profile_to_dict(getattr(wt, "micronutrients", None))
    for k, v in micro.items():
        if v < -EPSILON:
            raise PlannerStateError(f"negative weekly micronutrient {k}={v}")
    if completed_days:
        sum_cal = sum(daily_trackers[d].calories_consumed for d in completed_days if d in daily_trackers)
        sum_pro = sum(daily_trackers[d].protein_consumed for d in completed_days if d in daily_trackers)
        sum_fat = sum(daily_trackers[d].fat_consumed for d in completed_days if d in daily_trackers)
        sum_carbs = sum(daily_trackers[d].carbs_consumed for d in completed_days if d in daily_trackers)
        tol = 1e-6
        if abs(wt.calories - sum_cal) > tol:
            raise PlannerStateError(f"weekly calories {wt.calories} != sum(completed_days) {sum_cal}")
        if abs(wt.protein_g - sum_pro) > tol:
            raise PlannerStateError(f"weekly protein {wt.protein_g} != sum(completed_days) {sum_pro}")
        if abs(wt.fat_g - sum_fat) > tol:
            raise PlannerStateError(f"weekly fat {wt.fat_g} != sum(completed_days) {sum_fat}")
        if abs(wt.carbs_g - sum_carbs) > tol:
            raise PlannerStateError(f"weekly carbs {wt.carbs_g} != sum(completed_days) {sum_carbs}")
        valid = list(MicronutrientProfile.__dataclass_fields__.keys())
        for n in valid:
            wv = micro.get(n, 0.0)
            dv = sum(daily_trackers[d].micronutrients_consumed.get(n, 0.0) for d in completed_days if d in daily_trackers)
            if abs(wv - dv) > tol:
                raise PlannerStateError(f"weekly micro {n}={wv} != sum(completed_days) {dv}")


# --- Optional instrumentation (observational only) ---


@dataclass
class SearchStats:
    """Optional stats collection. All updates guarded by stats.enabled. Does not affect search behavior."""

    enabled: bool = False
    total_attempts: int = 0
    attempts_per_slot: Dict[Tuple[int, int], int] = field(default_factory=dict)
    attempts_per_day: Dict[int, int] = field(default_factory=dict)
    branching_factors: Dict[Tuple[int, int], int] = field(default_factory=dict)
    floor_bound_candidates_dropped: int = 0
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
    variant_index: int = 0,
    variant_nutrition: Optional[NutritionProfile] = None,
) -> None:
    """Update state with one assignment. Mutates daily_trackers and assignments. HC-2/HC-8 use recipe_id only."""
    day_slots = schedule[day_index]
    slots_total = len(day_slots)
    tracker = daily_trackers.get(day_index)
    if tracker is None:
        tracker = DailyTracker(slots_total=slots_total)
        daily_trackers[day_index] = tracker

    nut = get_effective_nutrition(recipe, variant_index, variant_nutrition)
    micro = micronutrient_profile_to_dict(nut.micronutrients) if nut.micronutrients else {}

    new_cal = tracker.calories_consumed + nut.calories
    new_pro = tracker.protein_consumed + nut.protein_g
    new_fat = tracker.fat_consumed + nut.fat_g
    new_carbs = tracker.carbs_consumed + nut.carbs_g
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
    assignments.append(Assignment(day_index, slot_index, recipe_id, variant_index))
    _debug_log("assign", day_index=day_index, slot_index=slot_index, recipe_id=recipe_id, variant_index=variant_index)


# --- Remove assignment (unwind) ---


def _uncomplete_day(
    daily_trackers: Dict[int, DailyTracker],
    weekly_tracker: WeeklyTracker,
    day_index: int,
    schedule: List[List[MealSlot]],
    profile: PlanningUserProfile,
    completed_days: Set[int],
) -> None:
    """Subtract a completed day's totals from weekly and mark the day incomplete.

    Used when removing an assignment from a completed day, and when unwinding
    past a fully pinned completed day (pins are never removed from assignments).
    """
    if day_index not in completed_days:
        return
    tracker = daily_trackers.get(day_index)
    if tracker is None:
        completed_days.discard(day_index)
        return
    D = len(schedule)
    valid = list(MicronutrientProfile.__dataclass_fields__.keys())
    kwargs = {k: tracker.micronutrients_consumed.get(k, 0.0) for k in valid}
    day_micro = MicronutrientProfile(**kwargs) if tracker.micronutrients_consumed else None
    day_nut = NutritionProfile(
        tracker.calories_consumed,
        tracker.protein_consumed,
        tracker.fat_consumed,
        tracker.carbs_consumed,
        micronutrients=day_micro,
    )
    weekly_tracker.weekly_totals = _subtract_nutrition(weekly_tracker.weekly_totals, day_nut)
    _normalize_nutrition_profile(weekly_tracker.weekly_totals)
    completed_days.discard(day_index)
    weekly_tracker.days_completed = max(0, weekly_tracker.days_completed - 1)
    weekly_tracker.days_remaining = D - weekly_tracker.days_completed
    _recompute_carryover(weekly_tracker, profile, D)
    _debug_log("day_uncomplete", day_index=day_index)


def _remaining_budget_from_tracker(
    tracker: DailyTracker,
    profile: PlanningUserProfile,
) -> Dict[str, Any]:
    """Budget remaining after a day's pinned (or locked) assignments."""
    fat_min, fat_max = profile.daily_fat_g
    return {
        "calories": float(profile.daily_calories - tracker.calories_consumed),
        "protein_g": float(profile.daily_protein_g - tracker.protein_consumed),
        "carbs_g": float(profile.daily_carbs_g - tracker.carbs_consumed),
        "fat_g": {
            "min": float(fat_min),
            "max": float(fat_max),
            "consumed": float(tracker.fat_consumed),
        },
    }


def _remove_assignment(
    daily_trackers: Dict[int, DailyTracker],
    weekly_tracker: WeeklyTracker,
    assignments: List[Assignment],
    assignment: Assignment,
    recipe: PlanningRecipe,
    is_workout: bool,
    schedule: List[List[MealSlot]],
    profile: PlanningUserProfile,
    completed_days: Optional[Set[int]] = None,
) -> None:
    """Remove one assignment from state. Weekly adjustments happen only at day granularity: when removing from a completed day, subtract full-day nutrition once and uncomplete the day."""
    day_index, slot_index, recipe_id = assignment.day_index, assignment.slot_index, assignment.recipe_id
    _debug_log("remove", day_index=day_index, slot_index=slot_index, recipe_id=recipe_id)
    tracker = daily_trackers[day_index]
    if assignment.variant_index > 0:
        nut = compute_variant_nutrition(recipe, assignment.variant_index, profile)
    else:
        nut = get_effective_nutrition(recipe, 0)
    micro = micronutrient_profile_to_dict(nut.micronutrients) if nut.micronutrients else {}
    slots_total = tracker.slots_total
    new_slots_assigned = tracker.slots_assigned - 1

    # Per-day contract: if this day was completed, subtract full-day totals from weekly once and uncomplete the day.
    if completed_days is not None and day_index in completed_days:
        _uncomplete_day(
            daily_trackers, weekly_tracker, day_index, schedule, profile, completed_days
        )

    if new_slots_assigned == 0:
        if day_index in daily_trackers:
            del daily_trackers[day_index]
    else:
        new_cal = tracker.calories_consumed - nut.calories
        new_pro = tracker.protein_consumed - nut.protein_g
        new_fat = tracker.fat_consumed - nut.fat_g
        new_carbs = tracker.carbs_consumed - nut.carbs_g
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
        assignments.remove(assignment)
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
    tau = tau_from_profile(profile)
    carryover = {}
    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        needed = cumulative_minimum_total(daily_rdi, days_done, tau)
        consumed = micro.get(n, 0.0)
        carryover[n] = max(0.0, needed - consumed)
    weekly_tracker.carryover_needs = carryover


# --- Daily validation (Section 6.5): imported from failure_attribution ---


def _macro_failure_details(
    *,
    day_index: Optional[int],
    reason: Optional[str],
    tracker: Optional[DailyTracker],
    profile: PlanningUserProfile,
) -> Dict[str, Any]:
    if tracker is None:
        deltas = {}
    else:
        fat_min, fat_max = profile.daily_fat_g
        if tracker.fat_consumed < fat_min:
            fat_delta = tracker.fat_consumed - fat_min
        elif tracker.fat_consumed > fat_max:
            fat_delta = tracker.fat_consumed - fat_max
        else:
            fat_delta = 0.0
        deltas = {
            "calories": float(tracker.calories_consumed - profile.daily_calories),
            "protein_g": float(tracker.protein_consumed - profile.daily_protein_g),
            "fat_g": float(fat_delta),
            "carbs_g": float(tracker.carbs_consumed - profile.daily_carbs_g),
        }
    date_value = f"day-{day_index + 1}" if day_index is not None else ""
    return {
        "date": date_value,
        "deltas": deltas,
        "constraint": str(reason or "exhaustion"),
    }


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
    tau = tau_from_profile(profile)
    if "sodium_mg" in micro and "sodium_mg" in tracked:
        daily_rdi = tracked["sodium_mg"]
        if daily_rdi > 0:
            total_sodium = micro.get("sodium_mg", 0.0)
            if total_sodium > sodium_weekly_advisory_max_mg(daily_rdi, D):
                sodium_adv = "Weekly sodium exceeds 200% of prorated RDI."
    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        consumed = micro.get(n, 0.0)
        if is_below_weekly_minimum(consumed, daily_rdi, D, tau):
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
    _normalize_nutrition_profile(weekly_tracker.weekly_totals)
    weekly_tracker.days_completed += 1
    weekly_tracker.days_remaining = D - weekly_tracker.days_completed
    _recompute_carryover(weekly_tracker, profile, D)


# --- Search state and candidate cache ---


@dataclass
class _CandidateCacheEntry:
    ordered: List[Tuple[str, int]]  # (recipe_id, variant_index) ordered by score then tie-break
    variant_nutritions: Dict[Tuple[str, int], NutritionProfile]  # for variant_index > 0
    pointer: int


def _decision_order(schedule: List[List[MealSlot]], D: int) -> List[Tuple[int, int]]:
    """List of (day_index, slot_index) in spec order."""
    out: List[Tuple[int, int]] = []
    for day_index in range(D):
        for slot_index in range(len(schedule[day_index])):
            out.append((day_index, slot_index))
    return out


def _tag_empty_failure(
    *,
    day_index: int,
    slot_index: int,
    required_tag_slugs: List[str],
    candidate_count_before: int,
    candidate_count_after: int,
    missing_tag: str,
    assignments: List[Assignment],
    daily_trackers: Dict[int, DailyTracker],
    attempt_count: int,
    backtrack_count: int = 0,
    stats_dict: Optional[Dict[str, Any]] = None,
) -> MealPlanResult:
    """Build FM-TAG-EMPTY result with stable report + failures[] shape."""
    report = ensure_report_failures(
        build_report_fm_tag_empty(
            day_index=day_index,
            slot_index=slot_index,
            required_tag_slugs=required_tag_slugs,
            candidate_count_before=candidate_count_before,
            candidate_count_after=candidate_count_after,
            reason="No planner candidates satisfy required tag slugs for this slot.",
        )
    )
    slot_id = f"day-{day_index + 1}-slot-{slot_index}"
    report["failures"] = [
        build_failure(
            code="FM-TAG-EMPTY",
            day_index=day_index,
            slot_index=slot_index,
            slot_id=slot_id,
            date="",
            details={
                "missing_tag": missing_tag,
                "recipe_count": int(candidate_count_after),
            },
        )
    ]
    return result_from_failure(
        "TC-2",
        "FM-TAG-EMPTY",
        report,
        list(assignments),
        dict(daily_trackers),
        attempt_count,
        backtrack_count,
        None,
        stats_dict,
    )


def _downstream_pin_conflict_result(
    *,
    day_index: int,
    schedule: List[List[MealSlot]],
    profile: PlanningUserProfile,
    tracker: DailyTracker,
    reason: Optional[str],
    assignments: List[Assignment],
    daily_trackers: Dict[int, DailyTracker],
    attempt_count: int,
    backtrack_count: int,
    stats_dict: Optional[Dict[str, Any]],
    termination_code: str = "TC-2",
) -> MealPlanResult:
    """FM-3 downstream: day-level pin conflict (fully pinned pre-search or attribution)."""
    pinned_slots = [
        {"slot_index": slot_idx, "recipe_id": rid}
        for slot_idx in range(len(schedule[day_index]))
        for rid in [_get_pinned_recipe_id(profile, day_index, slot_idx)]
        if rid is not None
    ]
    pinned_conflicts: List[Dict[str, Any]] = [{
        "day": day_index,
        "slot_index": None,
        "recipe_id": None,
        "violation_type": PIN_VIOLATION_DOWNSTREAM,
        "constraint": reason,
        "pinned_slots": pinned_slots,
    }]
    remaining = _remaining_budget_from_tracker(tracker, profile)
    report = build_report_fm3(
        pinned_conflicts=pinned_conflicts,
        remaining_budget=remaining,
    )
    return result_from_failure(
        termination_code,
        "FM-3",
        report,
        list(assignments),
        dict(daily_trackers),
        attempt_count,
        backtrack_count,
        None,
        stats_dict,
    )


def _attach_diagnosis(
    result: MealPlanResult,
    attribution: Attribution,
    search_exit: str,
) -> MealPlanResult:
    report = dict(result.report or {})
    report["diagnosis"] = {
        "status": attribution.status,
        "step": attribution.step,
        "nodes": attribution.nodes,
        "search_exit": search_exit,
        "reason": attribution.details.get("reason") if attribution.status == "inconclusive" else None,
        "code": attribution.code,
    }
    result.report = report
    return result


def _attributed_exhaustion_result(
    *,
    profile: PlanningUserProfile,
    recipe_pool: List[PlanningRecipe],
    schedule: List[List[MealSlot]],
    D: int,
    resolved_ul: Optional[UpperLimits],
    fallback: Callable[[], MealPlanResult],
    search_exit: str,
    closest_assignments: List[Assignment],
    closest_daily_trackers: Dict[int, DailyTracker],
    attempt_count: int,
    backtrack_count: int,
    sodium_advisory: Optional[str],
    stats_dict: Optional[Dict[str, Any]],
    initial_daily_trackers: Dict[int, DailyTracker],
    max_daily_achievable: Optional[Dict[str, Dict[int, float]]] = None,
) -> MealPlanResult:
    """Replace last-event codes on exhaustion with post-search attribution (C2a steps 2–3)."""
    attribution = diagnose_exhausted_search(
        profile, recipe_pool, schedule, D, resolved_ul,
    )
    if attribution.status != "attributed" or attribution.code is None:
        return _attach_diagnosis(fallback(), attribution, search_exit)

    code = attribution.code
    day_index = attribution.day_index

    if code == "FM-3":
        d = int(day_index if day_index is not None else 0)
        # Budget remaining after pins only (from initial state when available).
        pin_tracker = initial_daily_trackers.get(d)
        if pin_tracker is None:
            pin_tracker = DailyTracker(slots_total=len(schedule[d]))
        result = _downstream_pin_conflict_result(
            day_index=d,
            schedule=schedule,
            profile=profile,
            tracker=pin_tracker,
            reason="no_valid_combination",
            assignments=closest_assignments,
            daily_trackers=closest_daily_trackers,
            attempt_count=attempt_count,
            backtrack_count=backtrack_count,
            stats_dict=stats_dict,
            termination_code="TC-2",
        )
        return _attach_diagnosis(result, attribution, search_exit)

    if code == "FM-2":
        d = day_index
        tracker = (
            closest_daily_trackers.get(d)
            if d is not None
            else None
        )
        report = ensure_report_failures(
            build_report_fm2(
                d,
                "no_valid_combination",
                {},
                {},
                build_plan_snapshot(closest_assignments, closest_daily_trackers),
            )
        )
        report["failures"] = [
            build_failure(
                code="FM-MACRO-INFEASIBLE",
                details=_macro_failure_details(
                    day_index=d,
                    reason="no_valid_combination",
                    tracker=tracker,
                    profile=profile,
                ),
                slot_id="",
                date=f"day-{d + 1}" if d is not None else "",
            )
        ]
        result = result_from_failure(
            "TC-2",
            "FM-2",
            report,
            closest_assignments,
            closest_daily_trackers,
            attempt_count,
            backtrack_count,
            sodium_advisory,
            stats_dict,
        )
        return _attach_diagnosis(result, attribution, search_exit)

    if code == "FM-1":
        d = int(day_index if day_index is not None else 0)
        blocking = attribution.details.get("blocking_constraints") or [
            "HC-8: consecutive-day non-workout recipe reuse leaves no valid day sequence"
        ]
        # Day-level: every slot has candidates; HC-8 blocks the day sequence.
        report = build_report_fm1(d, None, blocking[0], eligible_recipe_count=None)
        failure = build_failure(
            code="FM-1",
            message="No sequence of valid days avoids repeating a recipe on consecutive days.",
            details={"blocking_constraints": list(blocking)},
            day_index=d,
            date=f"day-{d + 1}",
        )
        failure["fix_hint"] = HC8_SEQUENCE_FIX_HINT
        report["failures"] = [failure]
        result = result_from_failure(
            "TC-2",
            "FM-1",
            report,
            closest_assignments,
            closest_daily_trackers,
            attempt_count,
            backtrack_count,
            None,
            stats_dict,
        )
        return _attach_diagnosis(result, attribution, search_exit)

    if code == "FM-4":
        nut_keys = list(profile.micronutrient_targets.keys())
        weekly = weekly_tracker_from_best_micro(
            profile, D, attribution.details.get("best_micro"), nut_keys
        )
        report = build_report_fm4(weekly, profile, D, max_daily_achievable)
        result = result_from_failure(
            "TC-2",
            "FM-4",
            report,
            closest_assignments,
            closest_daily_trackers,
            attempt_count,
            backtrack_count,
            sodium_advisory,
            stats_dict,
            best_effort_plan=list(closest_assignments),
            best_effort_daily_trackers=dict(closest_daily_trackers),
            best_effort_weekly_tracker=weekly,
            plan_incomplete_reason="Did not meet weekly targets.",
        )
        return _attach_diagnosis(result, attribution, search_exit)

    return _attach_diagnosis(fallback(), attribution, search_exit)


def _static_slot_precheck(
    profile: PlanningUserProfile,
    recipe_pool: List[PlanningRecipe],
    schedule: List[List[MealSlot]],
    D: int,
    resolved_ul: Optional[UpperLimits],
    stats: Optional[SearchStats] = None,
) -> Optional[MealPlanResult]:
    """Attribution step 1: first non-pinned slot that fails HC-1/HC-3 or required tags.

    Runs before search so a tagged slot later in the day is diagnosed ahead of FC-5.
    """
    for day_index, slot_index in _decision_order(schedule, D):
        if _is_pinned(profile, day_index, slot_index):
            continue
        slot = schedule[day_index][slot_index]
        check = check_slot_statically(recipe_pool, day_index, slot, profile, resolved_ul)
        if check.code is None:
            continue
        if stats is not None and stats.enabled:
            stats._end_time = time.perf_counter()
            stats.total_attempts = 0
        if check.code == "FM-TAG-EMPTY":
            missing_tag = ", ".join(check.missing_tag_slugs)
            return _tag_empty_failure(
                day_index=day_index,
                slot_index=slot_index,
                required_tag_slugs=check.required_tag_slugs,
                candidate_count_before=check.eligible_count,
                candidate_count_after=0,
                missing_tag=missing_tag,
                assignments=[],
                daily_trackers={},
                attempt_count=0,
                backtrack_count=0,
                stats_dict={"attempts": 0, "backtracks": 0},
            )
        # FM-1
        constraint_detail = (
            "; ".join(check.blocking_constraints)
            if check.blocking_constraints
            else "HC-1/HC-3"
        )
        report = build_report_fm1(
            day_index,
            slot_index,
            constraint_detail,
            eligible_recipe_count=0,
        )
        return result_from_failure(
            "TC-2",
            "FM-1",
            report,
            [],
            {},
            0,
            0,
            None,
            {"attempts": 0, "backtracks": 0},
        )
    return None


def run_meal_plan_search(
    profile: PlanningUserProfile,
    recipe_pool: List[PlanningRecipe],
    D: int,
    resolved_ul: Optional[UpperLimits],
    attempt_limit: int = DEFAULT_ATTEMPT_LIMIT,
    stats: Optional[SearchStats] = None,
) -> MealPlanResult:
    """
    Run the full meal plan search. Returns MealPlanResult (Section 10, 11).
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
        report = build_report_fm3(
            pinned_conflicts=[{"day": 0, "slot_index": 0, "recipe_id": "", "violation_type": PIN_VIOLATION_DIRECT, "remaining_budget": {}}],
        )
        return result_from_failure("TC-3", "FM-3", report, [], {}, 0, 0, None, {"attempts": 0, "backtracks": 0})
    recipe_by_id = {r.id: r for r in recipe_pool}

    # Pinned pre-validation (Section 3.5)
    pin_result = validate_pinned_assignments(profile, recipe_by_id, D)
    if not pin_result.success:
        if stats is not None and stats.enabled:
            stats._end_time = time.perf_counter()
            stats.total_attempts = 0
        # pinned_conflicts[].day is 0-based (see _fm3_failures_from_report).
        day_0 = max((pin_result.failed_pin_day_1based or 1) - 1, 0)
        slot_0 = pin_result.failed_pin_slot_index if pin_result.failed_pin_slot_index is not None else 0
        rid = pin_result.failed_pin_recipe_id or ""
        report = build_report_fm3(
            pinned_conflicts=[{"day": day_0, "slot_index": slot_0, "recipe_id": rid, "violation_type": PIN_VIOLATION_DIRECT, "remaining_budget": {}}],
        )
        return result_from_failure("TC-3", "FM-3", report, [], {}, 0, 0, None, {"attempts": 0, "backtracks": 0})

    # Attribution step 1: static FM-1 / FM-TAG-EMPTY before search (C2b).
    # Diagnose any unfillable non-pinned slot ahead of FC-5 look-ahead.
    precheck_failure = _static_slot_precheck(
        profile, recipe_pool, schedule, D, resolved_ul, stats=stats,
    )
    if precheck_failure is not None:
        return precheck_failure

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

    # Fully pinned days: daily validation cannot depend on search decisions (pins use
    # variant 0). Fail early with FM-3 rather than searching earlier free days for nothing.
    for d in range(D):
        tracker = daily_trackers.get(d)
        if tracker is None or tracker.slots_assigned != tracker.slots_total:
            continue
        ok, reason = _daily_validation(d, tracker, profile, resolved_ul)
        if ok:
            continue
        if stats is not None and stats.enabled:
            stats._end_time = time.perf_counter()
            stats.total_attempts = 0
        return _downstream_pin_conflict_result(
            day_index=d,
            schedule=schedule,
            profile=profile,
            tracker=tracker,
            reason=reason,
            assignments=list(assignments),
            daily_trackers=dict(daily_trackers),
            attempt_count=0,
            backtrack_count=0,
            stats_dict={"attempts": 0, "backtracks": 0},
            termination_code="TC-3",
        )

    macro_bounds = precompute_macro_bounds(recipe_pool, max_slots=8)
    floor_bounds = precompute_micro_floor_bounds(
        profile, recipe_pool, schedule, D, resolved_ul
    )
    max_daily_achievable = floor_bounds_to_slot_mda(floor_bounds, schedule)

    if not check_structural_feasibility(profile, schedule, D, floor_bounds):
        if stats is not None and stats.enabled:
            stats._end_time = time.perf_counter()
            stats.total_attempts = 0
        zero_weekly = WeeklyTracker(
            weekly_totals=NutritionProfile(0.0, 0.0, 0.0, 0.0),
            days_completed=0,
            days_remaining=D,
            carryover_needs={n: 0.0 for n in profile.micronutrient_targets},
        )
        report = build_report_fm4(zero_weekly, profile, D, max_daily_achievable)
        return result_from_failure(
            "TC-2", "FM-4", report, list(assignments), dict(daily_trackers), 0, 0, None,
            {"attempts": 0, "backtracks": 0},
        )

    scalable_sources: Optional[Dict[str, List[str]]] = None
    if profile.enable_primary_carb_downscaling:
        # Fail fast on malformed or missing primary carb reference data.
        scalable_sources = load_scalable_carb_sources()

    order = _decision_order(schedule, D)
    cache: Dict[Tuple[int, int], _CandidateCacheEntry] = {}
    completed_days: Set[int] = set()
    attempt_count = 0
    backtrack_count = 0
    i = 0
    best_assignments: List[Assignment] = list(assignments)
    best_daily_trackers: Dict[int, DailyTracker] = dict(daily_trackers)
    sodium_advisory: Optional[str] = None
    _stats_dict: Optional[Dict[str, Any]] = None  # populated on exit when stats.enabled

    while i < len(order):
        day_index, slot_index = order[i]
        if attempt_count >= attempt_limit:
            if stats is not None and stats.enabled:
                stats._end_time = time.perf_counter()
                stats.total_attempts = attempt_count
            report = build_report_fm5(
                attempts=attempt_count,
                backtracks=backtrack_count,
                best_plan=build_plan_snapshot(best_assignments, best_daily_trackers),
                best_plan_violations={},
            )
            return result_from_failure("TC-3", "FM-5", report, best_assignments, best_daily_trackers, attempt_count, backtrack_count, sodium_advisory, _stats_dict)

        if stats is not None and stats.enabled and slot_index == 0:
            stats._day_starts[day_index] = time.perf_counter()

        # FC-4 at start of day d > 1 (Section 6, BT-4)
        if day_index > 0 and slot_index == 0:
            feas_state = FeasibilityStateView(
                daily_trackers=dict(daily_trackers),
                weekly_tracker=weekly_tracker,
                schedule=schedule,
            )
            if not check_fc4_cross_day_rdi(day_index, feas_state, profile, D, floor_bounds):
                # BT-4: backtrack
                target = _find_backtrack_target(order, i, cache, profile)
                if target is None:
                    if stats is not None and stats.enabled:
                        stats._end_time = time.perf_counter()
                        stats.total_attempts = attempt_count
                    report = build_report_fm4(weekly_tracker, profile, D, max_daily_achievable)
                    return result_from_failure("TC-2", "FM-4", report, list(assignments), dict(daily_trackers), attempt_count, backtrack_count, None, _stats_dict)
                if stats is not None and stats.enabled:
                    stats._backtrack_depths.append(i - target)
                backtrack_count += 1
                i, daily_trackers, weekly_tracker, assignments, cache = _unwind_to(
                    i, target, order, daily_trackers, weekly_tracker, assignments, cache,
                    completed_days, recipe_by_id, schedule, profile,
                )
                continue

        if _is_pinned(profile, day_index, slot_index):
            assigned_slots = {(a.day_index, a.slot_index) for a in assignments}
            if (day_index, slot_index) in assigned_slots:
                i += 1
                # Fall through to shared day-completion / end-of-plan tail.
            else:
                recipe_id = _get_pinned_recipe_id(profile, day_index, slot_index)
                recipe = recipe_by_id[recipe_id]
                day_slots = schedule[day_index]
                next_first = schedule[day_index + 1][0] if day_index + 1 < D else None
                act_ctx = activity_context_for_profile(
                    profile, day_index, day_slots[slot_index], slot_index, day_slots, next_first
                )
                is_w = is_workout_slot(act_ctx)
                _apply_assignment(daily_trackers, assignments, day_index, slot_index, recipe_id, recipe, is_w, schedule, variant_index=0)
                _validate_planner_state(daily_trackers, weekly_tracker, completed_days, D, schedule)
                i += 1
                attempt_count += 1
                if stats is not None and stats.enabled:
                    stats.attempts_per_slot[(day_index, slot_index)] = stats.attempts_per_slot.get((day_index, slot_index), 0) + 1
                    stats.attempts_per_day[day_index] = stats.attempts_per_day.get(day_index, 0) + 1
                if _update_best(assignments, daily_trackers, best_assignments, best_daily_trackers):
                    pass
                # Fall through to shared day-completion / end-of-plan tail.
        else:
            # Non-pinned: use cache or generate
            key = (day_index, slot_index)
            if key not in cache:
                cg = generate_candidates(
                    recipe_pool, day_index, slot_index,
                    dict(daily_trackers), copy.deepcopy(weekly_tracker), schedule,
                    profile, resolved_ul, macro_bounds,
                    scalable_sources=scalable_sources,
                )
                if cg.trigger_backtrack:
                    target = _find_backtrack_target(order, i, cache, profile)
                    if target is None:
                        if stats is not None and stats.enabled:
                            stats._end_time = time.perf_counter()
                            stats.total_attempts = attempt_count
                        if (
                            not cg.candidates
                            and cg.required_tag_filter_applied
                            and cg.candidate_count_before_required > 0
                            and cg.candidate_count_after_required == 0
                        ):
                            missing_tag = str(cg.required_tag_slugs[0]) if cg.required_tag_slugs else ""
                            return _tag_empty_failure(
                                day_index=day_index,
                                slot_index=slot_index,
                                required_tag_slugs=cg.required_tag_slugs,
                                candidate_count_before=cg.candidate_count_before_required,
                                candidate_count_after=cg.candidate_count_after_required,
                                missing_tag=missing_tag,
                                assignments=list(assignments),
                                daily_trackers=dict(daily_trackers),
                                attempt_count=attempt_count,
                                backtrack_count=backtrack_count,
                                stats_dict=_stats_dict,
                            )
                        # C2a: attribute empty-candidate / FC-5 exhaustion after search.
                        def _fallback_fm1_empty() -> MealPlanResult:
                            report = build_report_fm1(
                                day_index,
                                slot_index,
                                "Empty candidate set or FC-5",
                                eligible_recipe_count=len(cg.candidates),
                            )
                            return result_from_failure(
                                "TC-2",
                                "FM-1",
                                report,
                                list(assignments),
                                dict(daily_trackers),
                                attempt_count,
                                backtrack_count,
                                None,
                                _stats_dict,
                            )
                        return _attributed_exhaustion_result(
                            profile=profile,
                            recipe_pool=recipe_pool,
                            schedule=schedule,
                            D=D,
                            resolved_ul=resolved_ul,
                            fallback=_fallback_fm1_empty,
                            search_exit="FM-1",
                            closest_assignments=list(assignments),
                            closest_daily_trackers=dict(daily_trackers),
                            attempt_count=attempt_count,
                            backtrack_count=backtrack_count,
                            sodium_advisory=None,
                            stats_dict=_stats_dict,
                            initial_daily_trackers=initial.daily_trackers,
                            max_daily_achievable=max_daily_achievable,
                        )
                    if stats is not None and stats.enabled:
                        stats._backtrack_depths.append(i - target)
                    backtrack_count += 1
                    i, daily_trackers, weekly_tracker, assignments, cache = _unwind_to(
                        i, target, order, daily_trackers, weekly_tracker, assignments, cache,
                        completed_days, recipe_by_id, schedule, profile,
                    )
                    continue
                scored_triples: List[Tuple[str, int, PlanningRecipe, float]] = []
                for (rid, vi) in sorted(cg.candidates):
                    r = recipe_by_id[rid]
                    nut = cg.variant_nutritions.get((rid, vi)) or get_effective_nutrition(r, vi, None)
                    recipe_view = PlanningRecipe(
                        id=r.id,
                        name=r.name,
                        ingredients=r.ingredients,
                        cooking_time_minutes=r.cooking_time_minutes,
                        nutrition=nut,
                        primary_carb_contribution=r.primary_carb_contribution,
                        primary_carb_source=r.primary_carb_source,
                        canonical_tag_slugs=set(getattr(r, "canonical_tag_slugs", set()) or set()),
                        hard_eligible_tag_slugs=(
                            None
                            if getattr(r, "hard_eligible_tag_slugs", None) is None
                            else set(getattr(r, "hard_eligible_tag_slugs", set()) or set())
                        ),
                    )
                    # No meal-prep provenance is currently carried in planner runtime state.
                    # Keep this unset so scoring does not infer meal-prep exemptions from unrelated signals.
                    state_view = ScoringStateView(
                        daily_trackers=dict(daily_trackers),
                        weekly_tracker=weekly_tracker,
                        schedule=schedule,
                        meal_prep_recipe_ids=None,
                    )
                    sc = composite_score(recipe_view, day_index, slot_index, state_view, profile)
                    scored_triples.append((rid, vi, recipe_view, sc))
                ord_state = OrderingStateView(daily_trackers=dict(daily_trackers), weekly_tracker=weekly_tracker)
                slot = schedule[day_index][slot_index]
                ordered_triples = sorted(
                    scored_triples,
                    key=lambda t: ordering_key(
                        (t[2], t[3]),
                        ord_state,
                        profile,
                        day_index,
                        slot=slot,
                        tie_break_seed="phase7-search-seed",
                    ),
                )
                ordered_ids = [(rid, vi) for rid, vi, _rv, _sc in ordered_triples]
                if floor_bounds.tight and D > 1 and profile.micronutrient_targets:
                    today_prefix = _today_recipe_prefix(assignments, day_index, slot_index)
                    weekly_consumed = micronutrient_profile_to_dict(
                        getattr(weekly_tracker.weekly_totals, "micronutrients", None)
                    )
                    kept: List[Tuple[str, int]] = []
                    dropped = 0
                    for rid, vi in ordered_ids:
                        if candidate_passes_micro_floor(
                            rid,
                            day_index,
                            today_prefix,
                            weekly_consumed,
                            profile,
                            D,
                            floor_bounds,
                        ):
                            kept.append((rid, vi))
                        else:
                            dropped += 1
                    ordered_ids = kept
                    if stats is not None and stats.enabled and dropped:
                        stats.floor_bound_candidates_dropped += dropped
                cache[key] = _CandidateCacheEntry(
                    ordered=ordered_ids,
                    variant_nutritions=cg.variant_nutritions,
                    pointer=0,
                )
                if stats is not None and stats.enabled:
                    stats.branching_factors[key] = len(cache[key].ordered)

            entry = cache[key]
            if entry.pointer >= len(entry.ordered):
                target = _find_backtrack_target(order, i, cache, profile)
                if target is None:
                    if stats is not None and stats.enabled:
                        stats._end_time = time.perf_counter()
                        stats.total_attempts = attempt_count

                    def _fallback_fm2_pointer() -> MealPlanResult:
                        report = ensure_report_failures(
                            build_report_fm2(
                                None,
                                "exhaustion",
                                {},
                                {},
                                build_plan_snapshot(best_assignments, best_daily_trackers),
                            )
                        )
                        failure_day_index = max(best_daily_trackers) if best_daily_trackers else None
                        failure_tracker = (
                            best_daily_trackers.get(failure_day_index)
                            if failure_day_index is not None
                            else None
                        )
                        report["failures"] = [
                            build_failure(
                                code="FM-MACRO-INFEASIBLE",
                                details=_macro_failure_details(
                                    day_index=failure_day_index,
                                    reason="exhaustion",
                                    tracker=failure_tracker,
                                    profile=profile,
                                ),
                                slot_id="",
                                date=f"day-{failure_day_index + 1}" if failure_day_index is not None else "",
                            )
                        ]
                        return result_from_failure(
                            "TC-2",
                            "FM-2",
                            report,
                            best_assignments,
                            best_daily_trackers,
                            attempt_count,
                            backtrack_count,
                            sodium_advisory,
                            _stats_dict,
                        )

                    return _attributed_exhaustion_result(
                        profile=profile,
                        recipe_pool=recipe_pool,
                        schedule=schedule,
                        D=D,
                        resolved_ul=resolved_ul,
                        fallback=_fallback_fm2_pointer,
                        search_exit="FM-2",
                        closest_assignments=best_assignments,
                        closest_daily_trackers=best_daily_trackers,
                        attempt_count=attempt_count,
                        backtrack_count=backtrack_count,
                        sodium_advisory=sodium_advisory,
                        stats_dict=_stats_dict,
                        initial_daily_trackers=initial.daily_trackers,
                        max_daily_achievable=max_daily_achievable,
                    )
                if stats is not None and stats.enabled:
                    stats._backtrack_depths.append(i - target)
                backtrack_count += 1
                i, daily_trackers, weekly_tracker, assignments, cache = _unwind_to(
                    i, target, order, daily_trackers, weekly_tracker, assignments, cache,
                    completed_days, recipe_by_id, schedule, profile,
                )
                continue

            recipe_id, variant_index = entry.ordered[entry.pointer]
            recipe = recipe_by_id[recipe_id]
            variant_nutrition = entry.variant_nutritions.get((recipe_id, variant_index)) if variant_index > 0 else None
            day_slots = schedule[day_index]
            next_first = schedule[day_index + 1][0] if day_index + 1 < D else None
            act_ctx = activity_context_for_profile(
                profile, day_index, day_slots[slot_index], slot_index, day_slots, next_first
            )
            is_w = is_workout_slot(act_ctx)
            _apply_assignment(
                daily_trackers, assignments, day_index, slot_index, recipe_id, recipe, is_w, schedule,
                variant_index=variant_index,
                variant_nutrition=variant_nutrition,
            )
            _validate_planner_state(daily_trackers, weekly_tracker, completed_days, D, schedule)
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
        if (
            tracker is not None
            and tracker.slots_assigned == tracker.slots_total
            and day_index not in completed_days
        ):
            ok, reason = _daily_validation(day_index, tracker, profile, resolved_ul)
            if not ok:
                target = _find_backtrack_target(order, i, cache, profile)
                if target is None:
                    if stats is not None and stats.enabled:
                        stats._end_time = time.perf_counter()
                        stats.total_attempts = attempt_count

                    def _fallback_fm2_day() -> MealPlanResult:
                        macro_v: Dict[str, Any] = {}
                        ul_v: Dict[str, Any] = {}
                        if reason:
                            if (reason or "").startswith("UL:"):
                                ul_v[reason] = "exceeded"
                            else:
                                macro_v["constraint_detail"] = reason
                                macro_v["calories_consumed"] = tracker.calories_consumed
                                macro_v["protein_consumed"] = tracker.protein_consumed
                                macro_v["fat_consumed"] = tracker.fat_consumed
                                macro_v["carbs_consumed"] = tracker.carbs_consumed
                        report = ensure_report_failures(
                            build_report_fm2(
                                day_index,
                                reason,
                                macro_v,
                                ul_v,
                                build_plan_snapshot(assignments, daily_trackers),
                            )
                        )
                        report["failures"] = [
                            build_failure(
                                code="FM-MACRO-INFEASIBLE",
                                details=_macro_failure_details(
                                    day_index=day_index,
                                    reason=reason,
                                    tracker=tracker,
                                    profile=profile,
                                ),
                                slot_id="",
                                date=f"day-{day_index + 1}",
                            )
                        ]
                        return result_from_failure(
                            "TC-2",
                            "FM-2",
                            report,
                            list(assignments),
                            dict(daily_trackers),
                            attempt_count,
                            backtrack_count,
                            None,
                            _stats_dict,
                        )

                    return _attributed_exhaustion_result(
                        profile=profile,
                        recipe_pool=recipe_pool,
                        schedule=schedule,
                        D=D,
                        resolved_ul=resolved_ul,
                        fallback=_fallback_fm2_day,
                        search_exit="FM-2",
                        closest_assignments=list(assignments),
                        closest_daily_trackers=dict(daily_trackers),
                        attempt_count=attempt_count,
                        backtrack_count=backtrack_count,
                        sodium_advisory=None,
                        stats_dict=_stats_dict,
                        initial_daily_trackers=initial.daily_trackers,
                        max_daily_achievable=max_daily_achievable,
                    )
                if stats is not None and stats.enabled:
                    stats._backtrack_depths.append(i - target)
                backtrack_count += 1
                # origin = slot that completed the day (we already did i += 1 after assignment)
                origin_i = i - 1 if i > 0 else 0
                i, daily_trackers, weekly_tracker, assignments, cache = _unwind_to(
                    origin_i, target, order, daily_trackers, weekly_tracker, assignments, cache,
                    completed_days, recipe_by_id, schedule, profile,
                )
                continue
            if stats is not None and stats.enabled:
                stats.day_runtimes[day_index] = time.perf_counter() - stats._day_starts.get(day_index, stats._start_time or 0)
            _update_weekly_after_day(daily_trackers, weekly_tracker, day_index, schedule, profile, D)
            completed_days.add(day_index)
            _debug_log("day_complete", day_index=day_index)
            _validate_planner_state(daily_trackers, weekly_tracker, completed_days, D, schedule)

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
                    _stats_dict = {"attempts": attempt_count, "backtracks": backtrack_count} if stats and stats.enabled else None
                    return result_from_success(list(assignments), dict(daily_trackers), weekly_tracker, profile, D, "TC-4", _stats_dict)
                ok, reason, sodium_adv = _weekly_validation(D, weekly_tracker, profile)
                if sodium_adv:
                    sodium_advisory = sodium_adv
                if not ok:
                    target = _find_backtrack_target(order, i, cache, profile)
                    if target is None:
                        if stats is not None and stats.enabled:
                            stats._end_time = time.perf_counter()
                            stats.total_attempts = attempt_count
                        report = build_report_fm4(weekly_tracker, profile, D, max_daily_achievable)
                        return result_from_failure(
                            "TC-2", "FM-4", report, list(assignments), dict(daily_trackers),
                            attempt_count, backtrack_count, sodium_advisory, _stats_dict,
                            best_effort_plan=list(assignments),
                            best_effort_daily_trackers=dict(daily_trackers),
                            best_effort_weekly_tracker=weekly_tracker,
                            plan_incomplete_reason="Did not meet weekly targets.",
                        )
                    if stats is not None and stats.enabled:
                        stats._backtrack_depths.append(i - target)
                    backtrack_count += 1
                    # origin = slot that triggered failure (we already did i += 1 after assigning last slot)
                    origin_i = i - 1 if i > 0 else 0
                    i, daily_trackers, weekly_tracker, assignments, cache = _unwind_to(
                        origin_i, target, order, daily_trackers, weekly_tracker, assignments, cache,
                        completed_days, recipe_by_id, schedule, profile,
                    )
                    continue
                if stats is not None and stats.enabled:
                    stats._end_time = time.perf_counter()
                    stats.total_attempts = attempt_count
                _stats_dict = {"attempts": attempt_count, "backtracks": backtrack_count} if stats and stats.enabled else None
                return result_from_success(list(assignments), dict(daily_trackers), weekly_tracker, profile, D, "TC-1", _stats_dict)

    if stats is not None and stats.enabled:
        stats._end_time = time.perf_counter()
        stats.total_attempts = attempt_count
    _stats_dict = {"attempts": attempt_count, "backtracks": backtrack_count} if stats and stats.enabled else None

    def _fallback_fm2_fallthrough() -> MealPlanResult:
        report = ensure_report_failures(
            build_report_fm2(
                None,
                "exhaustion",
                {},
                {},
                build_plan_snapshot(best_assignments, best_daily_trackers),
            )
        )
        failure_day_index = max(best_daily_trackers) if best_daily_trackers else None
        failure_tracker = (
            best_daily_trackers.get(failure_day_index)
            if failure_day_index is not None
            else None
        )
        report["failures"] = [
            build_failure(
                code="FM-MACRO-INFEASIBLE",
                details=_macro_failure_details(
                    day_index=failure_day_index,
                    reason="exhaustion",
                    tracker=failure_tracker,
                    profile=profile,
                ),
                slot_id="",
                date=f"day-{failure_day_index + 1}" if failure_day_index is not None else "",
            )
        ]
        return result_from_failure(
            "TC-2",
            "FM-2",
            report,
            best_assignments,
            best_daily_trackers,
            attempt_count,
            backtrack_count,
            sodium_advisory,
            _stats_dict,
        )

    return _attributed_exhaustion_result(
        profile=profile,
        recipe_pool=recipe_pool,
        schedule=schedule,
        D=D,
        resolved_ul=resolved_ul,
        fallback=_fallback_fm2_fallthrough,
        search_exit="FM-2",
        closest_assignments=best_assignments,
        closest_daily_trackers=best_daily_trackers,
        attempt_count=attempt_count,
        backtrack_count=backtrack_count,
        sodium_advisory=sodium_advisory,
        stats_dict=_stats_dict,
        initial_daily_trackers=initial.daily_trackers,
        max_daily_achievable=max_daily_achievable,
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


def _today_recipe_prefix(
    assignments: List[Assignment],
    day_index: int,
    slot_index: int,
) -> Tuple[str, ...]:
    """Recipe IDs already assigned on this day for slots 0..slot_index-1, in slot order."""
    by_slot = {
        a.slot_index: a.recipe_id
        for a in assignments
        if a.day_index == day_index and a.slot_index < slot_index
    }
    return tuple(by_slot[s] for s in range(slot_index))


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
    origin_i: int,
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
    """Unwind state to target_i.

    Origin is the index where backtrack triggered. Boundary crossing = origin_day > target_day.
    Cache policy: ALWAYS preserve target slot cache entry (and pointer), invalidate only later slots.
    Pointer advances only at selection time in main loop.
    """
    n = len(order)
    if origin_i >= n:
        origin_i = n - 1
    if origin_i < 0:
        origin_i = 0
    assert 0 <= origin_i < len(order), "origin_i must be a valid decision index"
    target_day, target_slot = order[target_i]
    origin_day, origin_slot = order[origin_i]
    crossed_day_boundary = origin_day > target_day
    cache_policy = "preserve_target_invalidate_later" if crossed_day_boundary else "keep_target_pointer"
    _debug_log(
        "backtrack",
        origin_i=origin_i,
        target_i=target_i,
        origin_day=origin_day,
        origin_slot=origin_slot,
        target_day=target_day,
        target_slot=target_slot,
        crossed_day_boundary=crossed_day_boundary,
        cache_policy=cache_policy,
    )
    to_remove_list: List[Assignment] = [
        a for a in assignments
        if (a.day_index, a.slot_index) >= (target_day, target_slot) and not _is_pinned(profile, a.day_index, a.slot_index)
    ]
    to_remove_list.sort(key=lambda a: (a.day_index, a.slot_index), reverse=True)

    for a in to_remove_list:
        recipe = recipe_by_id.get(a.recipe_id)
        if recipe is None:
            continue
        day_slots = schedule[a.day_index]
        next_first = schedule[a.day_index + 1][0] if a.day_index + 1 < len(schedule) else None
        act_ctx = activity_context_for_profile(
            profile, a.day_index, day_slots[a.slot_index], a.slot_index, day_slots, next_first
        )
        is_w = is_workout_slot(act_ctx)
        _remove_assignment(
            daily_trackers, weekly_tracker, assignments, a, recipe, is_w, schedule, profile, completed_days
        )

    # Fully pinned completed days past the target have no free assignments to remove,
    # so _remove_assignment never uncompletes them. Drop them from weekly totals here.
    for d in sorted((x for x in completed_days if x > target_day), reverse=True):
        _uncomplete_day(
            daily_trackers, weekly_tracker, d, schedule, profile, completed_days
        )

    cache_cleaned: Dict[Tuple[int, int], _CandidateCacheEntry] = {}
    target_key = (target_day, target_slot)
    for (d, s), entry in cache.items():
        if (d, s) < (target_day, target_slot):
            cache_cleaned[(d, s)] = entry
        elif (d, s) == (target_day, target_slot):
            # ALWAYS preserve target slot cache (and pointer), even across day boundaries.
            cache_cleaned[(d, s)] = entry
        # (d, s) > (target_day, target_slot): drop (invalidate)

    # Defensive assertion: the backtrack target must still have untried candidates.
    target_entry = cache_cleaned.get(target_key)
    if target_entry is not None:
        _debug_log(
            "backtrack_target_cache",
            target_day=target_day,
            target_slot=target_slot,
            pointer=target_entry.pointer,
            remaining=max(0, len(target_entry.ordered) - target_entry.pointer),
        )
        assert target_entry.pointer < len(
            target_entry.ordered
        ), "backtrack target must have untried candidates"

    _validate_planner_state(daily_trackers, weekly_tracker, completed_days, len(schedule), schedule)
    return target_i, daily_trackers, weekly_tracker, assignments, cache_cleaned
