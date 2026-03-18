import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.cli as cli
from src.api.server import app
from src.config.llm_settings import LLMSettings
from src.llm.client import LLMClient
from src.planning.phase10_reporting import MealPlanResult


class DummyRecipeDB:
    def __init__(self, *args, **kwargs):
        pass

    def get_all_recipes(self):
        return []


class DummyProvider:
    def resolve_all(self, ingredient_names):
        return None


def _plan_result_success():
    return MealPlanResult(
        success=True,
        termination_code="TC-1",
        plan=[],
        daily_trackers={},
        weekly_tracker=None,
        report={},
        stats={"attempts": 1, "backtracks": 0},
    )


@pytest.mark.parametrize("llm_enabled", [False, True])
def test_api_plan_feature_flag_routes(monkeypatch, llm_enabled):
    client = TestClient(app)

    monkeypatch.setattr("src.api.server.RecipeDB", DummyRecipeDB)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda _: DummyProvider())

    monkeypatch.setattr(
        "src.api.server.format_result_json",
        lambda result, recipe_by_id, profile, days: {"success": result.success},
    )

    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=llm_enabled,
        ),
    )

    monkeypatch.setattr("src.api.server.build_llm_client", lambda: object())
    monkeypatch.setattr("src.api.server.build_usda_provider", lambda: DummyProvider())

    called = {"plan_meals": 0, "orchestrator": 0}

    def _fake_plan_meals(*args, **kwargs):
        called["plan_meals"] += 1
        return _plan_result_success()

    def _fake_orchestrator(*args, **kwargs):
        called["orchestrator"] += 1
        return _plan_result_success()

    monkeypatch.setattr("src.api.server.plan_meals", _fake_plan_meals)
    monkeypatch.setattr("src.api.server.plan_with_llm_feedback", _fake_orchestrator)

    resp = client.post(
        "/api/plan",
        json={
            "daily_calories": 2400,
            "daily_protein_g": 150.0,
            "daily_fat_g_min": 50.0,
            "daily_fat_g_max": 100.0,
            "schedule": {"07:00": 2, "12:00": 3, "18:00": 3},
            "liked_foods": ["egg"],
            "disliked_foods": ["mushroom"],
            "allergies": [],
            "days": 1,
            "ingredient_source": "local",
            "micronutrient_goals": None,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    if llm_enabled:
        assert called["orchestrator"] == 1
        assert called["plan_meals"] == 0
    else:
        assert called["orchestrator"] == 0
        assert called["plan_meals"] == 1


def test_cli_feature_flag_routes_to_orchestrator_when_enabled(monkeypatch, tmp_path):
    recipes_path = tmp_path / "recipes.json"
    recipes_path.write_text(json.dumps({"recipes": []}), encoding="utf-8")

    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=True,
        ),
    )

    # Avoid hitting external providers in the "enabled" route.
    monkeypatch.setattr("src.cli.USDAClient.from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr("src.cli.CachedIngredientLookup", lambda usda_client: object())
    monkeypatch.setattr("src.cli.APIIngredientProvider", lambda cached_lookup: DummyProvider())
    monkeypatch.setattr("src.cli.LLMClient", lambda settings: object())

    monkeypatch.setattr("src.cli.RecipeDB", DummyRecipeDB)
    monkeypatch.setattr("src.cli.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.cli.LocalIngredientProvider", lambda _: DummyProvider())

    monkeypatch.setattr("src.cli.format_result_markdown", lambda *args, **kwargs: "")
    monkeypatch.setattr("src.cli.format_result_json_string", lambda *args, **kwargs: "{}")

    called = {"plan_meals": 0, "orchestrator": 0}

    monkeypatch.setattr(
        "src.cli.plan_with_llm_feedback",
        lambda *args, **kwargs: (called.update({"orchestrator": called["orchestrator"] + 1}) or _plan_result_success()),
    )
    monkeypatch.setattr(
        "src.cli.plan_meals",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("plan_meals should not be called when LLM enabled")
        ),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "cli.py",
            "--profile",
            "config/user_profile.yaml",
            "--recipes",
            str(recipes_path),
            "--ingredients",
            "data/ingredients/custom_ingredients.json",
            "--output",
            "json",
            "--ingredient-source",
            "local",
            "--days",
            "1",
        ],
    )

    cli.main()
    assert called["orchestrator"] == 1
    assert called["plan_meals"] == 0


def test_cli_feature_flag_routes_to_plan_meals_when_disabled(monkeypatch, tmp_path):
    recipes_path = tmp_path / "recipes.json"
    recipes_path.write_text(json.dumps({"recipes": []}), encoding="utf-8")

    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="",
            model="",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    monkeypatch.setattr("src.cli.RecipeDB", DummyRecipeDB)
    monkeypatch.setattr("src.cli.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.cli.LocalIngredientProvider", lambda _: DummyProvider())

    monkeypatch.setattr("src.cli.format_result_markdown", lambda *args, **kwargs: "")
    monkeypatch.setattr("src.cli.format_result_json_string", lambda *args, **kwargs: "{}")

    called = {"plan_meals": 0, "orchestrator": 0}

    monkeypatch.setattr(
        "src.cli.plan_meals",
        lambda *args, **kwargs: (called.update({"plan_meals": called["plan_meals"] + 1}) or _plan_result_success()),
    )
    monkeypatch.setattr(
        "src.cli.plan_with_llm_feedback",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("orchestrator should not be called when LLM disabled")),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "cli.py",
            "--profile",
            "config/user_profile.yaml",
            "--recipes",
            str(recipes_path),
            "--ingredients",
            "data/ingredients/custom_ingredients.json",
            "--output",
            "json",
            "--ingredient-source",
            "local",
            "--days",
            "1",
        ],
    )

    cli.main()
    assert called["plan_meals"] == 1
    assert called["orchestrator"] == 0

