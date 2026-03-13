"""Formatters for meal plan output (JSON and Markdown)."""

import json
from typing import Dict, List, Any, Optional, Union

from src.data_layer.models import Ingredient, NutritionProfile, MicronutrientProfile
from src.planning.phase0_models import (
    PlanningRecipe,
    PlanningUserProfile,
    Assignment,
    micronutrient_profile_to_dict,
)
from src.planning.phase10_reporting import MealPlanResult


# Human-readable names for micronutrients in markdown output
MICRO_DISPLAY_NAMES: Dict[str, str] = {
    "iron_mg": "Iron",
    "vitamin_c_mg": "Vitamin C",
    "calcium_mg": "Calcium",
    "potassium_mg": "Potassium",
    "magnesium_mg": "Magnesium",
    "zinc_mg": "Zinc",
    "vitamin_a_ug": "Vitamin A",
    "vitamin_d_iu": "Vitamin D",
    "vitamin_e_mg": "Vitamin E",
    "vitamin_k_ug": "Vitamin K",
    "b1_thiamine_mg": "Vitamin B1",
    "b2_riboflavin_mg": "Vitamin B2",
    "b3_niacin_mg": "Vitamin B3",
    "b5_pantothenic_acid_mg": "Vitamin B5",
    "b6_pyridoxine_mg": "Vitamin B6",
    "b12_cobalamin_ug": "Vitamin B12",
    "folate_ug": "Folate",
    "phosphorus_mg": "Phosphorus",
    "selenium_ug": "Selenium",
    "sodium_mg": "Sodium",
    "manganese_mg": "Manganese",
    "copper_mg": "Copper",
    "fiber_g": "Fiber",
    "omega_3_g": "Omega-3",
    "omega_6_g": "Omega-6",
}


def _micro_key_to_display_name(key: str) -> str:
    """Convert field key like vitamin_a_ug to 'Vitamin A' if not in MICRO_DISPLAY_NAMES."""
    if key in MICRO_DISPLAY_NAMES:
        return MICRO_DISPLAY_NAMES[key]
    # Fallback: vitamin_a_ug -> Vitamin A, b6_pyridoxine_mg -> Vitamin B6 (snake to Title)
    base = key.rsplit("_", 1)[0] if key.rsplit("_", 1)[-1] in ("ug", "mg", "g", "iu") else key
    return base.replace("_", " ").title()


def _micronutrients_to_dict(
    micronutrients: Optional[Union[MicronutrientProfile, Dict[str, float]]],
) -> Dict[str, float]:
    """Convert micronutrients to dict and filter to values > 0."""
    if micronutrients is None:
        return {}
    if isinstance(micronutrients, dict):
        return {k: float(v) for k, v in micronutrients.items() if v and float(v) > 0}
    return {
        k: v
        for k, v in micronutrient_profile_to_dict(micronutrients).items()
        if v and v > 0
    }


def format_ingredient_string(ingredient: Ingredient) -> str:
    """Format an ingredient as a string (e.g., "200g cream of rice").
    
    Args:
        ingredient: Ingredient object
        
    Returns:
        Formatted string like "200g cream of rice" or "salt to taste"
    """
    if ingredient.is_to_taste:
        return f"{ingredient.name} to taste"
    
    # Format quantity (remove .0 if whole number)
    if ingredient.quantity == int(ingredient.quantity):
        qty_str = str(int(ingredient.quantity))
    else:
        qty_str = f"{ingredient.quantity:.1f}".rstrip('0').rstrip('.')
    
    # Format unit
    unit_str = ingredient.unit if ingredient.unit else ""
    
    # Combine (add space between quantity/unit and name)
    if unit_str:
        return f"{qty_str} {unit_str} {ingredient.name}"
    else:
        return f"{qty_str} {ingredient.name}"


def format_nutrition_breakdown(
    nutrition: NutritionProfile,
    indent: str = "",
    micronutrients: Optional[Union[MicronutrientProfile, Dict[str, float]]] = None,
) -> str:
    """Format nutrition profile as a readable breakdown.

    Args:
        nutrition: NutritionProfile object
        indent: Optional indentation prefix
        micronutrients: Optional MicronutrientProfile or Dict[str, float]; shown when present with values > 0

    Returns:
        Formatted string with calories, macros, and optionally micronutrients
    """
    lines = [
        f"{indent}**Calories:** {nutrition.calories:.0f} kcal",
        f"{indent}**Protein:** {nutrition.protein_g:.1f}g",
        f"{indent}**Fat:** {nutrition.fat_g:.1f}g",
        f"{indent}**Carbs:** {nutrition.carbs_g:.1f}g",
    ]
    micro_dict = _micronutrients_to_dict(micronutrients)
    if micro_dict:
        lines.append("")
        lines.append(f"{indent}**Micronutrients:**")
        for key in sorted(micro_dict.keys()):
            val = micro_dict[key]
            unit = "mg" if key.endswith("_mg") else "ug" if key.endswith("_ug") else "g" if key.endswith("_g") else "IU"
            lines.append(f"{indent}  {_micro_key_to_display_name(key)}: {val:.1f} {unit}")
    return "\n".join(lines)


# --- Canonical formatters (MealPlanResult) ---


def format_result_markdown(
    result: MealPlanResult,
    recipe_by_id: Dict[str, PlanningRecipe],
    profile: PlanningUserProfile,
    D: int,
) -> str:
    """Format a MealPlanResult as Markdown. Groups by day; shows recipe name, ingredients, nutrition, daily/weekly totals."""
    lines = []
    lines.append("# Meal Plan Result\n")
    lines.append(f"**Success:** {result.success}")
    lines.append(f"**Termination code:** {result.termination_code}\n")
    if result.warning:
        lines.append("## Warnings")
        for k, v in result.warning.items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    if not result.plan:
        return "\n".join(lines)

    meal_names = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner", "snack": "Snack"}
    by_day: Dict[int, List[Assignment]] = {}
    for a in result.plan:
        by_day.setdefault(a.day_index, []).append(a)
    for day_index in sorted(by_day.keys()):
        assignments = sorted(by_day[day_index], key=lambda x: x.slot_index)
        lines.append(f"## Day {day_index + 1}\n")
        for a in assignments:
            recipe = recipe_by_id.get(a.recipe_id)
            if recipe is None:
                lines.append(f"- Recipe id={a.recipe_id} (not in pool)\n")
                continue
            slot = profile.schedule[day_index][a.slot_index] if day_index < len(profile.schedule) else None
            meal_type = slot.meal_type if slot else "meal"
            meal_type_display = meal_names.get(meal_type, meal_type.capitalize())
            lines.append(f"### {recipe.name} ({meal_type_display})")
            lines.append(f"**Cooking time:** {recipe.cooking_time_minutes} minutes")
            lines.append("**Ingredients:**")
            for ing in recipe.ingredients:
                lines.append(f"- {format_ingredient_string(ing)}")
            lines.append("**Nutrition:**")
            lines.append(
                format_nutrition_breakdown(
                    recipe.nutrition,
                    micronutrients=getattr(recipe.nutrition, "micronutrients", None),
                )
            )
            lines.append("")
        if result.daily_trackers and day_index in result.daily_trackers:
            t = result.daily_trackers[day_index]
            day_totals = NutritionProfile(
                t.calories_consumed, t.protein_consumed, t.fat_consumed, t.carbs_consumed
            )
            lines.append("**Day totals:**")
            micro_day = getattr(t, "micronutrients_consumed", None) or {}
            lines.append(
                format_nutrition_breakdown(day_totals, micronutrients=micro_day if micro_day else None)
            )
            lines.append("")

    if D > 1 and result.weekly_tracker and result.weekly_tracker.weekly_totals:
        lines.append("## Weekly totals")
        w = result.weekly_tracker.weekly_totals
        micro_weekly = getattr(w, "micronutrients", None)
        lines.append(
            format_nutrition_breakdown(w, micronutrients=micro_weekly)
        )
        lines.append("")

    return "\n".join(lines)


def format_result_json(
    result: MealPlanResult,
    recipe_by_id: Dict[str, PlanningRecipe],
    profile: PlanningUserProfile,
    D: int,
) -> Dict[str, Any]:
    """Format a MealPlanResult as a JSON-serializable dict. Top-level: success, termination_code, days, daily_plans, weekly_totals (if D>1), warnings, goals."""
    daily_plans = []
    if result.plan and result.daily_trackers:
        by_day: Dict[int, List[Assignment]] = {}
        for a in result.plan:
            by_day.setdefault(a.day_index, []).append(a)
        for day_index in sorted(by_day.keys()):
            assignments = sorted(by_day[day_index], key=lambda x: x.slot_index)
            meals_json = []
            for a in assignments:
                recipe = recipe_by_id.get(a.recipe_id)
                if recipe is None:
                    meals_json.append({"recipe_id": a.recipe_id, "error": "not in pool"})
                    continue
                slot = profile.schedule[day_index][a.slot_index] if day_index < len(profile.schedule) else None
                meal_type = slot.meal_type if slot else "meal"
                rec_nut = recipe.nutrition
                nutrition_json = {
                    "calories": round(rec_nut.calories, 1),
                    "protein_g": round(rec_nut.protein_g, 1),
                    "fat_g": round(rec_nut.fat_g, 1),
                    "carbs_g": round(rec_nut.carbs_g, 1),
                }
                micro_rec = _micronutrients_to_dict(getattr(rec_nut, "micronutrients", None))
                if micro_rec:
                    nutrition_json["micronutrients"] = {k: round(v, 1) for k, v in micro_rec.items()}
                meals_json.append({
                    "recipe_id": recipe.id,
                    "name": recipe.name,
                    "meal_type": meal_type,
                    "cooking_time_minutes": recipe.cooking_time_minutes,
                    "ingredients": [format_ingredient_string(ing) for ing in recipe.ingredients],
                    "nutrition": nutrition_json,
                })
            t = result.daily_trackers.get(day_index)
            day_totals = None
            if t is not None:
                day_totals = {
                    "calories": round(t.calories_consumed, 1),
                    "protein_g": round(t.protein_consumed, 1),
                    "fat_g": round(t.fat_consumed, 1),
                    "carbs_g": round(t.carbs_consumed, 1),
                }
                micro_day = getattr(t, "micronutrients_consumed", None) or {}
                if micro_day:
                    micro_filtered = _micronutrients_to_dict(micro_day)
                    if micro_filtered:
                        day_totals["micronutrients"] = {k: round(v, 1) for k, v in micro_filtered.items()}
            daily_plans.append({"day": day_index + 1, "meals": meals_json, "totals": day_totals})

    weekly_totals = None
    if D > 1 and result.weekly_tracker and result.weekly_tracker.weekly_totals:
        w = result.weekly_tracker.weekly_totals
        weekly_totals = {
            "calories": round(w.calories, 1),
            "protein_g": round(w.protein_g, 1),
            "fat_g": round(w.fat_g, 1),
            "carbs_g": round(w.carbs_g, 1),
        }
        micro_weekly = _micronutrients_to_dict(getattr(w, "micronutrients", None))
        if micro_weekly:
            weekly_totals["micronutrients"] = {k: round(v, 1) for k, v in micro_weekly.items()}

    goals = {
        "daily_calories": profile.daily_calories,
        "daily_protein_g": profile.daily_protein_g,
        "daily_fat_g_min": profile.daily_fat_g[0],
        "daily_fat_g_max": profile.daily_fat_g[1],
        "daily_carbs_g": profile.daily_carbs_g,
    }

    out = {
        "success": result.success,
        "termination_code": result.termination_code,
        "days": D,
        "daily_plans": daily_plans,
        "warnings": result.warning if result.warning else {},
        "goals": goals,
    }
    if weekly_totals is not None:
        out["weekly_totals"] = weekly_totals
    return out


def format_result_json_string(
    result: MealPlanResult,
    recipe_by_id: Dict[str, PlanningRecipe],
    profile: PlanningUserProfile,
    D: int,
    indent: int = 2,
) -> str:
    """Format a MealPlanResult as a JSON string."""
    return json.dumps(format_result_json(result, recipe_by_id, profile, D), indent=indent)

