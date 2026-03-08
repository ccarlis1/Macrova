"""Conversion layer from data layer (Recipe, UserProfile) to planning layer (PlanningRecipe, PlanningUserProfile).

Pure functions only. No I/O, no provider access. Deterministic.
"""

from dataclasses import fields
from typing import List, Optional

from src.data_layer.models import (
    Recipe,
    UserProfile,
    NutritionProfile,
    Ingredient,
    WeeklyNutritionTargets,
)
from src.planning.phase0_models import PlanningRecipe, PlanningUserProfile, MealSlot
from src.nutrition.calculator import NutritionCalculator


def extract_ingredient_names(recipes: List[Recipe]) -> List[str]:
    """Return sorted unique ingredient names, excluding 'to taste' and empty names.

    Used to drive eager resolution before planning so no API calls occur
    during scoring or backtracking. Deterministic.
    """
    names: set[str] = set()
    for recipe in recipes:
        for ing in recipe.ingredients:
            if ing.is_to_taste:
                continue
            n = ing.name
            if n is None:
                continue
            n = str(n).strip()
            if not n:
                continue
            names.add(n)
    return sorted(names)


def convert_recipes(
    recipes: List[Recipe],
    calculator: NutritionCalculator,
) -> List[PlanningRecipe]:
    """Convert data-layer recipes to planning recipes with pre-computed nutrition.

    Calls calculator.calculate_recipe_nutrition for each recipe. Output is sorted
    by recipe.id for determinism. No provider access; calculator only.
    """
    out: List[PlanningRecipe] = []
    for recipe in recipes:
        nutrition = calculator.calculate_recipe_nutrition(recipe)
        out.append(
            PlanningRecipe(
                id=recipe.id,
                name=recipe.name,
                ingredients=recipe.ingredients,
                cooking_time_minutes=recipe.cooking_time_minutes,
                nutrition=nutrition,
                primary_carb_contribution=None,
                primary_carb_source=None,
            )
        )
    out.sort(key=lambda r: r.id)
    return out


def _weekly_targets_to_daily_dict(weekly_targets: WeeklyNutritionTargets) -> dict:
    """Convert WeeklyNutritionTargets (weekly totals) to daily RDI dict for micronutrient_targets."""
    result = {}
    for f in fields(weekly_targets):
        val = getattr(weekly_targets, f.name)
        if val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if v <= 0:
            continue
        result[f.name] = v / 7.0
    return result


def _schedule_dict_to_slots_one_day(
    schedule: dict,
    meal_types_per_day: Optional[List[List[str]]] = None,
    day_index: int = 0,
) -> List[MealSlot]:
    """Convert UserProfile.schedule (Dict[str, int]) to one day's List[MealSlot]."""
    meal_type_by_position = ("breakfast", "lunch", "dinner", "snack")
    sorted_times = sorted(schedule.keys())
    slots: List[MealSlot] = []
    for i, time_str in enumerate(sorted_times):
        busyness = schedule[time_str]
        if meal_types_per_day is not None and day_index < len(meal_types_per_day):
            day_types = meal_types_per_day[day_index]
            meal_type = day_types[i] if i < len(day_types) else meal_type_by_position[min(i, 3)]
        else:
            meal_type = meal_type_by_position[min(i, 3)]
        slots.append(
            MealSlot(time=time_str, busyness_level=busyness, meal_type=meal_type)
        )
    return slots


def convert_profile(
    user_profile: UserProfile,
    days: int,
    meal_types_per_day: Optional[List[List[str]]] = None,
) -> PlanningUserProfile:
    """Convert UserProfile and planning horizon to PlanningUserProfile.

    Excluded ingredients = allergies + disliked_foods. Schedule is replicated
    for `days` days. Micronutrient targets from weekly_targets (weekly totals
    converted to daily). Deterministic.
    """
    excluded_ingredients = list(user_profile.allergies) + list(user_profile.disliked_foods)

    one_day_slots = _schedule_dict_to_slots_one_day(
        user_profile.schedule,
        meal_types_per_day=meal_types_per_day,
        day_index=0,
    )
    schedule: List[List[MealSlot]] = []
    for d in range(days):
        if meal_types_per_day is not None and d < len(meal_types_per_day):
            slots_d = _schedule_dict_to_slots_one_day(
                user_profile.schedule,
                meal_types_per_day=meal_types_per_day,
                day_index=d,
            )
        else:
            slots_d = one_day_slots
        schedule.append(slots_d)

    if user_profile.weekly_targets is not None:
        micronutrient_targets = _weekly_targets_to_daily_dict(user_profile.weekly_targets)
    else:
        micronutrient_targets = {}

    return PlanningUserProfile(
        daily_calories=user_profile.daily_calories,
        daily_protein_g=user_profile.daily_protein_g,
        daily_fat_g=user_profile.daily_fat_g,
        daily_carbs_g=user_profile.daily_carbs_g,
        max_daily_calories=user_profile.max_daily_calories,
        schedule=schedule,
        excluded_ingredients=excluded_ingredients,
        liked_foods=list(user_profile.liked_foods),
        demographic="adult_male",
        upper_limits_overrides=None,
        pinned_assignments={},
        micronutrient_targets=micronutrient_targets,
        activity_schedule={},
        enable_primary_carb_downscaling=False,
    )
