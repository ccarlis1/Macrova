"""The MCP tools' logic, without the MCP SDK.

Each function takes validated models from :mod:`src.mcp_server.models` and returns a
result model (plus Markdown for :func:`plan_meals`). Bad input raises
:class:`InputError`; the server turns it into an ``isError`` result. An infeasible
plan is not an error: it comes back with ``status="failed"``.

Nothing here reads or writes user data (recipes, pins, batches, profile), and no
LLM client is built. Planning is always deterministic. Ingredient nutrition comes
from the bundled table first, then the USDA cache, then the USDA API when
``USDA_API_KEY`` is set.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pydantic import ValidationError

from src.api import server as api
from src.api.server import PlanRequest, PlanTagData, build_plan_inputs, format_plan_response
from src.data_layer.exceptions import IngredientNotFoundError
from src.data_layer.macro_targets import MacroTargetsError
from src.data_layer.models import Ingredient as DataIngredient
from src.data_layer.models import Recipe as DataRecipe
from src.data_layer.nutrition_db import NutritionDB
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.ingestion.usda_client import USDAClient
from src.llm import tag_repository
from src.llm.schemas import TagMetaJson
from src.mcp_server import models as m
from src.mcp_server.indexing import (
    SlotNumberError,
    batches_from_mcp,
    failure_where,
    meal_number,
    pins_from_mcp,
    recipe_gap_slots,
)
from src.mcp_server.nutrients import daily_rdis, plain_name, plain_names, upper_limits
from src.models.legacy_schedule_migration import merge_schedule_warnings_into_result
from src.nutrition.calculator import NutritionCalculator
from src.planning.planner import plan_meals as run_planner
from src.providers.summary_hybrid_provider import SummaryHybridIngredientProvider

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_RECIPES_PATH = ROOT / "data" / "recipes" / "recipes.json.example"
TAG_PATH = ROOT / api.DEFAULT_TAG_PATH
INGREDIENTS_PATH = ROOT / api.DEFAULT_INGREDIENTS_PATH
INGREDIENT_CACHE_DIR = ROOT / ".cache" / "ingredients"

_SOURCES = {"planner": "planner", "pinned_assignment": "pin", "meal_prep_batch": "meal_prep"}
_THREE_MEAL_LABELS = ("breakfast", "lunch", "dinner")


class InputError(ValueError):
    """Malformed or inconsistent tool input. Reported as ``isError: true``."""


# --- Ingredients ---------------------------------------------------------------


def usda_enabled() -> bool:
    return bool(os.environ.get("USDA_API_KEY", "").strip())


@lru_cache(maxsize=1)
def _nutrition_db() -> NutritionDB:
    return NutritionDB(str(INGREDIENTS_PATH))


def build_provider() -> SummaryHybridIngredientProvider:
    """Bundled table, then the USDA cache, then the USDA API (only with a key). Patched in tests."""
    client = USDAClient.from_env() if usda_enabled() else None
    lookup = CachedIngredientLookup(cache_dir=str(INGREDIENT_CACHE_DIR), usda_client=client)
    return SummaryHybridIngredientProvider(_nutrition_db(), lookup)


def _data_ingredient(line: m.RecipeIngredient) -> DataIngredient:
    return api._nutrition_line_to_data_ingredient(
        api.NutritionIngredientLine(name=line.name, quantity=line.quantity, unit=line.unit)
    )


def _data_recipe(recipe: m.Recipe) -> DataRecipe:
    return DataRecipe(
        id=recipe.id,
        name=recipe.name,
        ingredients=[_data_ingredient(line) for line in recipe.ingredients],
        cooking_time_minutes=recipe.cooking_time_minutes,
        instructions=list(recipe.instructions),
    )


# --- Tags ----------------------------------------------------------------------


@lru_cache(maxsize=1)
def _approved_tags() -> Dict[str, TagMetaJson]:
    """Registry tags a caller may use: everything except proposed or rejected LLM tags."""
    out: Dict[str, TagMetaJson] = {}
    for meta in tag_repository.list_by_type(str(TAG_PATH)):
        enriched = tag_repository.enrich_tag_meta(meta)
        if str(enriched.eligibility or "").lower() not in {"proposed", "rejected"}:
            out[enriched.slug] = enriched
    return out


def _resolve_tag(raw: str, where: str) -> TagMetaJson:
    token = raw.strip()
    meta = _approved_tags().get(token.lower())
    if meta is None:
        try:
            meta = _approved_tags().get(tag_repository.resolve(token, str(TAG_PATH)).slug)
        except ValueError:
            meta = None
    if meta is None:
        raise InputError(f"Unknown tag {raw!r} on {where}. Call macrova_list_tags for the valid slugs.")
    return meta


def _tag_data(recipes: Sequence[m.Recipe]) -> PlanTagData:
    canonical: Dict[str, set[str]] = {}
    hard: Dict[str, set[str]] = {}
    for recipe in recipes:
        metas = [_resolve_tag(t, f"recipe {recipe.id!r}") for t in recipe.tags]
        canonical[recipe.id] = {meta.slug for meta in metas}
        hard[recipe.id] = {meta.slug for meta in metas if tag_repository.is_planner_hard_eligible(meta)}
    return PlanTagData(tags_by_id={}, canonical_slugs_by_id=canonical, hard_eligible_slugs_by_id=hard)


# --- Sample recipes ------------------------------------------------------------


@lru_cache(maxsize=1)
def _sample_recipes() -> Tuple[m.Recipe, ...]:
    with open(SAMPLE_RECIPES_PATH, encoding="utf-8") as f:
        raw = json.load(f)["recipes"]
    slugs_by_id = tag_repository.load_canonical_recipe_tag_slugs(str(TAG_PATH))
    approved = _approved_tags()
    return tuple(
        m.Recipe(
            id=r["id"],
            name=r["name"],
            ingredients=[m.RecipeIngredient(**line) for line in r["ingredients"]],
            cooking_time_minutes=int(r.get("cooking_time_minutes") or 0),
            instructions=list(r.get("instructions") or []),
            tags=sorted(s for s in slugs_by_id.get(r["id"], set()) if s in approved),
        )
        for r in raw
    )


def get_sample_recipes() -> m.SampleRecipes:
    calculator = NutritionCalculator(build_provider())
    out = []
    for recipe in _sample_recipes():
        data_recipe = _data_recipe(recipe)
        unmatched = calculator.unresolved_ingredient_names(data_recipe)
        nutrition = None if unmatched else calculator.calculate_recipe_nutrition(data_recipe)
        out.append(
            m.SampleRecipe(
                **recipe.model_dump(),
                per_serving_calories=round(nutrition.calories) if nutrition else None,
                per_serving_protein_g=round(nutrition.protein_g, 1) if nutrition else None,
                ready_for_planning=not unmatched,
                unmatched=unmatched,
            )
        )
    return m.SampleRecipes(recipes=out)


# --- Tags tool -----------------------------------------------------------------


def list_tags() -> m.TagList:
    return m.TagList(
        tags=[
            m.Tag(
                slug=meta.slug,
                type=meta.tag_type,
                description=meta.display,
                can_require=tag_repository.is_planner_hard_eligible(meta),
            )
            for meta in sorted(_approved_tags().values(), key=lambda t: (t.tag_type, t.slug))
        ]
    )


# --- Recipe analysis -----------------------------------------------------------


def analyze_recipe(recipe: m.Recipe, servings: int = 1) -> m.RecipeAnalysis:
    provider = build_provider()
    calculator = NutritionCalculator(provider)
    matched: List[m.MatchedIngredient] = []
    unmatched: List[m.UnmatchedIngredient] = []
    skipped: List[str] = []
    for line in recipe.ingredients:
        ingredient = _data_ingredient(line)
        if ingredient.is_to_taste:
            skipped.append(line.name)
            continue
        info = provider.get_ingredient_info(ingredient.name)
        if info is None:
            unmatched.append(m.UnmatchedIngredient(input=line.name, reason="no confident match"))
            continue
        try:
            grams = calculator.to_grams(ingredient, info)
        except IngredientNotFoundError:
            unmatched.append(
                m.UnmatchedIngredient(
                    input=line.name,
                    reason=f"no gram conversion for {line.unit!r}; give the amount in g or oz",
                )
            )
            continue
        provenance = info.get("provenance") or {}
        matched.append(
            m.MatchedIngredient(
                input=line.name,
                matched_to=str(provenance.get("description") or info.get("name") or line.name),
                source="usda" if provenance else "local",
                grams=round(grams, 1),
            )
        )

    total = calculator.calculate_recipe_nutrition(_data_recipe(recipe))
    micros = {
        key: getattr(total.micronutrients, key, 0.0) / servings
        for key in NutritionCalculator.MICRONUTRIENT_FIELDS
    }
    return m.RecipeAnalysis(
        per_serving=m.PerServing(
            calories=round(total.calories / servings, 1),
            protein_g=round(total.protein_g / servings, 1),
            fat_g=round(total.fat_g / servings, 1),
            carbs_g=round(total.carbs_g / servings, 1),
            micronutrients=plain_names(micros),
        ),
        servings=servings,
        matched=matched,
        unmatched=unmatched,
        skipped=skipped,
        ready_for_planning=not unmatched,
    )


# --- Planning ------------------------------------------------------------------


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(err["msg"].removeprefix("Value error, ") for err in exc.errors())


def _recipe_pool(recipes: Sequence[m.Recipe], use_sample_recipes: bool) -> List[m.Recipe]:
    pool = list(recipes) + (list(_sample_recipes()) if use_sample_recipes else [])
    if not pool:
        raise InputError("Send at least one recipe, or set use_sample_recipes to true.")
    seen: set[str] = set()
    for recipe in pool:
        if recipe.id in seen:
            hint = " (the sample recipes use recipe_001…recipe_018)" if use_sample_recipes else ""
            raise InputError(f"Two recipes share the id {recipe.id!r}{hint}.")
        seen.add(recipe.id)
    return pool


def _schedule_days(schedule: Optional[m.Schedule], days: int) -> List[Dict[str, Any]]:
    """MCP schedule -> ``PlanRequest.schedule_days`` dicts. Both are 1-based."""
    if schedule is None:
        schedule = m.ShorthandSchedule(meals_per_day=3)
    if isinstance(schedule, m.ShorthandSchedule):
        n = schedule.meals_per_day
        levels = [schedule.busyness] * n if schedule.busyness else [2] + [3] * (n - 1)
        meals = []
        for i in range(n):
            meal: Dict[str, Any] = {"index": i + 1, "busyness_level": levels[i]}
            if n == len(_THREE_MEAL_LABELS):
                meal["tags"] = [_THREE_MEAL_LABELS[i]]
            meals.append(meal)
        return [{"day_index": d, "meals": [dict(x) for x in meals]} for d in range(1, days + 1)]

    if [d.day for d in schedule.days] != list(range(1, days + 1)):
        raise InputError(f"schedule.days must list days 1 to {days} in order, one entry each.")
    out = []
    for day in schedule.days:
        if [x.meal for x in day.meals] != list(range(1, len(day.meals) + 1)):
            raise InputError(f"Day {day.day}'s meals must be numbered 1 to {len(day.meals)} in order.")
        out.append(
            {
                "day_index": day.day,
                "meals": [
                    {
                        "index": x.meal,
                        "busyness_level": x.busyness,
                        "tags": [x.label] if x.label else None,
                        "preferred_time": x.time,
                        "required_tag_slugs": [_resolve_tag(t, f"day {day.day} meal {x.meal}").slug for t in x.required_tags] or None,
                        "preferred_tag_slugs": [_resolve_tag(t, f"day {day.day} meal {x.meal}").slug for t in x.preferred_tags] or None,
                    }
                    for x in day.meals
                ],
                "workouts": [
                    {"after_meal_index": w.after_meal, "type": w.type, "intensity": w.intensity}
                    for w in day.workouts
                ],
            }
        )
    return out


def _check_recipe_ids(ids: set[str], pins: Sequence[m.Pin], meal_prep: Sequence[m.MealPrep]) -> None:
    for pin in pins:
        if pin.recipe_id not in ids:
            raise InputError(f"Pinned recipe {pin.recipe_id!r} (day {pin.day}, meal {pin.meal}) isn't in the recipes.")
    for entry in meal_prep:
        if entry.recipe_id not in ids:
            raise InputError(f"Meal-prep recipe {entry.recipe_id!r} isn't in the recipes.")


def _plain_warnings(value: Any) -> Iterable[str]:
    """Flatten the API's ``warnings`` object into its human-readable strings."""
    if isinstance(value, str):
        if value.strip():
            yield value.strip()
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if key not in {"type", "code", "deprecated"}:
                yield from _plain_warnings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _plain_warnings(item)


def _failure(out: Mapping[str, Any]) -> Optional[m.Failure]:
    report = out.get("report") or {}
    failures = report.get("failures") or []
    if not failures and out.get("plan_status") == "success":
        return None
    first = failures[0] if failures else {}
    cause = report.get("failure_cause") or {}
    gap = cause.get("recipe_gap")
    return m.Failure(
        explanation=first.get("explanation") or out.get("plan_status_message") or "The planner couldn't complete the plan.",
        fix=first.get("fix"),
        where=m.Where(**failure_where(first)) if first else m.Where(),
        a_new_recipe_could_help=bool(cause.get("recipe_could_help")),
        recipe_gap=(
            m.RecipeGap(
                per_meal_calories=gap.get("per_meal_calories"),
                per_meal_protein_g=gap.get("per_meal_protein_g"),
                per_meal_fat_g_max=gap.get("per_meal_fat_g_max"),
                per_meal_carbs_g=gap.get("per_meal_carbs_g"),
                max_cooking_minutes=gap.get("cook_time_cap_minutes"),
                excluded_ingredients=list(gap.get("excluded_ingredients") or []),
                nutrient_minimums={
                    plain_name(k): round(float(v), 1) for k, v in (gap.get("nutrient_min_per_recipe") or {}).items()
                },
                meal_types=list(gap.get("meal_types") or []),
                meals=[m.Where(**w) for w in recipe_gap_slots(gap.get("slots") or [])],
            )
            if gap
            else None
        ),
        code=str(first.get("code") or out.get("termination_code") or "unknown"),
    )


def _planned_days(out: Mapping[str, Any], schedule_days: Sequence[Mapping[str, Any]]) -> List[m.PlannedDay]:
    days = []
    for plan in out.get("daily_plans") or []:
        slots = schedule_days[plan["day"] - 1]["meals"] if plan["day"] <= len(schedule_days) else []
        meals = []
        for row in plan.get("meals") or []:
            number = meal_number(row)
            slot = slots[number - 1] if number and number <= len(slots) else {}
            label = (slot.get("tags") or [None])[0] or row.get("meal_type")
            meals.append(
                m.PlannedMeal(
                    meal=number or 0,
                    label=label,
                    recipe_id=str(row.get("recipe_id")),
                    name=row.get("name"),
                    servings=float(row.get("servings") or 1.0),
                    source=_SOURCES.get(row.get("source") or "planner", "planner"),
                )
            )
        totals = plan.get("totals")
        days.append(
            m.PlannedDay(
                day=plan["day"],
                meals=meals,
                totals=m.DayTotals(**{k: totals[k] for k in ("calories", "protein_g", "fat_g", "carbs_g")}) if totals else None,
            )
        )
    return days


def _weekly_micronutrients(
    out: Mapping[str, Any], targets: m.Targets, days: int
) -> Dict[str, m.NutrientProgress]:
    if targets.demographic is None or not out.get("daily_plans"):
        return {}
    totals: Dict[str, float] = {}
    for plan in out.get("daily_plans") or []:
        for key, value in ((plan.get("totals") or {}).get("micronutrients") or {}).items():
            totals[key] = totals.get(key, 0.0) + float(value)
    progress = {}
    for key, daily in daily_rdis(targets.demographic).items():
        target = round(daily * days, 1)
        total = round(totals.get(key, 0.0), 1)
        progress[plain_name(key)] = m.NutrientProgress(total=total, target=target, met=total >= target)
    return progress


def _summary(status: str, days: Sequence[m.PlannedDay], requested_days: int, failure: Optional[m.Failure]) -> str:
    if status == "success":
        with_totals = [d.totals for d in days if d.totals]
        kcal = round(sum(t.calories for t in with_totals) / len(with_totals)) if with_totals else 0
        protein = round(sum(t.protein_g for t in with_totals) / len(with_totals)) if with_totals else 0
        noun = "day" if requested_days == 1 else "days"
        return f"Planned {requested_days} {noun} at about {kcal} kcal and {protein} g protein per day."
    reason = failure.explanation if failure else "the planner couldn't complete the plan."
    if status == "partial":
        if len(days) < requested_days:
            return f"Planned {len(days)} of {requested_days} days; the plan is incomplete. {reason}"
        return f"The plan is incomplete. {reason}"
    return f"No plan was possible. {reason}"


def _markdown(result: m.PlanResult) -> str:
    lines = [f"**{result.status.capitalize()}:** {result.summary}", ""]
    if result.days:
        lines += ["| Day | Meal | Recipe | Source |", "|---|---|---|---|"]
        for day in result.days:
            for meal in day.meals:
                label = f"{meal.meal} ({meal.label})" if meal.label else str(meal.meal)
                servings = f" ×{meal.servings:g}" if meal.servings != 1 else ""
                lines.append(f"| {day.day} | {label} | {meal.name or meal.recipe_id}{servings} | {meal.source} |")
            if day.totals:
                t = day.totals
                lines.append(
                    f"| {day.day} | **total** | {t.calories:.0f} kcal · {t.protein_g:.0f} g protein · "
                    f"{t.fat_g:.0f} g fat · {t.carbs_g:.0f} g carbs | |"
                )
        lines.append("")
    if result.failure:
        lines.append(f"**Why:** {result.failure.explanation}")
        if result.failure.fix:
            lines.append(f"**Fix:** {result.failure.fix}")
    unmet = [name for name, p in result.weekly_micronutrients.items() if not p.met]
    if unmet:
        lines.append(f"**Below target:** {', '.join(unmet)}")
    for warning in result.warnings:
        lines.append(f"- {warning}")
    return "\n".join(lines).strip()


def plan_meals(
    *,
    days: int,
    targets: m.Targets,
    preferences: Optional[m.Preferences] = None,
    schedule: Optional[m.Schedule] = None,
    recipes: Sequence[m.Recipe] = (),
    use_sample_recipes: bool = False,
    pins: Sequence[m.Pin] = (),
    meal_prep: Sequence[m.MealPrep] = (),
) -> Tuple[m.PlanResult, str]:
    """Plan ``days`` days. Returns the structured result and a Markdown rendering of it."""
    preferences = preferences or m.Preferences()
    pool = _recipe_pool(recipes, use_sample_recipes)
    _check_recipe_ids({r.id for r in pool}, pins, meal_prep)
    tag_data = _tag_data(pool)
    schedule_days = _schedule_days(schedule, days)

    try:
        request = PlanRequest(
            daily_calories=targets.daily_calories,
            daily_protein_g=targets.daily_protein_g,
            daily_fat_g_min=targets.daily_fat_g_min,
            daily_fat_g_max=targets.daily_fat_g_max,
            max_daily_calories=targets.max_daily_calories,
            days=days,
            schedule_days=schedule_days,
            liked_foods=preferences.liked_foods,
            allergies=preferences.excluded_ingredients,
            micronutrient_goals=daily_rdis(targets.demographic) if targets.demographic else None,
            micronutrient_weekly_min_fraction=1.0,
            planning_mode="deterministic",
        )
        user_profile, schedule_warnings = api._build_user_profile(request)
        meal_counts = [len(d["meals"]) for d in schedule_days]
        plan_pins = pins_from_mcp([p.model_dump() for p in pins], meal_counts)
        batches = batches_from_mcp([b.model_dump() for b in meal_prep], meal_counts)
    except ValidationError as exc:
        raise InputError(_validation_message(exc)) from exc
    except MacroTargetsError as exc:
        raise InputError(exc.message) from exc
    except SlotNumberError as exc:
        raise InputError(str(exc)) from exc

    inputs = build_plan_inputs(
        user_profile=user_profile,
        days=days,
        recipes=[_data_recipe(r) for r in pool],
        tag_data=tag_data,
        tag_preferences=request,
        provider=build_provider(),
        pins=plan_pins,
        batches=batches,
        keep_batch_recipes=True,
    )
    resolved_ul = upper_limits(targets.demographic) if targets.demographic else None
    planner_result = run_planner(inputs.planning_profile, inputs.recipe_pool, days, resolved_ul=resolved_ul)
    out = format_plan_response(
        planner_result, inputs, user_profile=user_profile, days=days, pins=plan_pins, batches=batches
    )
    merge_schedule_warnings_into_result(out, schedule_warnings)

    status = out["plan_status"]
    planned = _planned_days(out, schedule_days)
    failure = _failure(out) if status != "success" else None
    result = m.PlanResult(
        status=status,
        summary=_summary(status, planned, days, failure),
        requested_targets=targets,
        days=planned,
        weekly_micronutrients=_weekly_micronutrients(out, targets, days),
        warnings=list(dict.fromkeys(_plain_warnings(out.get("warnings") or {}))),
        failure=failure,
    )
    return result, _markdown(result)
