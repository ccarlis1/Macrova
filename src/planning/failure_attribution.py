"""Post-search failure attribution (C2a). Spec §11 steps 2–3.

When search ends exhausted without hitting the attempt budget (FM-5), diagnose
the structural cause: day-level macro/pin infeasibility (FM-2 / FM-3) or
across-days HC-8 / micronutrient-floor infeasibility (FM-1 / FM-4).

Pure function of planner inputs. Does not mutate search state. Deterministic:
day-major order, sorted recipe IDs, node-count budget (never wall-clock).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.data_layer.models import MicronutrientProfile, NutritionProfile, UpperLimits
from src.data_layer.upper_limits import validate_daily_upper_limits

from src.planning.micronutrient_policy import (
    is_below_weekly_minimum,
    tau_from_profile,
    weekly_minimum_total,
)
from src.planning.phase0_models import (
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    WeeklyTracker,
    micronutrient_profile_to_dict,
)
from src.planning.phase6_candidates import check_slot_statically
from src.planning.slot_attributes import activity_context_for_profile, is_workout_slot

# Shared with phase7_search (imported as alias there). Spec §6.5 daily windows.
DAILY_TOLERANCE = 0.10

# Node budget for post-search diagnosis. Counts slot nodes (step 2) and
# day-combination nodes (step 3). Tuned above worst-case C2a / HC-8 scenarios.
DIAGNOSIS_NODE_LIMIT = 500_000

# Cap on materialized day solutions before treating diagnosis as inconclusive.
_DAY_SOLUTION_CAP = 60_000


@dataclass(frozen=True)
class Attribution:
    """Result of post-search diagnosis. Spec §11 steps 2–3."""

    status: str  # "attributed" | "inconclusive"
    code: Optional[str]  # "FM-2" | "FM-3" | "FM-4" | "FM-1" | None when inconclusive
    day_index: Optional[int]
    details: Dict[str, Any] = field(default_factory=dict)
    nodes: int = 0
    step: Optional[str] = None  # "day_check" | "across_days" | None


def daily_tracker_to_micro_profile(tracker: DailyTracker) -> MicronutrientProfile:
    """Build MicronutrientProfile from a day's consumed micros."""
    valid = list(MicronutrientProfile.__dataclass_fields__.keys())
    kwargs = {k: tracker.micronutrients_consumed.get(k, 0.0) for k in valid}
    return MicronutrientProfile(**kwargs)


def daily_validation(
    day_index: int,
    tracker: DailyTracker,
    profile: PlanningUserProfile,
    resolved_ul: Optional[UpperLimits],
) -> Tuple[bool, Optional[str]]:
    """Daily calorie/macro/ceiling/UL check. Spec §6.5. Shared with phase7 search."""
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
        micro_profile = daily_tracker_to_micro_profile(tracker)
        violations = validate_daily_upper_limits(micro_profile, resolved_ul)
        if violations:
            return False, f"UL:{violations[0].nutrient}"
    return True, None


# --- Internal day / multi-day enumeration ---


@dataclass
class _DayEnumResult:
    feasible: bool
    solutions: List[Tuple[str, ...]] = field(default_factory=list)
    count: int = 0
    capped: bool = False
    empty_slot: Optional[int] = None  # slot_index when a free slot has no eligible recipes
    nodes: int = 0
    budget_hit: bool = False


def _pin_for(profile: PlanningUserProfile, day_index: int, slot_index: int) -> Optional[str]:
    # pinned_assignments keys are (day_1based, slot_index_0based).
    return profile.pinned_assignments.get((day_index + 1, slot_index))


def _day_pins(
    profile: PlanningUserProfile,
    day_index: int,
) -> Dict[Tuple[int, int], str]:
    """Return this day's pins keyed as (day_0based, slot_index) for reporting."""
    day_1based = day_index + 1
    return {
        (day_index, s): rid
        for (d, s), rid in profile.pinned_assignments.items()
        if d == day_1based
    }


def _workout_slots_for_day(
    profile: PlanningUserProfile,
    schedule: List[List[MealSlot]],
    day_index: int,
) -> Set[int]:
    day_slots = schedule[day_index]
    next_first = schedule[day_index + 1][0] if day_index + 1 < len(schedule) else None
    out: Set[int] = set()
    for s_idx, slot in enumerate(day_slots):
        act = activity_context_for_profile(profile, day_index, slot, s_idx, day_slots, next_first)
        if is_workout_slot(act):
            out.add(s_idx)
    return out


def _slot_options(
    recipe_pool: List[PlanningRecipe],
    profile: PlanningUserProfile,
    schedule: List[List[MealSlot]],
    day_index: int,
    resolved_ul: Optional[UpperLimits],
    *,
    ignore_pins: bool = False,
) -> Tuple[List[List[str]], Optional[int]]:
    """Per-slot eligible recipe ID lists. Returns (elig, empty_slot_index)."""
    day_slots = schedule[day_index]
    elig: List[List[str]] = []
    for s_idx, slot in enumerate(day_slots):
        pin = None if ignore_pins else _pin_for(profile, day_index, s_idx)
        if pin is not None:
            elig.append([pin])
            continue
        check = check_slot_statically(recipe_pool, day_index, slot, profile, resolved_ul)
        if check.code is not None or not check.eligible_recipe_ids:
            return elig, s_idx
        elig.append(list(check.eligible_recipe_ids))
    return elig, None


def _vec4(recipe: PlanningRecipe) -> Tuple[float, float, float, float]:
    n = recipe.nutrition
    return (n.calories, n.protein_g, n.carbs_g, n.fat_g)


def _tracker_from_combo(
    recipe_by_id: Dict[str, PlanningRecipe],
    combo: Tuple[str, ...],
    schedule: List[List[MealSlot]],
    day_index: int,
    profile: PlanningUserProfile,
) -> DailyTracker:
    day_slots = schedule[day_index]
    next_first = schedule[day_index + 1][0] if day_index + 1 < len(schedule) else None
    cal = pro = fat = carbs = 0.0
    micro: Dict[str, float] = {}
    used: Set[str] = set()
    non_workout: Set[str] = set()
    for s_idx, rid in enumerate(combo):
        recipe = recipe_by_id[rid]
        nut = recipe.nutrition
        cal += nut.calories
        pro += nut.protein_g
        fat += nut.fat_g
        carbs += nut.carbs_g
        if nut.micronutrients is not None:
            for k, v in micronutrient_profile_to_dict(nut.micronutrients).items():
                micro[k] = micro.get(k, 0.0) + v
        used.add(rid)
        act = activity_context_for_profile(
            profile, day_index, day_slots[s_idx], s_idx, day_slots, next_first
        )
        if not is_workout_slot(act):
            non_workout.add(rid)
    return DailyTracker(
        calories_consumed=cal,
        protein_consumed=pro,
        fat_consumed=fat,
        carbs_consumed=carbs,
        micronutrients_consumed=micro,
        used_recipe_ids=used,
        non_workout_recipe_ids=non_workout,
        slots_assigned=len(combo),
        slots_total=len(day_slots),
    )


def _enumerate_day(
    recipe_pool: List[PlanningRecipe],
    recipe_by_id: Dict[str, PlanningRecipe],
    profile: PlanningUserProfile,
    schedule: List[List[MealSlot]],
    day_index: int,
    resolved_ul: Optional[UpperLimits],
    *,
    ignore_pins: bool = False,
    want_solutions: bool = False,
    node_limit: int,
    nodes_so_far: int,
) -> _DayEnumResult:
    """DFS over a day's slot options. Prunes with suffix min/max (oracle-style)."""
    res = _DayEnumResult(feasible=False)
    elig, empty = _slot_options(
        recipe_pool, profile, schedule, day_index, resolved_ul, ignore_pins=ignore_pins
    )
    if empty is not None:
        res.empty_slot = empty
        return res

    n = len(elig)
    if n == 0:
        return res

    vecs = [[_vec4(recipe_by_id[rid]) for rid in e] for e in elig]
    suffix_min = [(0.0,) * 4 for _ in range(n + 1)]
    suffix_max = [(0.0,) * 4 for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        mn = tuple(min(v[k] for v in vecs[i]) for k in range(4))
        mx = tuple(max(v[k] for v in vecs[i]) for k in range(4))
        suffix_min[i] = tuple(a + b for a, b in zip(suffix_min[i + 1], mn))
        suffix_max[i] = tuple(a + b for a, b in zip(suffix_max[i + 1], mx))

    kcal_t = float(profile.daily_calories)
    p_t = float(profile.daily_protein_g)
    c_t = float(profile.daily_carbs_g)
    f_lo, f_hi = profile.daily_fat_g
    lo = (kcal_t * (1 - DAILY_TOLERANCE), p_t * (1 - DAILY_TOLERANCE), c_t * (1 - DAILY_TOLERANCE), f_lo)
    hi_list = [kcal_t * (1 + DAILY_TOLERANCE), p_t * (1 + DAILY_TOLERANCE), c_t * (1 + DAILY_TOLERANCE), f_hi]
    if profile.max_daily_calories is not None:
        hi_list[0] = min(hi_list[0], float(profile.max_daily_calories))
    hi = tuple(hi_list)

    chosen: List[str] = []
    nodes = nodes_so_far
    l0, l1, l2, l3 = lo
    h0, h1, h2, h3 = hi

    def rec(i: int, a0: float, a1: float, a2: float, a3: float) -> bool:
        """Return True to stop (found one / capped / budget)."""
        nonlocal nodes
        if i == n:
            combo = tuple(chosen)
            tracker = _tracker_from_combo(recipe_by_id, combo, schedule, day_index, profile)
            ok, _ = daily_validation(day_index, tracker, profile, resolved_ul)
            if not ok:
                return False
            res.feasible = True
            res.count += 1
            if want_solutions:
                res.solutions.append(combo)
                if res.count >= _DAY_SOLUTION_CAP:
                    res.capped = True
                    return True
                return False
            return True  # existence only

        smn = suffix_min[i + 1]
        smx = suffix_max[i + 1]
        for rid, v in zip(elig[i], vecs[i]):
            nodes += 1
            if nodes > node_limit:
                res.budget_hit = True
                return True
            if rid in chosen:
                continue
            b0 = a0 + v[0]
            if b0 + smn[0] > h0 or b0 + smx[0] < l0:
                continue
            b1 = a1 + v[1]
            if b1 + smn[1] > h1 or b1 + smx[1] < l1:
                continue
            b2 = a2 + v[2]
            if b2 + smn[2] > h2 or b2 + smx[2] < l2:
                continue
            b3 = a3 + v[3]
            if b3 + smn[3] > h3 or b3 + smx[3] < l3:
                continue
            chosen.append(rid)
            stop = rec(i + 1, b0, b1, b2, b3)
            chosen.pop()
            if stop:
                return True
        return False

    rec(0, 0.0, 0.0, 0.0, 0.0)
    res.nodes = nodes - nodes_so_far
    return res


def _day_signature(
    schedule: List[List[MealSlot]],
    day_index: int,
    profile: PlanningUserProfile,
    *,
    ignore_pins: bool,
) -> str:
    day_slots = schedule[day_index]
    meal_sig = tuple(
        (
            slot.busyness_level,
            tuple(getattr(slot, "required_tag_slugs", None) or []),
            slot.time,
            slot.meal_type,
        )
        for slot in day_slots
    )
    if ignore_pins:
        pins_sig: Tuple[Any, ...] = ()
    else:
        day_1based = day_index + 1
        pins_sig = tuple(
            sorted(
                (s, rid)
                for (d, s), rid in profile.pinned_assignments.items()
                if d == day_1based
            )
        )
    return repr((meal_sig, pins_sig, ignore_pins))


def _micro_of_combo(
    recipe_by_id: Dict[str, PlanningRecipe],
    combo: Tuple[str, ...],
    nutrient_keys: List[str],
) -> Tuple[float, ...]:
    totals = [0.0] * len(nutrient_keys)
    for rid in combo:
        nut = recipe_by_id[rid].nutrition
        if nut.micronutrients is None:
            continue
        md = micronutrient_profile_to_dict(nut.micronutrients)
        for i, k in enumerate(nutrient_keys):
            totals[i] += md.get(k, 0.0)
    return tuple(totals)


def _nonworkout_ids(
    combo: Tuple[str, ...],
    workout_slots: Set[int],
) -> Set[str]:
    return {rid for s, rid in enumerate(combo) if s not in workout_slots}


def _across_days(
    day_solutions: List[List[Tuple[str, ...]]],
    workout_slots_by_day: List[Set[int]],
    recipe_by_id: Dict[str, PlanningRecipe],
    profile: PlanningUserProfile,
    D: int,
    *,
    check_floors: bool,
    node_limit: int,
    nodes_so_far: int,
    fallback_plan: Optional[List[Tuple[str, ...]]] = None,
) -> Tuple[str, Optional[Dict[str, Any]], int, bool]:
    """Pass A (HC-8) or Pass B (HC-8 + floors).

    Returns (outcome, details, nodes_used, budget_hit) where outcome is one of:
    "found", "hc8_blocked", "floor_blocked". On "found" without floors,
    details["plan"] holds the HC-8-valid sequence. fallback_plan (Pass A's
    sequence) supplies the reported micro totals when Pass B prunes every
    sequence before completing one.
    """
    tracked = dict(profile.micronutrient_targets or {})
    nut_keys = list(tracked) if check_floors else []
    tau = tau_from_profile(profile)
    floors = [weekly_minimum_total(tracked[k], D, tau) for k in nut_keys] if nut_keys else []

    sols_with_micro: List[List[Tuple[Tuple[str, ...], Tuple[float, ...]]]] = []
    maxes: List[Tuple[float, ...]] = []
    for sols in day_solutions:
        if nut_keys:
            packed = [(s, _micro_of_combo(recipe_by_id, s, nut_keys)) for s in sols]
            # Deterministic order: prefer higher micro density (oracle-style).
            daily = [max(f / D, 1e-9) for f in floors]
            packed.sort(key=lambda x: -sum(m / d for m, d in zip(x[1], daily)))
            sols_with_micro.append(packed)
            maxes.append(tuple(max(m[k] for _, m in packed) for k in range(len(nut_keys))))
        else:
            sols_with_micro.append([(s, ()) for s in sols])

    zero = tuple(0.0 for _ in nut_keys)
    suffix_max = [zero for _ in range(D + 1)]
    if nut_keys:
        for d in range(D - 1, -1, -1):
            suffix_max[d] = tuple(a + b for a, b in zip(suffix_max[d + 1], maxes[d]))
        short = {
            k: {
                "best_achievable": round(suffix_max[0][i], 2),
                "min_req": round(floors[i], 2),
            }
            for i, k in enumerate(nut_keys)
            if suffix_max[0][i] < floors[i] - 1e-9
        }
        if short:
            return "floor_blocked", {"micronutrient_shortfall": short, "best_micro": suffix_max[0]}, 0, False

    nodes = nodes_so_far
    plan: List[Tuple[str, ...]] = []
    found_plan: List[Tuple[str, ...]] = []
    first_blocked_day: Optional[int] = None
    # Closest complete HC-8-valid sequence under floors (smallest relative shortfall).
    best_acc: Optional[Tuple[float, ...]] = None
    best_short = float("inf")

    def rec(d: int, acc: Tuple[float, ...]) -> Optional[bool]:
        """True = found; False = exhausted; None = budget."""
        nonlocal nodes, first_blocked_day, best_acc, best_short
        if d == D:
            if not nut_keys:
                found_plan[:] = plan
                return True
            if all(a >= f - 1e-9 for a, f in zip(acc, floors)):
                return True
            short = sum(max(0.0, f - a) / max(f, 1e-9) for a, f in zip(acc, floors))
            if short < best_short:
                best_short, best_acc = short, acc
            return False

        prev_nw = _nonworkout_ids(plan[-1], workout_slots_by_day[d - 1]) if d > 0 else set()
        extended = False
        for sol, m in sols_with_micro[d]:
            nodes += 1
            if nodes > node_limit:
                return None
            if prev_nw and (_nonworkout_ids(sol, workout_slots_by_day[d]) & prev_nw):
                continue
            a = tuple(x + y for x, y in zip(acc, m)) if nut_keys else acc
            if nut_keys and any(
                x + y < f - 1e-9 for x, y, f in zip(a, suffix_max[d + 1], floors)
            ):
                continue
            extended = True
            plan.append(sol)
            outcome = rec(d + 1, a)
            plan.pop()
            if outcome is True or outcome is None:
                return outcome
        if not extended and first_blocked_day is None:
            first_blocked_day = d
        return False

    result = rec(0, zero)
    used = nodes - nodes_so_far
    if result is None:
        return "hc8_blocked", {}, used, True
    if result is True:
        return "found", {"plan": list(found_plan)}, used, False
    if check_floors and nut_keys:
        # Every complete HC-8-valid sequence misses a floor, so report the totals
        # of an actual sequence (not per-day maxima, which can all pass).
        if best_acc is None:
            best_acc = zero
            for combo in fallback_plan or []:
                m = _micro_of_combo(recipe_by_id, combo, nut_keys)
                best_acc = tuple(a + b for a, b in zip(best_acc, m))
        short = {
            k: {
                "best_achievable": round(best_acc[i], 2),
                "min_req": round(floors[i], 2),
            }
            for i, k in enumerate(nut_keys)
            if best_acc[i] < floors[i] - 1e-9
        }
        return "floor_blocked", {"micronutrient_shortfall": short, "best_micro": best_acc}, used, False
    return (
        "hc8_blocked",
        {"day_index": first_blocked_day if first_blocked_day is not None else 0},
        used,
        False,
    )


def diagnose_exhausted_search(
    profile: PlanningUserProfile,
    recipe_pool: List[PlanningRecipe],
    schedule: List[List[MealSlot]],
    D: int,
    resolved_ul: Optional[UpperLimits],
    *,
    node_limit: int = DIAGNOSIS_NODE_LIMIT,
) -> Attribution:
    """Attribute an exhausted search failure. Spec §11 steps 2–3.

    Returns Attribution with status "attributed" (code set) or "inconclusive"
    (code None; caller keeps the last-event failure).
    """
    recipe_by_id = {r.id: r for r in recipe_pool}
    nodes = 0
    day_cache: Dict[str, _DayEnumResult] = {}
    day_results: List[_DayEnumResult] = []

    # --- Step 2: day check ---
    for d in range(D):
        sig = _day_signature(schedule, d, profile, ignore_pins=False)
        if sig not in day_cache:
            day_cache[sig] = _enumerate_day(
                recipe_pool,
                recipe_by_id,
                profile,
                schedule,
                d,
                resolved_ul,
                ignore_pins=False,
                want_solutions=False,
                node_limit=node_limit,
                nodes_so_far=nodes,
            )
            nodes += day_cache[sig].nodes
        r = day_cache[sig]
        day_results.append(r)
        if r.budget_hit or nodes > node_limit:
            return Attribution(
                status="inconclusive",
                code=None,
                day_index=d,
                details={"reason": "node_budget"},
                nodes=nodes,
                step="day_check",
            )
        if not r.feasible:
            # First infeasible day.
            if getattr(profile, "enable_primary_carb_downscaling", False):
                return Attribution(
                    status="inconclusive",
                    code=None,
                    day_index=d,
                    details={"reason": "carb_downscaling"},
                    nodes=nodes,
                    step="day_check",
                )
            day_pins = _day_pins(profile, d)
            code = "FM-2"
            if day_pins:
                unpinned = _enumerate_day(
                    recipe_pool,
                    recipe_by_id,
                    profile,
                    schedule,
                    d,
                    resolved_ul,
                    ignore_pins=True,
                    want_solutions=False,
                    node_limit=node_limit,
                    nodes_so_far=nodes,
                )
                nodes += unpinned.nodes
                if unpinned.budget_hit or nodes > node_limit:
                    return Attribution(
                        status="inconclusive",
                        code=None,
                        day_index=d,
                        details={"reason": "node_budget"},
                        nodes=nodes,
                        step="day_check",
                    )
                if unpinned.feasible:
                    code = "FM-3"
            return Attribution(
                status="attributed",
                code=code,
                day_index=d,
                details={
                    "infeasible_day": d,
                    "has_pins": bool(day_pins),
                    "pinned_slots": [
                        {"slot_index": s, "recipe_id": rid}
                        for (_, s), rid in sorted(day_pins.items())
                    ],
                },
                nodes=nodes,
                step="day_check",
            )

    # All days have at least one valid combination. Re-enumerate collecting solutions.
    collected: List[List[Tuple[str, ...]]] = []
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
        if r.budget_hit or nodes > node_limit or r.capped:
            return Attribution(
                status="inconclusive",
                code=None,
                day_index=d,
                details={"reason": "node_budget" if (r.budget_hit or nodes > node_limit) else "day_capped"},
                nodes=nodes,
                step="across_days",
            )
        collected.append(list(r.solutions))

    workout_slots = [_workout_slots_for_day(profile, schedule, d) for d in range(D)]
    tracked = dict(profile.micronutrient_targets or {})
    need_floors = bool(tracked) and D > 1

    # --- Step 3 Pass A: HC-8 only ---
    outcome, details, used, budget_hit = _across_days(
        collected,
        workout_slots,
        recipe_by_id,
        profile,
        D,
        check_floors=False,
        node_limit=node_limit,
        nodes_so_far=nodes,
    )
    nodes += used
    if budget_hit:
        return Attribution(
            status="inconclusive",
            code=None,
            day_index=None,
            details={"reason": "node_budget"},
            nodes=nodes,
            step="across_days",
        )
    if outcome == "hc8_blocked":
        day_idx = int(details.get("day_index", 0))
        return Attribution(
            status="attributed",
            code="FM-1",
            day_index=day_idx,
            details={
                "reason": "HC-8 consecutive-day repetition leaves no valid day sequence",
                "blocking_constraints": [
                    "HC-8: consecutive-day non-workout recipe reuse leaves no valid day sequence"
                ],
            },
            nodes=nodes,
            step="across_days",
        )
    if outcome == "found" and not need_floors:
        return Attribution(
            status="inconclusive",
            code=None,
            day_index=None,
            details={"reason": "plan_exists"},
            nodes=nodes,
            step="across_days",
        )

    # --- Step 3 Pass B: floors ---
    if need_floors:
        outcome_b, details_b, used_b, budget_b = _across_days(
            collected,
            workout_slots,
            recipe_by_id,
            profile,
            D,
            check_floors=True,
            node_limit=node_limit,
            nodes_so_far=nodes,
            fallback_plan=details.get("plan"),
        )
        nodes += used_b
        if budget_b:
            return Attribution(
                status="inconclusive",
                code=None,
                day_index=None,
                details={"reason": "node_budget"},
                nodes=nodes,
                step="across_days",
            )
        if outcome_b == "floor_blocked":
            return Attribution(
                status="attributed",
                code="FM-4",
                day_index=None,
                details=details_b,
                nodes=nodes,
                step="across_days",
            )
        if outcome_b == "found":
            return Attribution(
                status="inconclusive",
                code=None,
                day_index=None,
                details={"reason": "plan_exists"},
                nodes=nodes,
                step="across_days",
            )
        # HC-8 blocked under floors path shouldn't happen after Pass A found a sequence,
        # but treat as FM-1 if it does.
        if outcome_b == "hc8_blocked":
            return Attribution(
                status="attributed",
                code="FM-1",
                day_index=int(details_b.get("day_index", 0)),
                details={
                    "reason": "HC-8 consecutive-day repetition leaves no valid day sequence",
                    "blocking_constraints": [
                        "HC-8: consecutive-day non-workout recipe reuse leaves no valid day sequence"
                    ],
                },
                nodes=nodes,
                step="across_days",
            )

    return Attribution(
        status="inconclusive",
        code=None,
        day_index=None,
        details={"reason": "plan_exists"},
        nodes=nodes,
        step="across_days",
    )


def weekly_tracker_from_best_micro(
    profile: PlanningUserProfile,
    D: int,
    best_micro: Optional[Tuple[float, ...]],
    nutrient_keys: List[str],
) -> WeeklyTracker:
    """Build a WeeklyTracker whose micros reflect best achievable totals (for FM-4 reports)."""
    micro_dict: Dict[str, float] = {}
    if best_micro is not None:
        for k, v in zip(nutrient_keys, best_micro):
            micro_dict[k] = float(v)
    valid = list(MicronutrientProfile.__dataclass_fields__.keys())
    kwargs = {k: micro_dict.get(k, 0.0) for k in valid}
    micro = MicronutrientProfile(**kwargs)
    return WeeklyTracker(
        weekly_totals=NutritionProfile(0.0, 0.0, 0.0, 0.0, micronutrients=micro),
        days_completed=D,
        days_remaining=0,
        carryover_needs={},
    )


def is_below_any_weekly_floor(
    weekly_tracker: WeeklyTracker,
    profile: PlanningUserProfile,
    D: int,
) -> bool:
    """True if any tracked micronutrient is below τ × RDI × D."""
    tracked = profile.micronutrient_targets or {}
    if not tracked:
        return False
    tau = tau_from_profile(profile)
    micro = micronutrient_profile_to_dict(
        getattr(weekly_tracker.weekly_totals, "micronutrients", None)
    )
    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        if is_below_weekly_minimum(micro.get(n, 0.0), daily_rdi, D, tau):
            return True
    return False
