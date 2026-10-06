"""Conversion layer from data layer (Recipe, UserProfile) to planning layer (PlanningRecipe, PlanningUserProfile).

Pure functions only. No I/O, no provider access. Deterministic.
"""

import json
import logging
from dataclasses import replace
from typing import Any, Dict, List, Optional, Set

from src.data_layer.models import (
    Recipe,
    UserProfile,
    NutritionProfile,
    Ingredient,
)
from src.data_layer.exceptions import IngredientNotFoundError
from src.models.schedule import DaySchedule as CanonicalDaySchedule
from src.planning.allergens import expand_allergy_terms, exclusions_for_dietary_flags
from src.planning.phase0_models import PlanningRecipe, PlanningUserProfile, MealSlot
from src.nutrition.calculator import NutritionCalculator

logger = logging.getLogger(__name__)

# Synthetic meal clock anchors when ``preferred_time`` is absent (aligned with legacy migration).
_DEFAULT_MEAL_CLOCKS: tuple[str, ...] = (
    "07:00",
    "08:30",
    "12:00",
    "15:00",
    "18:00",
    "19:00",
    "20:00",
    "21:00",
)


def normalize_schedule_days_for_api(
    schedule_days: List[CanonicalDaySchedule],
) -> List[Dict[str, Any]]:
    """Canonical JSON for persisted/API schedule_days (matches PUT /profile/schedule output).

    Deterministic ordering: days by day_index, meals by index, workouts by gap then type.
    """

    normalized: List[Dict[str, Any]] = []
    for day in sorted(schedule_days, key=lambda d: d.day_index):
        day_payload = day.model_dump(mode="json", exclude_none=True)
        day_payload["meals"] = sorted(day_payload.get("meals", []), key=lambda m: m["index"])
        day_payload["workouts"] = sorted(
            day_payload.get("workouts", []),
            key=lambda w: (w["after_meal_index"], w["type"]),
        )
        normalized.append(day_payload)
    return normalized


def _expand_schedule_days(
    schedule_days: List[CanonicalDaySchedule],
    days: int,
) -> List[CanonicalDaySchedule]:
    """Normalize canonical days to length ``days`` (replicate or slice)."""
    if not schedule_days:
        raise ValueError("schedule_days is empty")
    if len(schedule_days) == days:
        return [
            schedule_days[i].model_copy(update={"day_index": i + 1})
            for i in range(days)
        ]
    if len(schedule_days) == 1:
        t = schedule_days[0]
        return [
            CanonicalDaySchedule(
                day_index=i + 1,
                meals=list(t.meals),
                workouts=list(t.workouts),
            )
            for i in range(days)
        ]
    if len(schedule_days) >= days:
        return [
            schedule_days[i].model_copy(update={"day_index": i + 1})
            for i in range(days)
        ]
    out: List[CanonicalDaySchedule] = []
    for i in range(days):
        src = schedule_days[i] if i < len(schedule_days) else schedule_days[-1]
        out.append(src.model_copy(update={"day_index": i + 1}))
    return out


def _meal_type_from_canonical(
    tags: Optional[List[str]],
    pos: int,
    n: int,
) -> str:
    meal_type_by_position = ("breakfast", "lunch", "dinner", "snack")
    if tags:
        for t in tags:
            tl = str(t).lower()
            if tl in ("breakfast", "lunch", "dinner", "snack"):
                return tl
    if n >= 3 and pos == 0:
        return "breakfast"
    if n >= 3 and pos == n - 1:
        return "dinner"
    if n >= 3 and pos == n // 2:
        return "lunch"
    return meal_type_by_position[min(pos, 3)]


def _canonical_day_to_planning_slots(
    day: CanonicalDaySchedule,
    meal_types_per_day: Optional[List[List[str]]],
    day_index: int,
) -> List[MealSlot]:
    """Map API ``DaySchedule`` to planner ``MealSlot`` rows (per-meal busyness + clock)."""
    slots: List[MealSlot] = []
    n = len(day.meals)
    for i, m in enumerate(day.meals):
        clock = m.preferred_time
        if not clock:
            clock = _DEFAULT_MEAL_CLOCKS[i] if i < len(_DEFAULT_MEAL_CLOCKS) else "12:00"
        if meal_types_per_day is not None and day_index < len(meal_types_per_day):
            day_types = meal_types_per_day[day_index]
            meal_type = (
                day_types[i]
                if i < len(day_types)
                else _meal_type_from_canonical(m.tags, i, n)
            )
        else:
            meal_type = _meal_type_from_canonical(m.tags, i, n)
        slots.append(
            MealSlot(
                time=clock,
                busyness_level=m.busyness_level,
                meal_type=meal_type,
                required_tag_slugs=list(m.required_tag_slugs or []) or None,
                preferred_tag_slugs=list(m.preferred_tag_slugs or []) or None,
            )
        )
    return slots


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


def _normalize_recipe_quantities(recipe: Recipe, calculator: NutritionCalculator) -> Recipe:
    """Return a copy of ``recipe`` whose ingredients carry grams in ``normalized_quantity``.

    Grams-first (U1/U2): each ingredient converts once, here, after provider
    resolution. An ingredient that can't convert is left unnormalized; the
    unresolved check below reports it and drops the recipe. Calculators without
    ``normalize_ingredient`` (e.g. the harness's stored-nutrition stub) are skipped.
    """
    normalize = getattr(calculator, "normalize_ingredient", None)
    if not callable(normalize):
        return recipe
    ingredients = []
    for ingredient in recipe.ingredients:
        try:
            ingredients.append(normalize(ingredient))
        except IngredientNotFoundError:
            ingredients.append(ingredient)
        except RuntimeError:
            # API provider: name not pre-resolved via resolve_all
            ingredients.append(ingredient)
    return replace(recipe, ingredients=ingredients)


def convert_recipes(
    recipes: List[Recipe],
    calculator: NutritionCalculator,
    canonical_tag_slugs_by_id: Optional[Dict[str, Set[str]]] = None,
    *,
    drop_unresolved: bool = True,
    unresolved_log: Optional[List[Dict[str, Any]]] = None,
) -> List[PlanningRecipe]:
    """Convert data-layer recipes to planning recipes with pre-computed nutrition.

    Each ingredient first converts to grams once (``normalized_quantity``, via
    ``calculator.normalize_ingredient``); the planning recipe carries the
    normalized ingredients. Then calls calculator.calculate_recipe_nutrition
    for each recipe. Output is sorted
    by recipe.id for determinism. No provider access; calculator only.

    When ``drop_unresolved`` is True (default, §4.4), recipes with any
    non-to-taste ingredient the calculator cannot resolve are omitted from the
    pool. If ``unresolved_log`` is provided, each dropped recipe is appended as
    ``{"recipe_id", "recipe_name", "unresolved_ingredients"}``.
    """
    out: List[PlanningRecipe] = []
    for recipe in recipes:
        recipe = _normalize_recipe_quantities(recipe, calculator)
        unresolved: List[str] = []
        lookup = getattr(calculator, "unresolved_ingredient_names", None)
        if callable(lookup):
            unresolved = list(lookup(recipe))
        if unresolved and drop_unresolved:
            if unresolved_log is not None:
                unresolved_log.append(
                    {
                        "recipe_id": recipe.id,
                        "recipe_name": recipe.name,
                        "unresolved_ingredients": unresolved,
                    }
                )
            logger.warning(
                "Dropping recipe %s from pool: unresolved ingredients %s",
                recipe.id,
                unresolved,
            )
            continue
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
                canonical_tag_slugs=set(
                    (canonical_tag_slugs_by_id or {}).get(recipe.id, set())
                ),
            )
        )
    out.sort(key=lambda r: r.id)
    return out


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
            MealSlot(
                time=time_str,
                busyness_level=busyness,
                meal_type=meal_type,
                required_tag_slugs=None,
                preferred_tag_slugs=None,
            )
        )
    return slots


def convert_profile(
    user_profile: UserProfile,
    days: int,
    meal_types_per_day: Optional[List[List[str]]] = None,
) -> PlanningUserProfile:
    """Convert UserProfile and planning horizon to PlanningUserProfile.

    Excluded ingredients = allergy terms expanded by allergen class, plus
    disliked_foods kept exact. Allergies are a safety guarantee (HC-1 / Q10);
    dislikes are exact-name hard exclusions only. Schedule is replicated for
    `days` days. Micronutrient targets from daily_micronutrient_targets
    (daily RDI values, pass-through). Deterministic.

    When ``user_profile.schedule_days`` is set, per-day meal counts, busyness,
    and workout gaps are taken from the canonical model; otherwise the legacy
    ``schedule`` dict path is used without explicit workout topology.
    """
    excluded_ingredients = expand_allergy_terms(
        user_profile.allergies
    ) + list(user_profile.disliked_foods)
    flag_exclusions = exclusions_for_dietary_flags(
        list(user_profile.dietary_flags or [])
    )
    if flag_exclusions:
        # Preserve allergy/dislike order; append dietary-flag names not already present.
        seen = {x.lower().strip() for x in excluded_ingredients}
        for name in flag_exclusions:
            if name not in seen:
                excluded_ingredients.append(name)
                seen.add(name)

    workout_after_meal_indices_by_day: Optional[List[List[int]]] = None
    schedule: List[List[MealSlot]]

    if user_profile.schedule_days is not None:
        expanded = _expand_schedule_days(list(user_profile.schedule_days), days)
        schedule = []
        workout_after_meal_indices_by_day = []
        for d in range(days):
            day_ds = expanded[d]
            schedule.append(
                _canonical_day_to_planning_slots(day_ds, meal_types_per_day, d)
            )
            workout_after_meal_indices_by_day.append(
                [w.after_meal_index for w in day_ds.workouts]
            )
        logger.debug(
            "convert_profile: translated planner schedule: %s",
            json.dumps(
                [
                    {
                        "day_index": d + 1,
                        "meal_count": len(schedule[d]),
                        "workout_gaps": workout_after_meal_indices_by_day[d],
                    }
                    for d in range(days)
                ],
                sort_keys=True,
            ),
        )
    else:
        one_day_slots = _schedule_dict_to_slots_one_day(
            user_profile.schedule,
            meal_types_per_day=meal_types_per_day,
            day_index=0,
        )
        schedule = []
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

    micronutrient_targets = dict(user_profile.daily_micronutrient_targets or {})
    # Hydration boundary: canonical persisted (day_index, slot_index) enters planner
    # as (day_1based, slot_index) pinned_assignments.
    pinned_assignments = {
        (int(pin.day_index) + 1, int(pin.slot_index)): str(pin.recipe_id)
        for pin in (user_profile.pins or [])
    }

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
        pinned_assignments=pinned_assignments,
        micronutrient_targets=micronutrient_targets,
        micronutrient_weekly_min_fraction=user_profile.micronutrient_weekly_min_fraction,
        activity_schedule={},
        workout_after_meal_indices_by_day=workout_after_meal_indices_by_day,
        enable_primary_carb_downscaling=False,
    )
