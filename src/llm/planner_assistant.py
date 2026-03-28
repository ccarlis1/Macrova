from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

from src.llm.client import LLMClient
from src.llm.recipe_generator import generate_recipe_drafts
from src.llm.schemas import RecipeDraft
from src.planning.phase0_models import PlanningUserProfile
from src.planning.phase10_reporting import MealPlanResult


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _compute_macro_deficit_amounts(
    *,
    day_macro_violations: Dict[str, Any],
    profile: PlanningUserProfile,
) -> List[Dict[str, Any]]:
    """Turn `phase7_search` macro violation payload into signed deficits/excesses.

    The planner's FM-2 report includes consumed values but not required bounds; we
    compute deficit/excess against the deterministic profile targets here.
    """

    consumed_calories = _safe_float(day_macro_violations.get("calories_consumed", 0.0))
    consumed_protein = _safe_float(day_macro_violations.get("protein_consumed", 0.0))
    consumed_fat = _safe_float(day_macro_violations.get("fat_consumed", 0.0))
    consumed_carbs = _safe_float(day_macro_violations.get("carbs_consumed", 0.0))

    target_calories = float(profile.daily_calories)
    target_protein = float(profile.daily_protein_g)
    target_fat_min, target_fat_max = profile.daily_fat_g
    target_carbs = float(profile.daily_carbs_g)

    constraint_detail = str(day_macro_violations.get("constraint_detail", "")).strip()

    # For guidance purposes we return both deficit and excess directions with
    # magnitude (positive numbers only) to keep downstream logic simple.
    def _one(name: str, *, delta: float) -> Dict[str, Any]:
        if delta < 0:
            return {"macro": name, "direction": "deficit", "amount": abs(delta)}
        if delta > 0:
            return {"macro": name, "direction": "excess", "amount": abs(delta)}
        return {"macro": name, "direction": "within_range", "amount": 0.0}

    calories_delta = consumed_calories - target_calories
    protein_delta = consumed_protein - target_protein
    fat_delta = 0.0
    if consumed_fat < target_fat_min:
        fat_delta = consumed_fat - target_fat_min
    elif consumed_fat > target_fat_max:
        fat_delta = consumed_fat - target_fat_max
    carbs_delta = consumed_carbs - target_carbs

    return [
        {"macro": "calories", "constraint_detail": constraint_detail, **_one("calories", delta=calories_delta)},
        {"macro": "protein", "constraint_detail": constraint_detail, **_one("protein", delta=protein_delta)},
        {"macro": "fat", "constraint_detail": constraint_detail, **_one("fat", delta=fat_delta)},
        {"macro": "carbs", "constraint_detail": constraint_detail, **_one("carbs", delta=carbs_delta)},
    ]


def build_feedback_context(
    result: MealPlanResult,
    profile: PlanningUserProfile,
) -> Dict[str, Any]:
    """Deterministically extract planner failure signals into an LLM prompt context.

    This function must NOT depend on the LLM and must be stable across runs.
    """

    failure_type = result.failure_mode or result.termination_code
    days = len(profile.schedule)
    meals_per_day = len(profile.schedule[0]) if days > 0 and profile.schedule else 0

    # FM-4: weekly micronutrient infeasibility -> deficient_nutrients list.
    deficient_nutrients: List[Dict[str, Any]] = []
    for item in (result.report or {}).get("deficient_nutrients", []) or []:
        if not isinstance(item, dict):
            continue
        deficient_nutrients.append(
            {
                "nutrient": str(item.get("nutrient", "")),
                "achieved": _safe_float(item.get("achieved", 0.0)),
                "required": _safe_float(item.get("required", 0.0)),
                "deficit": _safe_float(item.get("deficit", 0.0)),
                "classification": str(item.get("classification", "")),
            }
        )

    # FM-2: daily constraint exhaustion -> macro_violations per failed day.
    macro_violations_out: List[Dict[str, Any]] = []
    for failed_day in (result.report or {}).get("failed_days", []) or []:
        if not isinstance(failed_day, dict):
            continue
        day_index = failed_day.get("day")
        day_macro = failed_day.get("macro_violations", {}) or {}
        if not isinstance(day_macro, dict):
            day_macro = {}
        computed = _compute_macro_deficit_amounts(
            day_macro_violations=day_macro,
            profile=profile,
        )
        macro_violations_out.append(
            {
                "day": day_index,
                "violations": computed,
            }
        )

    # Keep the context as "prompt-ready JSON": only numbers/strings/arrays/dicts.
    # Copy defensively so callers can't mutate internal structures.
    busyness_by_day = [
        [int(slot.busyness_level) for slot in day] for day in (profile.schedule or [])
    ]
    workout_gaps = profile.workout_after_meal_indices_by_day
    ctx: Dict[str, Any] = {
        "failure_type": failure_type,
        "nutrient_deficits": deficient_nutrients,
        "macro_violations": macro_violations_out,
        "days": int(days),
        "meals_per_day": int(meals_per_day),
        "busyness_by_day": busyness_by_day,
        "workout_gaps_by_day": (
            [list(g) for g in workout_gaps] if workout_gaps is not None else None
        ),
    }
    return copy.deepcopy(ctx)


def suggest_targeted_recipe_drafts(
    client: LLMClient,
    context: Dict[str, Any],
    count: int,
) -> List[RecipeDraft]:
    """Generate targeted recipe drafts given deterministic feedback context."""

    # The existing recipe generator already enforces strict JSON + RecipeDraft
    # schema validation; we only control the deterministic prompt context shape.
    return generate_recipe_drafts(client=client, context=context, count=count)

