from types import SimpleNamespace

import json
import pytest
from fastapi.testclient import TestClient

import src.cli as cli
from src.api.server import app
from src.config.llm_settings import LLMSettings
from src.llm.schemas import (
    BudgetLevel,
    DietaryFlag,
    PrepTimeBucket,
    RecipeTagsJson,
)
from src.planning.phase10_reporting import MealPlanResult


def _tags(*, cuisine: str) -> RecipeTagsJson:
    return RecipeTagsJson(
        cuisine=cuisine,
        cost_level=BudgetLevel.cheap,
        prep_time_bucket=PrepTimeBucket.quick_meal,
        dietary_flags=[DietaryFlag.vegan],
    )


class DummyRecipeDB:
    def __init__(self, recipes):
        self._recipes = recipes

    def get_all_recipes(self):
        return list(self._recipes)


class DummyProvider:
    def resolve_all(self, ingredient_names):
        return None


def _base_plan_payload(*, planning_mode: str = "deterministic"):
    return {
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
        "planning_mode": planning_mode,
    }


@pytest.mark.parametrize(
    "scenario,tags_by_id,request_overrides,expected_recipe_ids",
    [
        (
            "reduces_pool",
            {"r1": _tags(cuisine="italian"), "r2": _tags(cuisine="mexican")},
            {"cuisine": ["mexican"]},
            ["r2"],
        ),
        (
            "no_preferences",
            {"r1": _tags(cuisine="italian"), "r2": _tags(cuisine="mexican")},
            {},
            ["r1", "r2"],
        ),
        (
            "missing_tags_fallback_full_pool",
            {},
            {"cuisine": ["mexican"]},
            ["r1", "r2"],
        ),
        (
            "empty_filter_result_fallback_full_pool",
            {"r1": _tags(cuisine="italian"), "r2": _tags(cuisine="italian")},
            {"cuisine": ["mexican"]},
            ["r1", "r2"],
        ),
        (
            "preserves_recipe_db_order",
            {"r1": _tags(cuisine="shared"), "r2": _tags(cuisine="shared")},
            {"cuisine": ["shared"]},
            ["r2", "r1"],
        ),
    ],
)
def test_api_plan_tag_filtering_applied_pre_conversion(
    monkeypatch,
    scenario,
    tags_by_id,
    request_overrides,
    expected_recipe_ids,
):
    # Recipe DB order matters for determinism: in the ordering test, we
    # intentionally return recipes in the reverse order.
    recipes = (
        [SimpleNamespace(id="r2"), SimpleNamespace(id="r1")]
        if scenario == "preserves_recipe_db_order"
        else [SimpleNamespace(id="r1"), SimpleNamespace(id="r2")]
    )

    monkeypatch.setattr("src.api.server.RecipeDB", lambda _: DummyRecipeDB(recipes))
    monkeypatch.setattr("src.api.server.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda _: DummyProvider())

    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    monkeypatch.setattr("src.api.server.load_recipe_tags", lambda _: tags_by_id)

    seen = {}

    def fake_extract_ingredient_names(recipes_in):
        seen["extract_ids"] = [r.id for r in recipes_in]
        return ["ingredient-x"]

    def fake_convert_recipes(recipes_in, _calculator):
        seen["convert_ids"] = [r.id for r in recipes_in]
        return [SimpleNamespace(id=r.id) for r in recipes_in]

    monkeypatch.setattr("src.api.server.extract_ingredient_names", fake_extract_ingredient_names)
    monkeypatch.setattr("src.api.server.convert_recipes", fake_convert_recipes)
    monkeypatch.setattr("src.api.server.NutritionCalculator", lambda _provider: object())

    monkeypatch.setattr(
        "src.api.server.plan_meals",
        lambda _profile, _pool, _days: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        ),
    )
    monkeypatch.setattr(
        "src.api.server.format_result_json",
        lambda _result, _recipe_by_id, _profile, _days: {"ok": True},
    )

    client = TestClient(app)
    payload = _base_plan_payload()
    payload.update(request_overrides)
    resp = client.post("/api/plan", json=payload)

    assert resp.status_code == 200
    assert seen["extract_ids"] == expected_recipe_ids
    assert seen["convert_ids"] == expected_recipe_ids


def _write_simple_recipe_store(path):
    # Two minimal recipes, just enough for `RecipeDB` parsing.
    path.write_text(
        """
{
  "recipes": [
    {
      "id": "r1",
      "name": "Recipe 1",
      "cooking_time_minutes": 10,
      "instructions": ["Step"],
      "ingredients": [
        {"name": "chicken", "quantity": 100.0, "unit": "g"}
      ]
    },
    {
      "id": "r2",
      "name": "Recipe 2",
      "cooking_time_minutes": 10,
      "instructions": ["Step"],
      "ingredients": [
        {"name": "beef", "quantity": 100.0, "unit": "g"}
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )


def _write_simple_recipe_store_ordered(path, recipe_ids: list[str]) -> None:
    recipes_by_id = {
        "r1": {
            "id": "r1",
            "name": "Recipe 1",
            "cooking_time_minutes": 10,
            "instructions": ["Step"],
            "ingredients": [{"name": "chicken", "quantity": 100.0, "unit": "g"}],
        },
        "r2": {
            "id": "r2",
            "name": "Recipe 2",
            "cooking_time_minutes": 10,
            "instructions": ["Step"],
            "ingredients": [{"name": "beef", "quantity": 100.0, "unit": "g"}],
        },
    }

    path.write_text(
        json.dumps({"recipes": [recipes_by_id[rid] for rid in recipe_ids]}),
        encoding="utf-8",
    )


def test_cli_tag_filtering_reduces_recipe_pool(monkeypatch, tmp_path, capsys):
    recipes_path = tmp_path / "recipes.json"
    _write_simple_recipe_store(recipes_path)

    ingredients_path = tmp_path / "ingredients.json"
    ingredients_path.write_text("{}", encoding="utf-8")

    tag_path = tmp_path / "tags.json"
    tag_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("src.cli.NutritionDB", lambda _: object())
    monkeypatch.setattr(
        "src.cli.LocalIngredientProvider", lambda _: DummyProvider()
    )
    monkeypatch.setattr("src.cli.UpperLimitsLoader", lambda *_: object())
    monkeypatch.setattr("src.cli.resolve_upper_limits", lambda *_args, **_kwargs: {})

    monkeypatch.setattr("src.cli.NutritionCalculator", lambda _provider: object())

    monkeypatch.setattr("src.cli.load_recipe_tags", lambda _: {
        "r1": _tags(cuisine="italian"),
        "r2": _tags(cuisine="mexican"),
    })

    seen = {}

    def fake_extract_ingredient_names(recipes_in):
        seen["extract_ids"] = [r.id for r in recipes_in]
        return ["ingredient-x"]

    def fake_convert_recipes(recipes_in, _calculator):
        seen["convert_ids"] = [r.id for r in recipes_in]
        return [SimpleNamespace(id=r.id) for r in recipes_in]

    monkeypatch.setattr("src.cli.extract_ingredient_names", fake_extract_ingredient_names)
    monkeypatch.setattr("src.cli.convert_recipes", fake_convert_recipes)

    monkeypatch.setattr(
        "src.cli.plan_meals",
        lambda _profile, _pool, _days: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        ),
    )

    monkeypatch.setattr("src.cli.format_result_json_string", lambda *_args, **_kwargs: "{}")
    monkeypatch.setattr("src.cli.format_result_markdown", lambda *_args, **_kwargs: "")

    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "cli.py",
            "--profile",
            "config/user_profile.yaml",
            "--recipes",
            str(recipes_path),
            "--ingredients",
            str(ingredients_path),
            "--output",
            "json",
            "--planning-mode",
            "deterministic",
            "--cuisine",
            "mexican",
            "--recipe-tags-path",
            str(tag_path),
        ],
    )

    cli.main()
    _ = capsys.readouterr()

    assert seen["extract_ids"] == ["r2"]
    assert seen["convert_ids"] == ["r2"]


def test_cli_tag_filtering_no_preferences_keeps_full_pool(
    monkeypatch, tmp_path, capsys
):
    recipes_path = tmp_path / "recipes.json"
    _write_simple_recipe_store(recipes_path)

    ingredients_path = tmp_path / "ingredients.json"
    ingredients_path.write_text("{}", encoding="utf-8")

    tag_path = tmp_path / "tags.json"
    tag_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("src.cli.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.cli.LocalIngredientProvider", lambda _: DummyProvider())
    monkeypatch.setattr("src.cli.UpperLimitsLoader", lambda *_: object())
    monkeypatch.setattr("src.cli.resolve_upper_limits", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("src.cli.NutritionCalculator", lambda _provider: object())

    monkeypatch.setattr(
        "src.cli.load_recipe_tags",
        lambda _: {
            "r1": _tags(cuisine="italian"),
            "r2": _tags(cuisine="mexican"),
        },
    )

    seen = {}

    def fake_extract_ingredient_names(recipes_in):
        seen["extract_ids"] = [r.id for r in recipes_in]
        return ["ingredient-x"]

    def fake_convert_recipes(recipes_in, _calculator):
        seen["convert_ids"] = [r.id for r in recipes_in]
        return [SimpleNamespace(id=r.id) for r in recipes_in]

    monkeypatch.setattr("src.cli.extract_ingredient_names", fake_extract_ingredient_names)
    monkeypatch.setattr("src.cli.convert_recipes", fake_convert_recipes)

    monkeypatch.setattr(
        "src.cli.plan_meals",
        lambda _profile, _pool, _days: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        ),
    )
    monkeypatch.setattr("src.cli.format_result_json_string", lambda *_args, **_kwargs: "{}")
    monkeypatch.setattr("src.cli.format_result_markdown", lambda *_args, **_kwargs: "")

    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "cli.py",
            "--profile",
            "config/user_profile.yaml",
            "--recipes",
            str(recipes_path),
            "--ingredients",
            str(ingredients_path),
            "--output",
            "json",
            "--planning-mode",
            "deterministic",
            "--recipe-tags-path",
            str(tag_path),
        ],
    )

    cli.main()
    _ = capsys.readouterr()

    assert seen["extract_ids"] == ["r1", "r2"]
    assert seen["convert_ids"] == ["r1", "r2"]


def test_cli_tag_filtering_missing_tags_fallback_full_pool(
    monkeypatch, tmp_path, capsys
):
    recipes_path = tmp_path / "recipes.json"
    _write_simple_recipe_store(recipes_path)

    ingredients_path = tmp_path / "ingredients.json"
    ingredients_path.write_text("{}", encoding="utf-8")

    tag_path = tmp_path / "tags.json"
    tag_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("src.cli.NutritionDB", lambda _: object())
    monkeypatch.setattr(
        "src.cli.LocalIngredientProvider", lambda _: DummyProvider()
    )
    monkeypatch.setattr("src.cli.UpperLimitsLoader", lambda *_: object())
    monkeypatch.setattr("src.cli.resolve_upper_limits", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("src.cli.NutritionCalculator", lambda _provider: object())

    # Simulate "all tags missing" -> fallback to full recipe pool.
    monkeypatch.setattr("src.cli.load_recipe_tags", lambda _: {})

    seen = {}

    def fake_extract_ingredient_names(recipes_in):
        seen["extract_ids"] = [r.id for r in recipes_in]
        return ["ingredient-x"]

    def fake_convert_recipes(recipes_in, _calculator):
        seen["convert_ids"] = [r.id for r in recipes_in]
        return [SimpleNamespace(id=r.id) for r in recipes_in]

    monkeypatch.setattr("src.cli.extract_ingredient_names", fake_extract_ingredient_names)
    monkeypatch.setattr("src.cli.convert_recipes", fake_convert_recipes)

    monkeypatch.setattr(
        "src.cli.plan_meals",
        lambda _profile, _pool, _days: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        ),
    )

    monkeypatch.setattr("src.cli.format_result_json_string", lambda *_args, **_kwargs: "{}")
    monkeypatch.setattr("src.cli.format_result_markdown", lambda *_args, **_kwargs: "")

    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "cli.py",
            "--profile",
            "config/user_profile.yaml",
            "--recipes",
            str(recipes_path),
            "--ingredients",
            str(ingredients_path),
            "--output",
            "json",
            "--planning-mode",
            "deterministic",
            "--cuisine",
            "mexican",
            "--recipe-tags-path",
            str(tag_path),
        ],
    )

    cli.main()
    _ = capsys.readouterr()

    assert seen["extract_ids"] == ["r1", "r2"]
    assert seen["convert_ids"] == ["r1", "r2"]


def test_cli_tag_filtering_empty_filter_result_fallback_full_pool(
    monkeypatch, tmp_path, capsys
):
    recipes_path = tmp_path / "recipes.json"
    _write_simple_recipe_store(recipes_path)

    ingredients_path = tmp_path / "ingredients.json"
    ingredients_path.write_text("{}", encoding="utf-8")

    tag_path = tmp_path / "tags.json"
    tag_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("src.cli.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.cli.LocalIngredientProvider", lambda _: DummyProvider())
    monkeypatch.setattr("src.cli.UpperLimitsLoader", lambda *_: object())
    monkeypatch.setattr("src.cli.resolve_upper_limits", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("src.cli.NutritionCalculator", lambda _provider: object())

    # Tags are present, but none match the requested cuisine => fallback.
    monkeypatch.setattr(
        "src.cli.load_recipe_tags",
        lambda _: {
            "r1": _tags(cuisine="italian"),
            "r2": _tags(cuisine="italian"),
        },
    )

    seen = {}

    def fake_extract_ingredient_names(recipes_in):
        seen["extract_ids"] = [r.id for r in recipes_in]
        return ["ingredient-x"]

    def fake_convert_recipes(recipes_in, _calculator):
        seen["convert_ids"] = [r.id for r in recipes_in]
        return [SimpleNamespace(id=r.id) for r in recipes_in]

    monkeypatch.setattr("src.cli.extract_ingredient_names", fake_extract_ingredient_names)
    monkeypatch.setattr("src.cli.convert_recipes", fake_convert_recipes)

    monkeypatch.setattr(
        "src.cli.plan_meals",
        lambda _profile, _pool, _days: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        ),
    )
    monkeypatch.setattr("src.cli.format_result_json_string", lambda *_args, **_kwargs: "{}")
    monkeypatch.setattr("src.cli.format_result_markdown", lambda *_args, **_kwargs: "")

    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "cli.py",
            "--profile",
            "config/user_profile.yaml",
            "--recipes",
            str(recipes_path),
            "--ingredients",
            str(ingredients_path),
            "--output",
            "json",
            "--planning-mode",
            "deterministic",
            "--cuisine",
            "mexican",
            "--recipe-tags-path",
            str(tag_path),
        ],
    )

    cli.main()
    _ = capsys.readouterr()

    assert seen["extract_ids"] == ["r1", "r2"]
    assert seen["convert_ids"] == ["r1", "r2"]


def test_cli_tag_filtering_preserves_recipe_db_order(
    monkeypatch, tmp_path, capsys
):
    recipes_path = tmp_path / "recipes.json"
    _write_simple_recipe_store_ordered(recipes_path, ["r2", "r1"])

    ingredients_path = tmp_path / "ingredients.json"
    ingredients_path.write_text("{}", encoding="utf-8")

    tag_path = tmp_path / "tags.json"
    tag_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("src.cli.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.cli.LocalIngredientProvider", lambda _: DummyProvider())
    monkeypatch.setattr("src.cli.UpperLimitsLoader", lambda *_: object())
    monkeypatch.setattr("src.cli.resolve_upper_limits", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("src.cli.NutritionCalculator", lambda _provider: object())

    monkeypatch.setattr(
        "src.cli.load_recipe_tags",
        lambda _: {
            "r1": _tags(cuisine="shared"),
            "r2": _tags(cuisine="shared"),
        },
    )

    seen = {}

    def fake_extract_ingredient_names(recipes_in):
        seen["extract_ids"] = [r.id for r in recipes_in]
        return ["ingredient-x"]

    def fake_convert_recipes(recipes_in, _calculator):
        seen["convert_ids"] = [r.id for r in recipes_in]
        return [SimpleNamespace(id=r.id) for r in recipes_in]

    monkeypatch.setattr("src.cli.extract_ingredient_names", fake_extract_ingredient_names)
    monkeypatch.setattr("src.cli.convert_recipes", fake_convert_recipes)

    monkeypatch.setattr(
        "src.cli.plan_meals",
        lambda _profile, _pool, _days: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        ),
    )
    monkeypatch.setattr("src.cli.format_result_json_string", lambda *_args, **_kwargs: "{}")
    monkeypatch.setattr("src.cli.format_result_markdown", lambda *_args, **_kwargs: "")

    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "cli.py",
            "--profile",
            "config/user_profile.yaml",
            "--recipes",
            str(recipes_path),
            "--ingredients",
            str(ingredients_path),
            "--output",
            "json",
            "--planning-mode",
            "deterministic",
            "--cuisine",
            "shared",
            "--recipe-tags-path",
            str(tag_path),
        ],
    )

    cli.main()
    _ = capsys.readouterr()

    assert seen["extract_ids"] == ["r2", "r1"]
    assert seen["convert_ids"] == ["r2", "r1"]


def test_cli_tag_filtering_multiple_cuisines_union_preserves_order(
    monkeypatch, tmp_path, capsys
):
    recipes_path = tmp_path / "recipes.json"
    _write_simple_recipe_store(recipes_path)

    ingredients_path = tmp_path / "ingredients.json"
    ingredients_path.write_text("{}", encoding="utf-8")

    tag_path = tmp_path / "tags.json"
    tag_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("src.cli.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.cli.LocalIngredientProvider", lambda _: DummyProvider())
    monkeypatch.setattr("src.cli.UpperLimitsLoader", lambda *_: object())
    monkeypatch.setattr("src.cli.resolve_upper_limits", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("src.cli.NutritionCalculator", lambda _provider: object())

    monkeypatch.setattr(
        "src.cli.load_recipe_tags",
        lambda _: {
            "r1": _tags(cuisine="italian"),
            "r2": _tags(cuisine="mexican"),
        },
    )

    seen = {}

    def fake_extract_ingredient_names(recipes_in):
        seen["extract_ids"] = [r.id for r in recipes_in]
        return ["ingredient-x"]

    def fake_convert_recipes(recipes_in, _calculator):
        seen["convert_ids"] = [r.id for r in recipes_in]
        return [SimpleNamespace(id=r.id) for r in recipes_in]

    monkeypatch.setattr("src.cli.extract_ingredient_names", fake_extract_ingredient_names)
    monkeypatch.setattr("src.cli.convert_recipes", fake_convert_recipes)

    monkeypatch.setattr(
        "src.cli.plan_meals",
        lambda _profile, _pool, _days: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        ),
    )
    monkeypatch.setattr("src.cli.format_result_json_string", lambda *_args, **_kwargs: "{}")
    monkeypatch.setattr("src.cli.format_result_markdown", lambda *_args, **_kwargs: "")

    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "cli.py",
            "--profile",
            "config/user_profile.yaml",
            "--recipes",
            str(recipes_path),
            "--ingredients",
            str(ingredients_path),
            "--output",
            "json",
            "--planning-mode",
            "deterministic",
            "--cuisine",
            "italian",
            "--cuisine",
            "mexican",
            "--recipe-tags-path",
            str(tag_path),
        ],
    )

    cli.main()
    _ = capsys.readouterr()

    assert seen["extract_ids"] == ["r1", "r2"]
    assert seen["convert_ids"] == ["r1", "r2"]


def test_api_and_cli_use_shared_apply_tag_filtering(monkeypatch, tmp_path):
    from src.llm.tag_filtering_service import apply_tag_filtering as real_apply_tag_filtering

    # ---------------- API: ensure shared helper is called ----------------
    recipes = [SimpleNamespace(id="r1"), SimpleNamespace(id="r2")]
    tags_by_id = {"r1": _tags(cuisine="mexican"), "r2": _tags(cuisine="italian")}

    monkeypatch.setattr("src.api.server.RecipeDB", lambda _: DummyRecipeDB(recipes))
    monkeypatch.setattr("src.api.server.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda _: DummyProvider())
    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )
    monkeypatch.setattr("src.api.server.load_recipe_tags", lambda _: tags_by_id)

    api_calls = {"count": 0}

    def _api_spy_apply_tag_filtering(*, recipes, tags_by_id, preferences):
        api_calls["count"] += 1
        return real_apply_tag_filtering(
            recipes=recipes, tags_by_id=tags_by_id, preferences=preferences
        )

    monkeypatch.setattr("src.api.server.apply_tag_filtering", _api_spy_apply_tag_filtering)

    monkeypatch.setattr("src.api.server.extract_ingredient_names", lambda recipes_in: [])
    monkeypatch.setattr("src.api.server.convert_recipes", lambda recipes_in, _calc: [])
    monkeypatch.setattr("src.api.server.NutritionCalculator", lambda _provider: object())

    monkeypatch.setattr(
        "src.api.server.plan_meals",
        lambda _profile, _pool, _days: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        ),
    )
    monkeypatch.setattr("src.api.server.format_result_json", lambda *_args, **_kwargs: {"ok": True})

    client = TestClient(app)
    payload = _base_plan_payload()
    payload.update({"planning_mode": "deterministic", "cuisine": ["mexican"]})
    resp = client.post("/api/plan", json=payload)
    assert resp.status_code == 200
    assert api_calls["count"] == 1

    # ---------------- CLI: ensure shared helper is called ----------------
    recipes_path = tmp_path / "recipes.json"
    recipes_path.write_text("{}", encoding="utf-8")
    ingredients_path = tmp_path / "ingredients.json"
    ingredients_path.write_text("{}", encoding="utf-8")
    tag_path = tmp_path / "tags.json"
    tag_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("src.cli.RecipeDB", lambda _: DummyRecipeDB(recipes))
    monkeypatch.setattr("src.cli.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.cli.LocalIngredientProvider", lambda _: DummyProvider())
    monkeypatch.setattr("src.cli.UpperLimitsLoader", lambda *_: object())
    monkeypatch.setattr("src.cli.resolve_upper_limits", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("src.cli.NutritionCalculator", lambda _provider: object())
    monkeypatch.setattr("src.cli.load_recipe_tags", lambda _: tags_by_id)

    cli_calls = {"count": 0}

    def _cli_spy_apply_tag_filtering(*, recipes, tags_by_id, preferences):
        cli_calls["count"] += 1
        return real_apply_tag_filtering(
            recipes=recipes, tags_by_id=tags_by_id, preferences=preferences
        )

    monkeypatch.setattr("src.cli.apply_tag_filtering", _cli_spy_apply_tag_filtering)
    monkeypatch.setattr("src.cli.extract_ingredient_names", lambda recipes_in: [])
    monkeypatch.setattr("src.cli.convert_recipes", lambda recipes_in, _calc: [])

    monkeypatch.setattr(
        "src.cli.plan_meals",
        lambda _profile, _pool, _days: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        ),
    )
    monkeypatch.setattr("src.cli.format_result_json_string", lambda *_args, **_kwargs: "{}")
    monkeypatch.setattr("src.cli.format_result_markdown", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    # Re-use the repo's known-good profile schema for CLI wiring tests.
    profile_path = "config/user_profile.yaml"

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "cli.py",
            "--profile",
            str(profile_path),
            "--recipes",
            str(recipes_path),
            "--ingredients",
            str(ingredients_path),
            "--output",
            "json",
            "--planning-mode",
            "deterministic",
            "--cuisine",
            "mexican",
            "--recipe-tags-path",
            str(tag_path),
        ],
    )

    cli.main()
    assert cli_calls["count"] == 1

