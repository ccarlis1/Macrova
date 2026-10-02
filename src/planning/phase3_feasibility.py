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
from src.planning.micronutrient_policy import tau_from_profile, weekly_minimum_total

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
    """Precompute loose top-M max_daily_achievable(nutrient, slot_count). Spec Section 5 FC-4 fallback.

    For each nutrient n and slot_count M: sum of the M largest values of n across distinct recipes.
    Ignores calorie/macro/eligibility constraints. Prefer MicroFloorBounds when enumeration succeeds.
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


# Node budget for day enumeration used to build tight floor bounds (same order as C2a).
FLOOR_ENUM_NODE_LIMIT = 500_000


@dataclass(frozen=True)
class MicroFloorBounds:
    """Per-day micronutrient ceilings for FC-4 / structural / per-slot floor pruning.

    When ``tight`` is True, ``day_max`` / ``prefix_max`` come from enumerating each day's
    valid meal combinations. When False, ``day_max`` is the loose top-M sum and
    ``prefix_max`` is empty (per-slot pruning disabled).
    """

    tight: bool
    day_max: List[Dict[str, float]]  # per day_index -> nutrient -> max
    suffix_max: List[Dict[str, float]]  # length D+1; suffix_max[d] = sum day_max[d..]
    prefix_max: List[Dict[Tuple[str, ...], Dict[str, float]]]  # per day; empty when not tight


def micro_floor_bounds_from_slot_mda(
    mda: Dict[str, Dict[int, float]],
    schedule: List[List[MealSlot]],
    D: int,
    nutrient_names: Optional[List[str]] = None,
) -> MicroFloorBounds:
    """Build loose (tight=False) MicroFloorBounds from a slot-count MDA table."""
    names = list(nutrient_names) if nutrient_names is not None else list(mda.keys())
    day_max: List[Dict[str, float]] = []
    for d in range(D):
        m = len(schedule[d]) if d < len(schedule) else 0
        day_max.append({n: float(mda.get(n, {}).get(m, 0.0)) for n in names})
    suffix_max = _build_suffix_max(day_max, names, D)
    return MicroFloorBounds(
        tight=False,
        day_max=day_max,
        suffix_max=suffix_max,
        prefix_max=[{} for _ in range(D)],
    )


def floor_bounds_to_slot_mda(
    bounds: MicroFloorBounds,
    schedule: List[List[MealSlot]],
) -> Dict[str, Dict[int, float]]:
    """Project day_max onto a (nutrient -> slot_count -> max) table for FM-4 reports."""
    result: Dict[str, Dict[int, float]] = {}
    for d, day in enumerate(bounds.day_max):
        m = len(schedule[d]) if d < len(schedule) else 0
        for n, val in day.items():
            by_slots = result.setdefault(n, {})
            prev = by_slots.get(m)
            if prev is None or val > prev:
                by_slots[m] = val
    return result


def _build_suffix_max(
    day_max: List[Dict[str, float]],
    nutrient_names: List[str],
    D: int,
) -> List[Dict[str, float]]:
    suffix: List[Dict[str, float]] = [{} for _ in range(D + 1)]
    for d in range(D - 1, -1, -1):
        cur = day_max[d] if d < len(day_max) else {}
        nxt = suffix[d + 1]
        suffix[d] = {n: float(cur.get(n, 0.0)) + float(nxt.get(n, 0.0)) for n in nutrient_names}
    return suffix


def precompute_micro_floor_bounds(
    profile: PlanningUserProfile,
    recipe_pool: List[PlanningRecipe],
    schedule: List[List[MealSlot]],
    D: int,
    resolved_ul: Optional[UpperLimits],
    *,
    node_limit: int = FLOOR_ENUM_NODE_LIMIT,
) -> MicroFloorBounds:
    """Precompute per-day / prefix micronutrient ceilings for FC-4 and per-slot pruning.

    Prefers enumeration of valid day combinations (tight). Falls back to the loose
    top-M sum when primary-carb downscaling is on, when no nutrients are tracked,
    or when enumeration hits its node/solution cap.
    """
    tracked = dict(profile.micronutrient_targets or {})
    nutrient_names = list(tracked.keys())
    slot_counts: Set[int] = {len(schedule[d]) for d in range(D)} if D > 0 else set()

    def _loose() -> MicroFloorBounds:
        names = nutrient_names or list(MicronutrientProfile.__dataclass_fields__.keys())
        mda = precompute_max_daily_achievable(recipe_pool, names, slot_counts or {1})
        return micro_floor_bounds_from_slot_mda(mda, schedule, D, names)

    if not tracked or D <= 0:
        return _loose()
    if getattr(profile, "enable_primary_carb_downscaling", False):
        return _loose()

    # Local import avoids a module-level cycle with failure_attribution helpers.
    from src.planning.failure_attribution import (
        _day_signature,
        _enumerate_day,
        _micro_of_combo,
    )

    recipe_by_id = {r.id: r for r in recipe_pool}
    day_cache: Dict[str, Any] = {}
    nodes = 0
    day_solutions: List[List[Tuple[str, ...]]] = []

    for d in range(D):
        sig = _day_signature(schedule, d, profile, ignore_pins=False) + "|sols"
        if sig not in day_cache:
            day_cache[sig] = _enumerate_day(
                recipe_pool,
                recipe_by_id,
                profile,
                schedule,
                d,
                resolved_ul,
                ignore_pins=False,
                want_solutions=True,
                node_limit=node_limit,
                nodes_so_far=nodes,
            )
            nodes += day_cache[sig].nodes
        r = day_cache[sig]
        if r.budget_hit or r.capped or nodes > node_limit:
            return _loose()
        day_solutions.append(list(r.solutions))

    day_max: List[Dict[str, float]] = [{n: 0.0 for n in nutrient_names} for _ in range(D)]
    prefix_max: List[Dict[Tuple[str, ...], Dict[str, float]]] = [{} for _ in range(D)]

    for d, sols in enumerate(day_solutions):
        for combo in sols:
            micros = _micro_of_combo(recipe_by_id, combo, nutrient_names)
            for i, n in enumerate(nutrient_names):
                if micros[i] > day_max[d][n]:
                    day_max[d][n] = micros[i]
            for k in range(1, len(combo) + 1):
                pref = combo[:k]
                cur = prefix_max[d].get(pref)
                if cur is None:
                    prefix_max[d][pref] = {n: micros[i] for i, n in enumerate(nutrient_names)}
                else:
                    for i, n in enumerate(nutrient_names):
                        if micros[i] > cur[n]:
                            cur[n] = micros[i]

    suffix_max = _build_suffix_max(day_max, nutrient_names, D)
    return MicroFloorBounds(
        tight=True,
        day_max=day_max,
        suffix_max=suffix_max,
        prefix_max=prefix_max,
    )


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


# --- Structural feasibility (pre-search) ---


def check_structural_feasibility(
    profile: PlanningUserProfile,
    schedule: List[List[MealSlot]],
    D: int,
    floor_bounds: MicroFloorBounds | Dict[str, Dict[int, float]],
) -> bool:
    """Return False if horizon is structurally impossible for any tracked micronutrient.

    For each tracked nutrient n: if suffix_max[0][n] (sum of per-day maxima) is below
    τ × daily_rdi × D, the plan cannot meet the weekly micronutrient floor (FM-4 pre-fail).

    ``floor_bounds`` may be a MicroFloorBounds or a legacy slot-count MDA dict.
    """
    tracked = profile.micronutrient_targets
    if not tracked:
        return True
    if isinstance(floor_bounds, dict):
        floor_bounds = micro_floor_bounds_from_slot_mda(floor_bounds, schedule, D, list(tracked.keys()))
    tau = tau_from_profile(profile)
    horizon = floor_bounds.suffix_max[0] if floor_bounds.suffix_max else {}
    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        total_needed = weekly_minimum_total(daily_rdi, D, tau)
        if float(horizon.get(n, 0.0)) < total_needed:
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
    floor_bounds: MicroFloorBounds | Dict[str, Dict[int, float]],
) -> bool:
    """FC-4: At start of day d (d>0), if consumed + suffix_max[d] cannot reach the floor, reject.

    Spec Section 5. ``floor_bounds`` may be MicroFloorBounds or a legacy slot-count MDA dict.
    """
    if day_index <= 0:
        return True
    w = state.weekly_tracker
    if w.days_remaining <= 0:
        return True
    tracked = user_profile.micronutrient_targets
    if not tracked:
        return True
    if day_index >= len(state.schedule):
        return True
    if isinstance(floor_bounds, dict):
        floor_bounds = micro_floor_bounds_from_slot_mda(
            floor_bounds, state.schedule, D, list(tracked.keys())
        )
    cumulative = _weekly_totals_micro_dict(w.weekly_totals)
    tau = tau_from_profile(user_profile)
    rest = floor_bounds.suffix_max[day_index] if day_index < len(floor_bounds.suffix_max) else {}

    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        floor = weekly_minimum_total(daily_rdi, D, tau)
        consumed = cumulative.get(n, 0.0)
        if consumed + float(rest.get(n, 0.0)) < floor - 1e-9:
            return False
    return True


def candidate_passes_micro_floor(
    recipe_id: str,
    day_index: int,
    today_prefix: Tuple[str, ...],
    weekly_consumed: Dict[str, float],
    profile: PlanningUserProfile,
    D: int,
    floor_bounds: MicroFloorBounds,
) -> bool:
    """Per-slot soundness check: prefix completion + remaining days can still hit floors.

    Only meaningful when ``floor_bounds.tight`` and D > 1 with tracked micronutrients.
    A missing prefix key means no valid day completes that prefix — reject.
    """
    tracked = profile.micronutrient_targets
    if not tracked or not floor_bounds.tight or D <= 1:
        return True
    if day_index < 0 or day_index >= len(floor_bounds.prefix_max):
        return True
    key = today_prefix + (recipe_id,)
    pmax = floor_bounds.prefix_max[day_index].get(key)
    if pmax is None:
        return False
    tau = tau_from_profile(profile)
    rem = (
        floor_bounds.suffix_max[day_index + 1]
        if day_index + 1 < len(floor_bounds.suffix_max)
        else {}
    )
    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        floor = weekly_minimum_total(daily_rdi, D, tau)
        if (
            float(weekly_consumed.get(n, 0.0))
            + float(pmax.get(n, 0.0))
            + float(rem.get(n, 0.0))
            < floor - 1e-9
        ):
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
