"""Build `GroceryOptimizeRequest.mealPlan` from planner data or `/api/v1/plan` JSON."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from src.data_layer.models import Ingredient, Recipe as DataRecipe


def recipe_servings_from_daily_plans(daily_plans: Iterable[Mapping[str, Any]]) -> Dict[str, float]:
    """Count `recipe_id` occurrences across all meals (effective servings per recipe in the window)."""

    counts: Dict[str, float] = {}
    for day in daily_plans:
        meals = day.get("meals") or []
        if not isinstance(meals, list):
            continue
        for meal in meals:
            if not isinstance(meal, Mapping):
                continue
            rid = meal.get("recipe_id")
            if rid is None:
                continue
            k = str(rid)
            counts[k] = counts.get(k, 0.0) + 1.0
    return counts


def grocery_meal_plan_payload(
    *,
    recipes: List[DataRecipe],
    recipe_servings: Optional[Mapping[str, float]] = None,
    plan_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Shape the `mealPlan` object for `GroceryOptimizeRequest` (camelCase in JSON).

    Callers typically compute `recipe_servings` with `recipe_servings_from_daily_plans`
    from the same plan JSON the Flutter app already has.
    """

    out_recipes: List[Dict[str, Any]] = []
    for r in recipes:
        out_recipes.append(
            {
                "id": r.id,
                "name": r.name,
                "ingredients": [_ingredient_to_grocery_json(ing) for ing in r.ingredients],
            }
        )
    body: Dict[str, Any] = {"recipes": out_recipes}
    if plan_id is not None:
        body["id"] = plan_id
    if recipe_servings:
        body["recipeServings"] = {str(k): float(v) for k, v in recipe_servings.items()}
    return body


def _ingredient_to_grocery_json(ing: Ingredient) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "name": ing.name,
        "quantity": float(ing.quantity),
        "unit": ing.unit,
    }
    if ing.is_to_taste:
        row["isToTaste"] = True
    return row


def merge_grocery_optimize_request(
    meal_plan: Mapping[str, Any],
    *,
    stores: List[Mapping[str, Any]],
    preferences: Optional[Mapping[str, Any]] = None,
    schema_version: str = "1.0",
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble a full `GroceryOptimizeRequest`-compatible dict for the Node CLI."""

    payload: Dict[str, Any] = {
        "schemaVersion": schema_version,
        "mealPlan": dict(meal_plan),
        "stores": [dict(s) for s in stores],
    }
    if preferences:
        payload["preferences"] = dict(preferences)
    if run_id:
        payload["runId"] = run_id
    return payload
