"""C4: tight multi-day micronutrient floor bounds — soundness and e2e.

Builds MB-067 / MB-068 / MB-071 the same way as evaluation/harness/run_benchmark.py
(PlanRequest → convert → stub nutrition → plan_meals).
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from pathlib import Path

import pytest

from src.api import server as S
from src.data_layer.meal_prep import MealPrepBatchRepository
from src.data_layer.models import (
    Ingredient,
    MicronutrientProfile,
    NutritionProfile,
    ProfilePin,
    Recipe,
)
from src.llm.tag_repository import (
    load_canonical_recipe_tag_slugs,
    load_hard_eligible_recipe_tag_slugs,
)
from src.planning.converters import convert_profile, convert_recipes
from src.planning.orchestrator import planning_batch_locks_from_batches
from src.planning.phase3_feasibility import (
    candidate_passes_micro_floor,
    precompute_micro_floor_bounds,
)
from src.planning.phase7_search import SearchStats
from src.planning.planner import plan_meals

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "evaluation" / "benchmark"
TAGS = str(BENCH / "recipe_tags.json")
LIB = json.load(open(BENCH / "recipes.json"))["recipes"]
LIB_BY = {r["id"]: r for r in LIB}
SCENARIOS = {s["id"]: s for s in json.load(open(BENCH / "scenarios.json"))["scenarios"]}
MICRO_FIELDS = {f.name for f in dataclasses.fields(MicronutrientProfile)}

# Oracle witness plans (evaluation/benchmark/oracle.py) for soundness checks.
ORACLE_WITNESS = {
    "MB-068": [
        ["bk_tofu_scramble", "ln_white_bean_soup", "dn_chickpea_curry"],
        ["dn_bean_quesadilla", "dn_veggie_pasta", "sn_edamame_cup"],
        ["bk_tofu_scramble", "ln_white_bean_soup", "dn_chickpea_curry"],
    ],
    "MB-071": [
        ["ln_tuna_poke", "ln_white_bean_soup", "dn_thigh_sheet_pan"],
        ["bk_cream_of_rice_whey", "dn_burger_bowl", "dn_salmon_potatoes"],
    ],
}


class _StubCalc:
    def calculate_recipe_nutrition(self, recipe):
        n = LIB_BY[recipe.id]["nutrition"]
        m = {k: v for k, v in n["micronutrients"].items() if k in MICRO_FIELDS}
        return NutritionProfile(
            n["calories"], n["protein_g"], n["fat_g"], n["carbs_g"], MicronutrientProfile(**m)
        )


def _data_recipe(r: dict) -> Recipe:
    ings = [
        Ingredient(
            name=i["name"],
            quantity=float(i["quantity"]),
            unit=i["unit"],
            normalized_unit="g",
            normalized_quantity=float(i["quantity"]),
        )
        for i in r["ingredients"]
    ]
    kw = dict(
        id=r["id"],
        name=r["name"],
        ingredients=ings,
        cooking_time_minutes=r["cooking_time_minutes"],
        instructions=[],
    )
    try:
        return Recipe(**kw)
    except TypeError:
        kw.pop("instructions")
        return Recipe(**kw)


def _build_scenario(sc: dict):
    """Mirror evaluation/harness/run_benchmark.py::run (without planning)."""
    os.environ["NUTRITION_TAG_REPO_PATH"] = TAGS
    p = sc["profile"]
    req = {
        "daily_calories": p["daily_calories"],
        "daily_protein_g": p["daily_protein_g"],
        "daily_fat_g_min": p["daily_fat_g"]["min"],
        "daily_fat_g_max": p["daily_fat_g"]["max"],
        "schedule_days": sc["schedule_days"],
        "days": sc["horizon_days"],
        "liked_foods": p.get("liked_foods", []),
        "disliked_foods": p.get("excluded_ingredients", []),
        "micronutrient_goals": p.get("micronutrient_targets") or None,
        "micronutrient_weekly_min_fraction": p.get("micronutrient_weekly_min_fraction", 1.0),
        "max_daily_calories": p.get("max_daily_calories"),
        "recipe_ids": sc["recipe_pool"]["recipe_ids"],
        "recipe_tags_path": TAGS,
    }
    preq = S.PlanRequest.model_validate(req)
    tmp = tempfile.mkdtemp()
    repo = MealPrepBatchRepository(os.path.join(tmp, "b.json"))
    pins = [
        ProfilePin(day_index=x["day_index"], slot_index=x["slot_index"], recipe_id=x["recipe_id"])
        for x in sc.get("pins") or []
    ]
    up, _ = S._build_user_profile(preq, persisted_pins=pins)
    up.pins = pins
    recipes = S._filter_recipes_by_ids([_data_recipe(r) for r in LIB], preq.recipe_ids)
    pool = convert_recipes(recipes, _StubCalc())
    S._attach_canonical_recipe_tags(
        pool,
        load_canonical_recipe_tag_slugs(TAGS),
        load_hard_eligible_recipe_tag_slugs(TAGS),
    )
    prof = convert_profile(up, preq.days)
    prof.batch_locks = planning_batch_locks_from_batches(repo.list_active())
    return prof, pool, preq.days


def _combo_micro(recipe_by_id, combo: list[str], nutrient: str) -> float:
    total = 0.0
    for rid in combo:
        micro = recipe_by_id[rid].nutrition.micronutrients
        if micro is None:
            continue
        total += float(getattr(micro, nutrient, 0.0) or 0.0)
    return total


@pytest.mark.parametrize("sid", ["MB-068", "MB-071"])
def test_per_slot_bound_never_rejects_oracle_witness(sid: str):
    """Soundness: every prefix of the oracle witness passes the per-slot floor check."""
    sc = SCENARIOS[sid]
    prof, pool, D = _build_scenario(sc)
    recipe_by_id = {r.id: r for r in pool}
    bounds = precompute_micro_floor_bounds(prof, pool, prof.schedule, D, None)
    assert bounds.tight is True
    witness = ORACLE_WITNESS[sid]
    tracked = list(prof.micronutrient_targets.keys())
    weekly = {n: 0.0 for n in tracked}
    for d, combo in enumerate(witness):
        for s, rid in enumerate(combo):
            prefix = tuple(combo[:s])
            assert candidate_passes_micro_floor(
                rid, d, prefix, weekly, prof, D, bounds
            ), f"{sid} day={d} slot={s} rid={rid} prefix={prefix}"
        for n in tracked:
            weekly[n] += _combo_micro(recipe_by_id, combo, n)


def test_mb067_presearch_fm4():
    sc = SCENARIOS["MB-067"]
    prof, pool, D = _build_scenario(sc)
    stats = SearchStats(enabled=True)
    res = plan_meals(prof, pool, D, attempt_limit=50_000, stats=stats)
    assert res.success is False
    assert res.failure_mode == "FM-4"
    assert stats.total_attempts == 0


@pytest.mark.parametrize("sid", ["MB-068", "MB-071"])
def test_feasible_floor_scenarios_succeed_within_default_budget(sid: str):
    sc = SCENARIOS[sid]
    prof, pool, D = _build_scenario(sc)
    stats = SearchStats(enabled=True)
    res = plan_meals(prof, pool, D, attempt_limit=50_000, stats=stats)
    assert res.success is True, f"{sid} failed: {res.failure_mode} attempts={stats.total_attempts}"
    assert stats.total_attempts < 50_000


def test_downscaling_uses_loose_bound_and_drops_nothing():
    sc = SCENARIOS["MB-068"]
    prof, pool, D = _build_scenario(sc)
    prof.enable_primary_carb_downscaling = True
    bounds = precompute_micro_floor_bounds(prof, pool, prof.schedule, D, None)
    assert bounds.tight is False
    assert all(not pm for pm in bounds.prefix_max)
    stats = SearchStats(enabled=True)
    # May or may not succeed with downscaling + floors; the contract under test is
    # that the loose path does not apply the per-slot prefix filter.
    plan_meals(prof, pool, D, attempt_limit=5_000, stats=stats)
    assert stats.floor_bound_candidates_dropped == 0
