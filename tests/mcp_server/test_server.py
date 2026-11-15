"""The MCP tools end to end, through the SDK's in-memory client.

Nutrition comes from the bundled ingredient table, with USDA turned off and the
ingredient cache in a temp dir, so nothing here touches the network or user data.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

import anyio
import pytest
from mcp import Client, StdioServerParameters

from src.mcp_server import models, tools
from src.mcp_server.server import build_server

TARGETS = {"daily_calories": 2200, "daily_protein_g": 150, "daily_fat_g_min": 50, "daily_fat_g_max": 90}


def _recipe(rid: str, name: str, minutes: int, *ingredients: tuple, tags=()) -> Dict[str, Any]:
    return {
        "id": rid,
        "name": name,
        "cooking_time_minutes": minutes,
        "ingredients": [{"name": n, "quantity": q, "unit": "g"} for n, q in ingredients],
        "tags": list(tags),
    }


# Gram-based recipes from ingredients in data/reference/ingredient_nutrition.json.
RECIPES = [
    _recipe("eggs", "Egg scramble", 10, ("eggs", 150), ("spinach", 60), ("sourdough bread", 60), ("butter", 8), tags=["breakfast"]),
    _recipe("yogurt", "Yogurt bowl", 3, ("greek yogurt plain nonfat", 250), ("banana", 120), ("almonds", 20), ("honey", 15)),
    _recipe("cottage", "Cottage cheese plate", 2, ("cottage cheese 1% fat", 250), ("papaya", 150), ("chia seeds", 10)),
    _recipe("chicken", "Chicken rice bowl", 25, ("chicken breast", 200), ("jasmine rice in unsalted water", 250), ("bell pepper", 100), ("olive oil", 10)),
    _recipe("beef", "Beef quinoa bowl", 25, ("hamburger or beef 95%", 180), ("quinoa", 200), ("zucchini", 120), ("olive oil", 8)),
    _recipe("salmon", "Salmon potatoes", 30, ("salmon canned", 150), ("potatoes flesh", 250), ("asparagus", 120), ("olive oil", 8)),
    _recipe("tofu", "Tofu stir fry", 20, ("tofu not silken firm", 250), ("jasmine rice in unsalted water", 200), ("carrots", 80), ("sesame oil", 8)),
    _recipe("tuna", "Tuna pasta", 20, ("tuna sashimi", 150), ("pasta", 200), ("cherry tomatoes", 120), ("olive oil", 10)),
]


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    monkeypatch.setattr(tools, "INGREDIENT_CACHE_DIR", tmp_path / "ingredients")


def _call(name: str, arguments: Dict[str, Any]):
    async def run():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments)

    return anyio.run(run)


def _plan(**arguments):
    return _call("macrova_plan_meals", {"targets": TARGETS, "recipes": RECIPES, **arguments})


# --- Tool list ---------------------------------------------------------------


def test_lists_four_read_only_tools_with_output_schemas():
    async def run():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    by_name = {t.name: t for t in anyio.run(run)}
    assert sorted(by_name) == [
        "macrova_analyze_recipe",
        "macrova_get_sample_recipes",
        "macrova_list_tags",
        "macrova_plan_meals",
    ]
    for tool in by_name.values():
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.output_schema["type"] == "object"
    plan = by_name["macrova_plan_meals"]
    assert plan.output_schema["properties"]["status"]["enum"] == ["success", "partial", "failed"]
    assert plan.input_schema["properties"]["days"]["maximum"] == 7
    assert plan.input_schema["required"] == ["days", "targets"]
    # USDA is off, so no tool reaches outside the server.
    assert plan.annotations.open_world_hint is False


# --- macrova_plan_meals --------------------------------------------------------


def test_plan_succeeds_and_echoes_the_requested_targets():
    result = _plan(days=3)
    assert result.is_error is False
    out = result.structured_content
    assert out["status"] == "success"
    assert out["failure"] is None
    assert out["requested_targets"] == {
        **TARGETS,
        "max_daily_calories": None,
        "demographic": None,
        "micronutrient_goals": None,
        "micronutrient_weekly_min_fraction": None,
    }
    assert [d["day"] for d in out["days"]] == [1, 2, 3]
    for day in out["days"]:
        assert [meal["meal"] for meal in day["meals"]] == [1, 2, 3]
        assert [meal["label"] for meal in day["meals"]] == ["breakfast", "lunch", "dinner"]
        assert {meal["source"] for meal in day["meals"]} == {"planner"}
        assert 50 <= day["totals"]["fat_g"] <= 90
    assert out["summary"].startswith("Planned 3 days at about ")
    text = result.content[0].text
    assert text.startswith("**Success:**")
    assert "| Day | Meal | Recipe | Source |" in text


def test_failed_plan_is_a_result_not_an_error():
    result = _plan(
        days=1,
        targets={"daily_calories": 1200, "daily_protein_g": 250, "daily_fat_g_min": 20, "daily_fat_g_max": 40},
    )
    assert result.is_error is False
    out = result.structured_content
    assert out["status"] == "failed"
    assert out["days"] == []
    failure = out["failure"]
    assert failure["explanation"]
    assert failure["code"].startswith("FM-")
    assert out["summary"].startswith("No plan was possible.")
    assert "**Why:**" in result.content[0].text


def test_pins_and_meal_prep_come_back_at_the_same_day_and_meal():
    result = _plan(
        days=2,
        pins=[{"day": 2, "meal": 3, "recipe_id": "salmon"}],
        meal_prep=[
            {
                "recipe_id": "chicken",
                "total_servings": 2,
                "assignments": [{"day": 1, "meal": 2}, {"day": 2, "meal": 2}],
            }
        ],
    )
    assert result.is_error is False
    meals = {
        (day["day"], meal["meal"]): meal for day in result.structured_content["days"] for meal in day["meals"]
    }
    assert meals[(2, 3)]["recipe_id"] == "salmon"
    assert meals[(2, 3)]["source"] == "pin"
    assert meals[(1, 2)]["recipe_id"] == "chicken"
    assert meals[(1, 2)]["source"] == "meal_prep"


def test_full_schedule_reports_where_a_day_fails():
    # Day 2 has a single meal, which can't reach 2200 kcal on its own.
    schedule = {
        "days": [
            {"day": 1, "meals": [{"meal": 1, "busyness": 2, "label": "breakfast"}, {"meal": 2, "busyness": 3}, {"meal": 3, "busyness": 3}]},
            {"day": 2, "meals": [{"meal": 1, "busyness": 4, "label": "feast"}]},
        ]
    }
    result = _plan(days=2, schedule=schedule)
    assert result.is_error is False
    out = result.structured_content
    assert out["status"] == "partial"
    assert [d["day"] for d in out["days"]] == [1]
    assert [m["meal"] for m in out["days"][0]["meals"]] == [1, 2, 3]
    assert out["failure"]["where"]["day"] == 2
    assert out["summary"].startswith("Planned 1 of 2 days")


def test_demographic_sets_micronutrient_targets():
    # These recipes can't reach every RDI, so the plan fails and says which nutrients fall short.
    result = _plan(days=2, targets={**TARGETS, "demographic": "adult_female"})
    assert result.is_error is False
    out = result.structured_content
    assert out["requested_targets"]["demographic"] == "adult_female"
    assert out["status"] == "failed"
    # Vitamin D was named here until DATA-2 corrected its ~40x inflation: the
    # salmon, tuna and egg recipes then sat above the 4,000 IU UL and were lost.
    assert "vitamin E" in out["failure"]["explanation"]
    assert out["weekly_micronutrients"] == {}


def test_weekly_micronutrients_use_plain_names():
    out = {"daily_plans": [{"totals": {"micronutrients": {"iron_mg": 20.0}}}, {"totals": {"micronutrients": {"iron_mg": 17.0}}}]}
    goals = {"iron_mg": 18.0, "vitamin_c_mg": 75.0}
    progress = tools._weekly_micronutrients(out, goals, days=2)
    assert progress["Iron (mg)"].model_dump() == {"total": 37.0, "target": 36.0, "minimum": 36.0, "met": True}
    assert progress["Vitamin C (mg)"].model_dump() == {"total": 0.0, "target": 150.0, "minimum": 150.0, "met": False}
    assert all("_" not in name for name in progress)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"days": 10}, "less than or equal to 7"),
        ({"days": 2, "recipes": []}, "Send at least one recipe"),
        ({"days": 2, "pins": [{"day": 1, "meal": 1, "recipe_id": "nope"}]}, "isn't in the recipes"),
        ({"days": 2, "pins": [{"day": 1, "meal": 4, "recipe_id": "tofu"}]}, "day 1 has 3 meals; there is no meal 4"),
        ({"days": 2, "pins": [{"day": 3, "meal": 1, "recipe_id": "tofu"}]}, "outside the 2-day plan"),
        ({"days": 2, "recipes": RECIPES + [RECIPES[0]]}, "Two recipes share the id"),
        ({"days": 1, "recipes": [{**RECIPES[0], "tags": ["made-up-tag"]}]}, "Unknown tag 'made-up-tag'"),
        ({"days": 1, "schedule": {"days": [{"day": 2, "meals": [{"meal": 1, "busyness": 2}]}]}}, "must list days 1 to 1"),
        ({"days": 1, "targets": {**TARGETS, "daily_fat_g_min": 95, "daily_fat_g_max": 90}}, "must not exceed"),
        ({"days": 1, "use_sample_recipes": True, "recipes": [{**RECIPES[0], "id": "recipe_001"}]}, "recipe_001…recipe_018"),
    ],
)
def test_bad_input_is_an_error(arguments, message):
    result = _plan(**arguments)
    assert result.is_error is True
    assert message in result.content[0].text


def test_no_llm_client_is_built(monkeypatch):
    from src.api import server as api
    from src.llm import client as llm_client

    def refuse(*_args, **_kwargs):
        raise AssertionError("the MCP server must not build an LLM client")

    monkeypatch.setattr(api, "build_llm_client", refuse)
    monkeypatch.setattr(llm_client.LLMClient, "__init__", refuse)
    assert _plan(days=1).is_error is False
    assert _call("macrova_analyze_recipe", {"recipe": RECIPES[0]}).is_error is False


# --- The other tools -----------------------------------------------------------


def test_analyze_recipe_reports_matches_and_gaps():
    recipe = {
        "id": "draft",
        "name": "Draft bowl",
        "ingredients": [
            {"name": "chicken breast", "quantity": 400, "unit": "g"},
            # No weight for chia by the cup (only g and tbsp), so this unit stays unconvertible.
            {"name": "chia seeds", "quantity": 1, "unit": "cup"},
            {"name": "everything bagel seasoning", "quantity": 5, "unit": "g"},
            {"name": "salt", "quantity": 1, "unit": "to taste"},
        ],
    }
    result = _call("macrova_analyze_recipe", {"recipe": recipe, "servings": 2})
    assert result.is_error is False
    out = result.structured_content
    assert out["servings"] == 2
    assert [(row["input"], row["source"], row["grams"]) for row in out["matched"]] == [("chicken breast", "local", 400.0)]
    assert {row["input"] for row in out["unmatched"]} == {"chia seeds", "everything bagel seasoning"}
    assert out["skipped"] == ["salt"]
    assert out["ready_for_planning"] is False
    # 400 g chicken breast split over 2 servings.
    assert 200 <= out["per_serving"]["calories"] <= 260
    assert all("_" not in name for name in out["per_serving"]["micronutrients"])


def test_sample_recipes_carry_valid_tags():
    samples = _call("macrova_get_sample_recipes", {}).structured_content["recipes"]
    tags = {t["slug"] for t in _call("macrova_list_tags", {}).structured_content["tags"]}
    assert [r["id"] for r in samples] == [f"recipe_{n:03d}" for n in range(1, 19)]
    for recipe in samples:
        assert set(recipe["tags"]) <= tags
        assert (recipe["per_serving_calories"] is None) == bool(recipe["unmatched"])
        assert recipe["ready_for_planning"] is not bool(recipe["unmatched"])


def test_sample_recipes_ready_for_planning():
    """DATA-1: all 18 samples plan (FDC portions, plus Cronometer NCCDB servings where FDC has none)."""
    samples = _call("macrova_get_sample_recipes", {}).structured_content["recipes"]
    assert [r["name"] for r in samples if not r["ready_for_planning"]] == []
    assert len(samples) == 18


def test_list_tags_returns_registry_tags_only():
    tags = _call("macrova_list_tags", {}).structured_content["tags"]
    by_slug = {t["slug"]: t for t in tags}
    assert by_slug["breakfast"] == {"slug": "breakfast", "type": "context", "description": "Breakfast", "can_require": True}
    # A nutrition claim can rank recipes but can't be required.
    assert by_slug["high-calcium"]["can_require"] is False


# --- BE-20: demo micronutrient default (D-A), override, busyness 2/3/4 (D-B) -----

DEMO_TARGETS = {"daily_calories": 2400, "daily_protein_g": 150, "daily_fat_g_min": 50, "daily_fat_g_max": 100}


def _sample_plan(targets: Dict[str, Any], days: int = 7, **arguments):
    return _call(
        "macrova_plan_meals",
        {"days": days, "targets": targets, "use_sample_recipes": True, "schedule": {"meals_per_day": 3}, **arguments},
    )


def test_sample_recipes_with_demographic_default_plan_seven_days():
    """Failed before BE-20: all 25 RDIs at τ = 1.0 (FM-4)."""
    result = _sample_plan({**DEMO_TARGETS, "demographic": "adult_male"})
    assert result.is_error is False
    out = result.structured_content
    assert out["status"] == "success", out["failure"]
    assert len(out["days"]) == 7
    assert "Omega-3 (ALA) (g)" not in out["weekly_micronutrients"]
    assert "Vitamin C (mg)" in out["weekly_micronutrients"]


def test_default_warning_names_left_out_nutrients_and_the_override():
    out = _sample_plan({**DEMO_TARGETS, "demographic": "adult_male"}).structured_content
    warning = out["warnings"][0]
    assert warning.startswith("The default micronutrient goals for adult_male leave out ")
    assert "the bundled sample recipes can't meet them" in warning
    assert "Omega-3 (ALA) (g) and Omega-6 (linoleic acid) (g)" in warning
    assert "targets.micronutrient_goals" in warning
    assert '"omega_3_g": <daily amount>' in warning


@pytest.mark.parametrize("goals", [{}, {"iron_mg": 8}])
def test_no_left_out_warning_when_the_user_sends_goals(goals):
    out = _sample_plan({**DEMO_TARGETS, "demographic": "adult_male", "micronutrient_goals": goals}).structured_content
    assert not any("targets.micronutrient_goals" in w for w in out["warnings"])


def test_no_left_out_warning_without_a_demographic():
    out = _sample_plan(DEMO_TARGETS, days=1).structured_content
    assert not any("targets.micronutrient_goals" in w for w in out["warnings"])


def test_override_restores_a_left_out_nutrient():
    targets = models.Targets(**DEMO_TARGETS, demographic="adult_male", micronutrient_goals={"omega_3_g": 1.6})
    goals, left_out = tools._micronutrient_goals(targets)
    assert goals["omega_3_g"] == 1.6
    assert goals["vitamin_c_mg"] == 90.0  # the rest of the default stays
    assert left_out == ()
    out = _sample_plan(
        {**DEMO_TARGETS, "demographic": "adult_male", "micronutrient_goals": {"omega_3_g": 1.6}}, days=2
    ).structured_content
    # The sample recipes can't meet omega-3 at the full target; the failure says so.
    assert out["status"] != "success"
    assert "omega" in out["failure"]["explanation"].lower()


def test_override_replaces_a_value_and_zero_removes_it():
    targets = models.Targets(
        **DEMO_TARGETS, demographic="adult_male", micronutrient_goals={"iron_mg": 12, "calcium_mg": 0}
    )
    goals, _ = tools._micronutrient_goals(targets)
    assert goals["iron_mg"] == 12.0
    assert "calcium_mg" not in goals
    empty, _ = tools._micronutrient_goals(models.Targets(**DEMO_TARGETS, demographic="adult_male", micronutrient_goals={}))
    assert empty == {}


def test_override_lowers_tau(monkeypatch):
    seen: Dict[str, Any] = {}
    real = tools.run_planner

    def _spy(profile, pool, days, **kwargs):
        seen["tau"] = profile.micronutrient_weekly_min_fraction
        return real(profile, pool, days, **kwargs)

    monkeypatch.setattr(tools, "run_planner", _spy)
    _sample_plan({**DEMO_TARGETS, "demographic": "adult_male", "micronutrient_weekly_min_fraction": 0.5}, days=1)
    assert seen["tau"] == 0.5
    _sample_plan({**DEMO_TARGETS, "demographic": "adult_male"}, days=1)
    assert seen["tau"] == 1.0


@pytest.mark.parametrize(
    ("targets", "message"),
    [
        ({**DEMO_TARGETS, "micronutrient_goals": {"vitamin_z_mg": 5}}, "Unknown micronutrient 'vitamin_z_mg'"),
        ({**DEMO_TARGETS, "micronutrient_goals": {"iron_mg": -1}}, "greater than or equal to 0"),
        ({**DEMO_TARGETS, "micronutrient_weekly_min_fraction": 0}, "greater than 0"),
        ({**DEMO_TARGETS, "micronutrient_weekly_min_fraction": 1.5}, "less than or equal to 1"),
    ],
)
def test_bad_micronutrient_override_is_an_error(targets, message):
    result = _sample_plan(targets, days=1)
    assert result.is_error is True
    assert message in result.content[0].text
    if "Unknown" in message:
        assert "Use these keys: vitamin_a_ug" in result.content[0].text


def test_shorthand_default_busyness_is_2_3_4():
    """Failed before BE-20: [2, 3, 3]."""
    days = tools._schedule_days(models.ShorthandSchedule(meals_per_day=3), 2)
    for day in days:
        assert [m["busyness_level"] for m in day["meals"]] == [2, 3, 4]
    omitted = tools._schedule_days(None, 1)
    assert [m["busyness_level"] for m in omitted[0]["meals"]] == [2, 3, 4]


@pytest.mark.parametrize(
    ("meals", "levels"),
    [(1, [2]), (2, [2, 4]), (3, [2, 3, 4]), (4, [2, 3, 3, 4]), (5, [2, 3, 3, 3, 4])],
)
def test_shorthand_default_busyness_rule_for_other_meal_counts(meals, levels):
    (day,) = tools._schedule_days(models.ShorthandSchedule(meals_per_day=meals), 1)
    assert [m["busyness_level"] for m in day["meals"]] == levels


def test_explicit_shorthand_busyness_still_applies_to_every_meal():
    (day,) = tools._schedule_days(models.ShorthandSchedule(meals_per_day=3, busyness=1), 1)
    assert [m["busyness_level"] for m in day["meals"]] == [1, 1, 1]


def test_tool_schema_describes_the_new_fields_and_2_3_4():
    async def run():
        async with Client(build_server()) as client:
            return {t.name: t for t in (await client.list_tools()).tools}["macrova_plan_meals"]

    plan = anyio.run(run)
    assert "2/3/4" in plan.input_schema["properties"]["schedule"]["description"]
    targets = plan.input_schema["$defs"]["Targets"]["properties"]
    assert "micronutrient_goals" in targets and "micronutrient_weekly_min_fraction" in targets
    assert "Targets" not in plan.input_schema["required"]


# --- BE-20 follow-ups (planner-invariant review) ---------------------------------


def _targets(**extra) -> models.Targets:
    return models.Targets(**DEMO_TARGETS, **extra)


def test_goal_above_the_daily_upper_limit_is_an_error():
    """tau × goal above the daily UL can never be met (adult iron UL is 45 mg)."""
    with pytest.raises(tools.InputError) as err:
        tools._micronutrient_goals(_targets(demographic="adult_male", micronutrient_goals={"iron_mg": 100}))
    message = str(err.value)
    for part in ("Iron (mg)", "iron_mg", "100", "1.0", "45"):
        assert part in message, (part, message)
    # Through the tool it's a plain-language error, not a failed plan.
    result = _sample_plan({**DEMO_TARGETS, "demographic": "adult_male", "micronutrient_goals": {"iron_mg": 100}}, days=1)
    assert result.is_error is True
    assert "upper limit" in result.content[0].text


def test_goal_under_the_upper_limit_after_tau_is_allowed():
    goals, _ = tools._micronutrient_goals(
        _targets(demographic="adult_male", micronutrient_goals={"iron_mg": 100}, micronutrient_weekly_min_fraction=0.4)
    )
    assert goals["iron_mg"] == 100.0  # 0.4 × 100 = 40 mg ≤ 45 mg


def test_null_upper_limit_and_no_demographic_skip_the_check():
    # Magnesium's UL is null (supplement-only); without a demographic there are no ULs.
    goals, _ = tools._micronutrient_goals(_targets(demographic="adult_male", micronutrient_goals={"magnesium_mg": 5000}))
    assert goals["magnesium_mg"] == 5000.0
    goals, _ = tools._micronutrient_goals(_targets(micronutrient_goals={"iron_mg": 100}))
    assert goals == {"iron_mg": 100.0}


def test_default_goals_pass_the_upper_limit_check():
    from src.data_layer.upper_limits import DEMOGRAPHICS, default_micronutrient_goals

    for demographic in DEMOGRAPHICS:
        goals, _ = tools._micronutrient_goals(_targets(demographic=demographic))
        assert goals == default_micronutrient_goals(demographic)


def test_weekly_progress_is_met_at_the_tau_minimum():
    """Failed before: met compared against the full target, ignoring tau."""
    out = {"daily_plans": [{"totals": {"micronutrients": {"iron_mg": 10.0}}}, {"totals": {"micronutrients": {"iron_mg": 9.0}}}]}
    progress = tools._weekly_micronutrients(out, {"iron_mg": 18.0, "vitamin_c_mg": 75.0}, days=2, tau=0.5)
    assert progress["Iron (mg)"].model_dump() == {"total": 19.0, "target": 36.0, "minimum": 18.0, "met": True}
    assert progress["Vitamin C (mg)"].model_dump() == {"total": 0.0, "target": 150.0, "minimum": 75.0, "met": False}


def test_successful_low_tau_plan_reports_every_goal_met():
    result = _sample_plan({**DEMO_TARGETS, "demographic": "adult_male", "micronutrient_weekly_min_fraction": 0.5}, days=3)
    out = result.structured_content
    assert out["status"] == "success", out["failure"]
    assert out["weekly_micronutrients"]
    for name, progress in out["weekly_micronutrients"].items():
        assert progress["met"] is True, name
        assert progress["minimum"] == pytest.approx(0.5 * progress["target"], abs=0.1), name
    assert "Below" not in result.content[0].text


def test_goal_order_follows_nutrient_keys_not_json_order():
    """Failed before: the merged dict kept the request's key order."""
    a, _ = tools._micronutrient_goals(_targets(micronutrient_goals={"zinc_mg": 11, "iron_mg": 8, "vitamin_c_mg": 90}))
    b, _ = tools._micronutrient_goals(_targets(micronutrient_goals={"vitamin_c_mg": 90, "zinc_mg": 11, "iron_mg": 8}))
    assert list(a) == list(b) == ["vitamin_c_mg", "iron_mg", "zinc_mg"]
    c, _ = tools._micronutrient_goals(
        _targets(demographic="adult_male", micronutrient_goals={"omega_6_g": 17, "omega_3_g": 1.6, "calcium_mg": 1200})
    )
    assert list(c) == [k for k in tools.NUTRIENT_KEYS if k in c]
    goals = lambda order: {k: {"zinc_mg": 11, "iron_mg": 8, "vitamin_c_mg": 90}[k] for k in order}  # noqa: E731
    first = _plan(days=1, targets={**TARGETS, "micronutrient_goals": goals(["zinc_mg", "iron_mg", "vitamin_c_mg"])})
    second = _plan(days=1, targets={**TARGETS, "micronutrient_goals": goals(["vitamin_c_mg", "iron_mg", "zinc_mg"])})
    one, two = first.structured_content, second.structured_content
    assert one["days"] == two["days"]
    assert list(one["weekly_micronutrients"]) == list(two["weekly_micronutrients"])


def test_left_out_warning_names_sample_recipes_only_when_they_are_used():
    out = _plan(days=1, targets={**TARGETS, "demographic": "adult_male"}).structured_content
    (warning,) = [w for w in out["warnings"] if "targets.micronutrient_goals" in w]
    assert "sample recipes" not in warning
    assert "Omega-3 (ALA) (g) and Omega-6 (linoleic acid) (g) were left out of the default goals for adult_male" in warning
    assert "To plan for them anyway, add them to targets.micronutrient_goals" in warning
    assert tools._left_out_warning("adult_male", (), use_sample_recipes=False) is None


# --- Transport -----------------------------------------------------------------


def test_stdio_server_starts_from_any_directory(tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp_server"],
        cwd=str(tmp_path),
        env={**os.environ, "PYTHONPATH": str(tools.ROOT), "USDA_API_KEY": ""},
    )

    async def run():
        async with Client(params) as client:
            names = [t.name for t in (await client.list_tools()).tools]
            tags = await client.call_tool("macrova_list_tags", {})
            return names, tags

    names, tags = anyio.run(run)
    assert "macrova_plan_meals" in names
    assert tags.is_error is False
