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
    assert out["requested_targets"] == {**TARGETS, "max_daily_calories": None, "demographic": None}
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
    assert "vitamin D" in out["failure"]["explanation"]
    assert out["weekly_micronutrients"] == {}


def test_weekly_micronutrients_use_plain_names():
    out = {"daily_plans": [{"totals": {"micronutrients": {"iron_mg": 20.0}}}, {"totals": {"micronutrients": {"iron_mg": 17.0}}}]}
    targets = models.Targets(**TARGETS, demographic="adult_female")
    progress = tools._weekly_micronutrients(out, targets, days=2)
    assert progress["Iron (mg)"].model_dump() == {"total": 37.0, "target": 36.0, "met": True}
    assert progress["Vitamin C (mg)"].model_dump() == {"total": 0.0, "target": 150.0, "met": False}
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
            # No USDA portion weight for chia by the tbsp, so this unit stays unconvertible.
            {"name": "chia seeds", "quantity": 1, "unit": "tbsp, whole pieces"},
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


def test_list_tags_returns_registry_tags_only():
    tags = _call("macrova_list_tags", {}).structured_content["tags"]
    by_slug = {t["slug"]: t for t in tags}
    assert by_slug["breakfast"] == {"slug": "breakfast", "type": "context", "description": "Breakfast", "can_require": True}
    # A nutrition claim can rank recipes but can't be required.
    assert by_slug["high-calcium"]["can_require"] is False


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
