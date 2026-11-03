"""Plain-language explanations for planner failures.

Adds ``explanation``, ``fix`` and ``cause`` to each ``report.failures[]`` entry and a
``report.failure_cause`` block, so clients (Flutter, the MCP server) can show a
failure without knowing FM codes.

The table is keyed by (failure code, cause). The cause is the deterministic
recovery diagnosis (``GapSpec.kind`` or ``UnrecoverableReason.code``), refined for
FM-1 by the blocking constraint and for FM-3 by pin vs batch. Unmatched failures
fall back to the planner's ``message`` and ``fix_hint`` (``fix_hint_for_code``).

Reporting only: nothing here changes planner behavior or calls an LLM.
"""

from __future__ import annotations

import re
from typing import AbstractSet, Any, Dict, List, Optional, Sequence, Tuple, Union

from src.llm.recovery_diagnosis import diagnose
from src.llm.recovery_types import GapSpec, UnrecoverableReason
from src.planning.phase0_models import PlanningRecipe, PlanningUserProfile
from src.planning.phase10_reporting import MealPlanResult, fix_hint_for_code

Diagnosis = Union[GapSpec, UnrecoverableReason]

# Causes that explain every failure the same way, whatever the FM code.
_PLAN_WIDE_CAUSES = {"IMPOSSIBLE_TARGETS", "EMPTY_POOL"}

# FM-2 is the failure_mode name; failures[] carries FM-MACRO-INFEASIBLE.
_CODE_ALIASES = {"FM-2": "FM-MACRO-INFEASIBLE"}

_MACRO_EXPLANATION = "No combination of the available recipes meets your daily calorie and macro targets for {where}."

# (code, cause) -> (explanation template, fix template). A cause of None is the code's default.
_TABLE: Dict[Tuple[str, Optional[str]], Tuple[str, str]] = {
    ("*", "IMPOSSIBLE_TARGETS"): (
        "Your daily targets can't all be met at the same time: {problems}.",
        "Change the targets so they fit together, for example raise calories or lower the protein or minimum fat target.",
    ),
    ("*", "EMPTY_POOL"): (
        "No recipes were available to plan with.",
        "Add recipes, or check that your filters and excluded ingredients don't remove all of them.",
    ),
    ("FM-1", "HC-1"): (
        "{Where} has no recipe without your excluded ingredients.",
        "Add a recipe for {where} that avoids them, or remove an exclusion.",
    ),
    ("FM-1", "HC-3"): (
        "{Where} has no recipe that can be cooked {cap_clause}.",
        "Add a quicker recipe, or allow more cooking time for {where}.",
    ),
    ("FM-1", "HC-8"): (
        "There aren't enough different recipes to avoid serving the same meal on back-to-back days (first blocked at {where}).",
        "Add more recipes, plan fewer days, or relax the meal constraints.",
    ),
    ("FM-1", None): (
        "{Where} has no recipe that fits its constraints.",
        "Add a recipe that fits {where}, or relax its constraints.",
    ),
    ("FM-MACRO-INFEASIBLE", "macro_gap"): (
        _MACRO_EXPLANATION,
        "Add recipes close to {per_meal_calories} kcal and {per_meal_protein_g} g protein per meal, or widen the macro targets.",
    ),
    ("FM-MACRO-INFEASIBLE", "uniqueness_gap"): (
        "There are fewer different recipes than meals per day, and a recipe can't repeat within a day.",
        "Add more recipes, or plan fewer meals per day.",
    ),
    ("FM-MACRO-INFEASIBLE", None): (
        _MACRO_EXPLANATION,
        "Widen the calorie or macro targets, or add recipes that fit them.",
    ),
    ("FM-3", "batch"): (
        "A meal-prep batch on {where} doesn't fit that day's targets or rules.",
        "Move or remove the batch, or use a different recipe for it.",
    ),
    ("FM-3", None): (
        "A pinned meal on {where} doesn't fit that day's targets or rules.",
        "Unpin it, or pin a different recipe.",
    ),
    ("FM-4", None): (
        "The available recipes can't provide enough {nutrients} over the plan.",
        "Add recipes rich in {nutrients}, or lower those goals.",
    ),
    ("FM-5", None): (
        "The planner ran out of attempts before finding a plan. That doesn't mean no plan exists.",
        "Try again with fewer days, wider macro targets, or fewer pinned meals.",
    ),
    ("FM-TAG-EMPTY", None): (
        "{Where} requires the \"{tag}\" tag, and no available recipe has it.",
        "Tag a recipe \"{tag}\", or remove that requirement from {where}.",
    ),
    ("FM-BATCH-CONFLICT", None): (
        "More than one meal-prep batch is assigned to {where}.",
        "Remove a batch so only one fills that meal.",
    ),
}

_IMPOSSIBLE_TARGET_TEXT = {
    "calories": "the calorie target isn't positive",
    "carbs": "protein and fat leave no calories for carbs",
    "fat_range": "the minimum fat is above the maximum",
    "protein_fat_vs_calories": "protein and minimum fat alone exceed the calorie target",
    "calorie_ceiling": "the calorie ceiling is below the calorie target",
}

_UNIT_SUFFIX = re.compile(r"_(mg|mcg|ug|g|iu|kcal)$")


def nutrient_label(key: str) -> str:
    """``vitamin_c_mg`` -> ``vitamin C``; ``fiber_g`` -> ``fiber``."""
    words = _UNIT_SUFFIX.sub("", str(key)).split("_")
    if len(words) >= 2 and words[0] == "vitamin":
        return "vitamin " + "".join(words[1:]).upper()
    return " ".join(words)


def _join(items: Sequence[str]) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _day_number(failure: Dict[str, Any]) -> Optional[int]:
    """1-based day from day_index, or from a ``day-N`` date (FM-MACRO-INFEASIBLE sets only the date)."""
    day_index = failure.get("day_index")
    if isinstance(day_index, int):
        return day_index + 1
    for date in (failure.get("date"), (failure.get("details") or {}).get("date")):
        match = re.fullmatch(r"day-(\d+)", str(date or ""))
        if match:
            return int(match.group(1))
    return None


def _where(failure: Dict[str, Any]) -> str:
    day = _day_number(failure)
    slot_index = failure.get("slot_index")
    if day is None:
        return "the plan"
    if isinstance(slot_index, int):
        return f"day {day}, meal {slot_index + 1}"
    return f"day {day}"


def _variant(
    code: str,
    failure: Dict[str, Any],
    batch_slots: AbstractSet[Tuple[int, int]],
) -> Optional[str]:
    """Refine the cause from the failure itself where the diagnosis can't tell cases apart."""
    details = failure.get("details") or {}
    if code == "FM-1":
        blocking = " ".join(str(b) for b in details.get("blocking_constraints") or [])
        for constraint in ("HC-8", "HC-3", "HC-1"):
            if constraint in blocking:
                return constraint
    if code == "FM-3":
        pinned = details.get("pinned_slots") or []
        if any(isinstance(p, dict) and p.get("source") == "batch" for p in pinned):
            return "batch"
        # A direct FM-3 carries no source; look the slot up in the profile's batch locks.
        if (failure.get("day_index"), failure.get("slot_index")) in batch_slots:
            return "batch"
    return None


def _context(failure: Dict[str, Any], diagnosis: Optional[Diagnosis]) -> Dict[str, Any]:
    details = failure.get("details") or {}
    where = _where(failure)
    blocking = " ".join(str(b) for b in details.get("blocking_constraints") or [])
    cap = re.search(r"<=\s*(\d+)\s*min", blocking)
    nutrients = [
        nutrient_label(d["nutrient"])
        for d in details.get("deficient_nutrients") or []
        if isinstance(d, dict) and d.get("nutrient")
    ]
    if not nutrients and isinstance(diagnosis, GapSpec):
        nutrients = [nutrient_label(n) for n in diagnosis.nutrient_min_per_recipe]
    problems: List[str] = []
    if isinstance(diagnosis, UnrecoverableReason) and diagnosis.code == "IMPOSSIBLE_TARGETS":
        problems = [_IMPOSSIBLE_TARGET_TEXT.get(k, str(v)) for k, v in diagnosis.details.items()]
    return {
        "where": where,
        "Where": where[0].upper() + where[1:],
        "tag": details.get("missing_tag") or "required",
        "cap_clause": f"in {cap.group(1)} minutes or less" if cap else "within its time limit",
        "nutrients": _join(nutrients) or "some tracked nutrients",
        "problems": _join(problems) or "they conflict",
        "per_meal_calories": _round(getattr(diagnosis, "per_meal_calories", None)),
        "per_meal_protein_g": _round(getattr(diagnosis, "per_meal_protein_g", None)),
    }


def _round(value: Optional[float]) -> Optional[int]:
    return None if value is None else int(round(value))


def cause_of(diagnosis: Optional[Diagnosis]) -> Optional[str]:
    if isinstance(diagnosis, GapSpec):
        return diagnosis.kind
    if isinstance(diagnosis, UnrecoverableReason):
        return diagnosis.code
    return None


def explain_failure(
    failure: Dict[str, Any],
    diagnosis: Optional[Diagnosis],
    batch_slots: AbstractSet[Tuple[int, int]] = frozenset(),
) -> Dict[str, Any]:
    """Return ``{explanation, fix, cause}`` for one normalized failure object.

    ``batch_slots`` holds the 0-based ``(day_index, slot_index)`` of every batch lock.
    """
    code = _CODE_ALIASES.get(str(failure.get("code", "")), str(failure.get("code", "")))
    cause = cause_of(diagnosis)
    ctx = _context(failure, diagnosis)

    keys: List[Tuple[str, Optional[str]]] = []
    if cause in _PLAN_WIDE_CAUSES:
        keys.append(("*", cause))
    variant = _variant(code, failure, batch_slots)
    if variant:
        keys.append((code, variant))
    keys += [(code, cause), (code, None)]

    for key in keys:
        if key not in _TABLE:
            continue
        explanation, fix = _TABLE[key]
        if "{per_meal_" in fix and ctx["per_meal_calories"] is None:
            fix = _TABLE[(code, None)][1]
        return {
            "explanation": explanation.format(**ctx),
            "fix": fix.format(**ctx),
            "cause": cause,
        }

    hint = str(failure.get("fix_hint") or fix_hint_for_code(code))
    return {
        "explanation": str(failure.get("message") or "The planner couldn't build a plan."),
        "fix": hint,
        "cause": cause,
    }


def failure_cause_block(diagnosis: Optional[Diagnosis]) -> Optional[Dict[str, Any]]:
    """Summary for ``report.failure_cause``: can a new recipe help, and what must it satisfy?

    Indices in ``recipe_gap.slots`` are 0-based ``[day_index, slot_index]``, like the rest of the API.
    """
    if diagnosis is None:
        return None
    block: Dict[str, Any] = {
        "cause": cause_of(diagnosis),
        "recipe_could_help": isinstance(diagnosis, GapSpec),
    }
    if isinstance(diagnosis, GapSpec):
        block["recipe_gap"] = {
            "per_meal_calories": diagnosis.per_meal_calories,
            "per_meal_protein_g": diagnosis.per_meal_protein_g,
            "per_meal_fat_g_max": diagnosis.per_meal_fat_g_max,
            "per_meal_carbs_g": diagnosis.per_meal_carbs_g,
            "cook_time_cap_minutes": diagnosis.cook_time_cap_minutes,
            "excluded_ingredients": list(diagnosis.excluded_ingredients),
            "nutrient_min_per_recipe": dict(diagnosis.nutrient_min_per_recipe),
            "meal_types": list(diagnosis.meal_types),
            "slots": [list(s) for s in diagnosis.slots],
        }
    return block


def attach_failure_explanations(
    out: Dict[str, Any],
    result: MealPlanResult,
    profile: PlanningUserProfile,
    pool: Sequence[PlanningRecipe],
    days: int,
) -> None:
    """Add explanations to a ``format_result_json`` payload in place. No-op when nothing failed."""
    report = out.get("report")
    if not isinstance(report, dict):
        return
    failures = report.get("failures") or []
    if not failures:
        return
    diagnosis: Optional[Diagnosis] = diagnose(result, profile, list(pool), days)
    batch_slots = {(lock.day_index, lock.slot_index) for lock in profile.batch_locks or []}
    for failure in failures:
        if isinstance(failure, dict):
            failure.update(explain_failure(failure, diagnosis, batch_slots))
    report["failure_cause"] = failure_cause_block(diagnosis)
