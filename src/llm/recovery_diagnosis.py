"""Deterministic diagnosis of a planner failure: can new recipes help, and with what properties?

This module is the gate in front of the LLM. It never calls the LLM and never writes.
Given the planner result, the planning profile and the pool the planner saw, it returns
either a :class:`GapSpec` (what a useful recipe must satisfy) or an
:class:`UnrecoverableReason` (why no recipe can change the outcome).

It also provides :func:`feasibility_signal`, a cheap deterministic measure in the
dimension named by the gap, used to decide whether a recovery attempt made progress.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from src.data_layer.models import MicronutrientProfile
from src.llm.recovery_types import GapSpec, UnrecoverableReason
from src.planning.micronutrient_policy import tau_from_profile, weekly_minimum_total
from src.planning.phase0_models import MealSlot, PlanningRecipe, PlanningUserProfile
from src.planning.phase1_state import _recipe_contains_excluded_ingredient
from src.planning.phase3_feasibility import precompute_max_daily_achievable
from src.planning.phase10_reporting import MealPlanResult
from src.planning.slot_attributes import cooking_time_max

MACRO_TOLERANCE = 0.10
_NEVER_RECOVERABLE = {"FM-3", "FM-BATCH-CONFLICT"}
_MAX_LIST = 80


def _slot_required(slot: MealSlot) -> List[str]:
    return [str(s).strip().lower() for s in (getattr(slot, "required_tag_slugs", None) or []) if str(s).strip()]


def _recipe_hard_tags(recipe: PlanningRecipe) -> set:
    hard = getattr(recipe, "hard_eligible_tag_slugs", None)
    if hard is None:
        return {str(s).strip().lower() for s in (getattr(recipe, "canonical_tag_slugs", set()) or set())}
    return {str(s).strip().lower() for s in (hard or set())}


def _passes_slot_hard_filters(recipe: PlanningRecipe, slot: MealSlot, profile: PlanningUserProfile) -> bool:
    if _recipe_contains_excluded_ingredient(recipe, profile.excluded_ingredients):
        return False
    cap = cooking_time_max(slot.busyness_level)
    if cap is not None and recipe.cooking_time_minutes > cap:
        return False
    req = _slot_required(slot)
    if req and not set(req).issubset(_recipe_hard_tags(recipe)):
        return False
    return True


def slot_candidate_counts(profile: PlanningUserProfile, pool: Sequence[PlanningRecipe]) -> Dict[str, int]:
    """Per-slot count of pool recipes passing HC-1 (exclusions), HC-3 (cook cap), HC-9 (required tags)."""
    out: Dict[str, int] = {}
    for d, day in enumerate(profile.schedule):
        for s, slot in enumerate(day):
            out[f"{d}:{s}"] = sum(1 for r in pool if _passes_slot_hard_filters(r, slot, profile))
    return out


def impossible_targets(profile: PlanningUserProfile) -> Optional[Dict[str, Any]]:
    """Return details when the macro targets cannot be met by any set of recipes."""
    kcal = float(profile.daily_calories)
    protein = float(profile.daily_protein_g)
    fat_min, fat_max = (float(profile.daily_fat_g[0]), float(profile.daily_fat_g[1]))
    carbs = float(profile.daily_carbs_g)
    problems: Dict[str, Any] = {}
    if kcal <= 0:
        problems["calories"] = "non-positive daily calorie target"
    if carbs <= 0:
        problems["carbs"] = f"derived daily carbs {carbs:.1f} g is not positive"
    if fat_min > fat_max:
        problems["fat_range"] = f"fat min {fat_min:.1f} g exceeds fat max {fat_max:.1f} g"
    if protein * 4.0 + fat_min * 9.0 > kcal * (1.0 + MACRO_TOLERANCE):
        problems["protein_fat_vs_calories"] = "protein and minimum fat alone exceed the calorie window"
    ceiling = getattr(profile, "max_daily_calories", None)
    if ceiling is not None and float(ceiling) < kcal * (1.0 - MACRO_TOLERANCE):
        problems["calorie_ceiling"] = f"ceiling {ceiling} is below the lower edge of the calorie window ({kcal * (1.0 - MACRO_TOLERANCE):.0f})"
    return problems or None


def nutrient_gaps(profile: PlanningUserProfile, pool: Sequence[PlanningRecipe], days: int) -> Dict[str, Dict[str, float]]:
    """Per tracked nutrient: required horizon total vs the maximum the pool could reach."""
    tracked = profile.micronutrient_targets or {}
    if not tracked:
        return {}
    slot_counts = {len(day) for day in profile.schedule}
    mda = precompute_max_daily_achievable(list(pool), list(tracked.keys()), slot_counts)
    tau = tau_from_profile(profile)
    out: Dict[str, Dict[str, float]] = {}
    for n, rdi in tracked.items():
        if rdi <= 0:
            continue
        required = weekly_minimum_total(rdi, days, tau)
        reachable = sum(mda.get(n, {}).get(len(profile.schedule[d]), 0.0) for d in range(days))
        if reachable < required:
            out[n] = {"required": required, "reachable": reachable, "deficit": required - reachable}
    return out


def diagnose(
    result: MealPlanResult,
    profile: PlanningUserProfile,
    pool: Sequence[PlanningRecipe],
    days: int,
    *,
    known_ingredient_vocabulary: Optional[Sequence[str]] = None,
) -> Union[GapSpec, UnrecoverableReason]:
    """Decide deterministically whether adding recipes could change the planner outcome."""
    fm = result.failure_mode or ""
    if fm in _NEVER_RECOVERABLE:
        return UnrecoverableReason(code="PIN_OR_BATCH_CONFLICT", message=f"{fm}: a pinned or batch-locked slot conflicts with the rules; adding recipes cannot change it.")
    if fm == "FM-TAG-EMPTY":
        return UnrecoverableReason(code="REQUIRED_TAG_UNHELD", message="A slot requires a tag no recipe holds; generated recipes cannot carry approved tags.", details=dict(result.report or {}).get("tag_empty_slots", [{}])[0] if (result.report or {}).get("tag_empty_slots") else {})

    problems = impossible_targets(profile)
    if problems:
        return UnrecoverableReason(code="IMPOSSIBLE_TARGETS", message="The macro targets cannot be met by any combination of recipes.", details=problems)

    if len(pool) == 0:
        return UnrecoverableReason(code="EMPTY_POOL", message="The recipe pool is empty (a filter or selection removed every recipe); recipes generated now would bypass that filter.")

    counts = slot_candidate_counts(profile, pool)
    # Required-tag check: any slot whose required tags are held by no recipe at all.
    for d, day in enumerate(profile.schedule):
        for s, slot in enumerate(day):
            req = _slot_required(slot)
            if req and not any(set(req).issubset(_recipe_hard_tags(r)) for r in pool):
                return UnrecoverableReason(code="REQUIRED_TAG_UNHELD", message=f"Slot day {d} slot {s} requires tags {req} that no recipe in the pool holds; generated recipes enter untagged.", details={"day_index": d, "slot_index": s, "required_tag_slugs": req})

    if fm == "FM-5":
        return UnrecoverableReason(code="SEARCH_BUDGET", message="The search hit its attempt limit without proving infeasibility; this is a search-budget problem, not an inventory gap.", details={"attempts": (result.stats or {}).get("attempts")})

    slots_per_day = len(profile.schedule[0]) if profile.schedule else 1
    per_meal_kcal = float(profile.daily_calories) / max(1, slots_per_day)
    per_meal_protein = float(profile.daily_protein_g) / max(1, slots_per_day)
    per_meal_fat_max = float(profile.daily_fat_g[1]) / max(1, slots_per_day)
    per_meal_carbs = float(profile.daily_carbs_g) / max(1, slots_per_day)
    names = sorted({r.name for r in pool})[:_MAX_LIST]
    vocab = sorted(set(known_ingredient_vocabulary or []))[:_MAX_LIST * 2]
    base = dict(
        failure_mode=fm, days=days, meals_per_day=slots_per_day,
        per_meal_calories=round(per_meal_kcal, 1), per_meal_protein_g=round(per_meal_protein, 1),
        per_meal_fat_g_max=round(per_meal_fat_max, 1), per_meal_carbs_g=round(per_meal_carbs, 1),
        excluded_ingredients=sorted({str(x).strip().lower() for x in profile.excluded_ingredients if str(x).strip()}),
        existing_recipe_names=names, known_ingredient_vocabulary=vocab,
    )

    empty_slots = [k for k, v in counts.items() if v == 0]
    if empty_slots:
        slots = [[int(a), int(b)] for a, b in (k.split(":") for k in empty_slots)]
        caps = [cooking_time_max(profile.schedule[d][s].busyness_level) for d, s in slots]
        cap = min((c for c in caps if c is not None), default=None)
        return GapSpec(kind="candidate_gap", cook_time_cap_minutes=cap, slots=slots,
                       explanation=f"{len(slots)} slot(s) have no recipe passing exclusions, cook-time cap and required tags.", **base)

    distinct = len({r.id for r in pool})
    if distinct < slots_per_day:
        return GapSpec(kind="uniqueness_gap", slots=[], explanation=f"Only {distinct} distinct recipes for {slots_per_day} slots per day (same-day uniqueness).", **base)

    gaps = nutrient_gaps(profile, pool, days)
    if fm == "FM-4" or gaps:
        need = {n: round(g["deficit"] / max(1, days), 3) for n, g in gaps.items()}
        if not need:
            # Planner reported FM-4 but the pool ceiling is not the cause: combinations, not inventory.
            deficient = (result.report or {}).get("deficient_nutrients", []) or []
            need = {str(d.get("nutrient")): round(float(d.get("deficit", 0.0)) / max(1, days), 3) for d in deficient if isinstance(d, dict) and d.get("nutrient")}
        return GapSpec(kind="nutrient_gap", nutrient_min_per_recipe=need,
                       explanation="Tracked micronutrient floors exceed what the pool can reach; a useful recipe must contribute at least the listed amount per serving.", **base)

    tight_cap = min((cooking_time_max(sl.busyness_level) or 10**6 for day in profile.schedule for sl in day), default=None)
    return GapSpec(kind="macro_gap", cook_time_cap_minutes=None if tight_cap in (None, 10**6) else tight_cap,
                   explanation="Every slot has candidates but no combination meets the daily macro window; a useful recipe lands near the per-meal targets.", **base)


def feasibility_signal(profile: PlanningUserProfile, pool: Sequence[PlanningRecipe], gap: GapSpec, days: int) -> Dict[str, Any]:
    """Cheap deterministic measure of how close the pool is to closing the gap."""
    counts = slot_candidate_counts(profile, pool)
    sig: Dict[str, Any] = {"distinct_recipes": len({r.id for r in pool})}
    if gap.kind == "candidate_gap":
        keys = [f"{d}:{s}" for d, s in gap.slots] or list(counts.keys())
        sig["min_gap_slot_candidates"] = min((counts[k] for k in keys if k in counts), default=0)
    elif gap.kind == "nutrient_gap":
        tracked = profile.micronutrient_targets or {}
        slot_counts = {len(day) for day in profile.schedule}
        mda = precompute_max_daily_achievable(list(pool), list(tracked.keys()), slot_counts)
        sig["reachable"] = {n: round(sum(mda.get(n, {}).get(len(profile.schedule[d]), 0.0) for d in range(days)), 3) for n in gap.nutrient_min_per_recipe}
    elif gap.kind == "macro_gap":
        target = gap.per_meal_calories or 0.0
        sig["recipes_near_per_meal_target"] = sum(1 for r in pool if target and 0.5 * target <= r.nutrition.calories <= 1.5 * target)
    return sig


def improved(before: Dict[str, Any], after: Dict[str, Any], gap: GapSpec) -> bool:
    """True when the signal moved in the direction the gap needs."""
    if gap.kind == "candidate_gap":
        return after.get("min_gap_slot_candidates", 0) > before.get("min_gap_slot_candidates", 0)
    if gap.kind == "nutrient_gap":
        b, a = before.get("reachable", {}), after.get("reachable", {})
        return any(a.get(n, 0.0) > b.get(n, 0.0) for n in gap.nutrient_min_per_recipe)
    if gap.kind == "macro_gap":
        return after.get("recipes_near_per_meal_target", 0) > before.get("recipes_near_per_meal_target", 0)
    return after.get("distinct_recipes", 0) > before.get("distinct_recipes", 0)
