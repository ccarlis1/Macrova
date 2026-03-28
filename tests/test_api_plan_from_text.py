import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.config.llm_settings import LLMSettings
from src.data_layer.user_profile import user_profile_from_planner_config
from src.llm.constraint_parser import PlannerConfigParsingError
from src.llm.schemas import BudgetLevel, PlannerConfigJson, PlannerPreferences, PlannerTargets
from src.planning.phase10_reporting import MealPlanResult
import json


class DummyRecipeDB:
    def __init__(self, *args, **kwargs):
        pass

    def get_all_recipes(self):
        return []


class DummyProvider:
    def resolve_all(self, ingredient_names):
        return None


def _cfg():
    return PlannerConfigJson(
        days=1,
        meals_per_day=1,
        targets=PlannerTargets(calories=2000, protein=150.0),
        preferences=PlannerPreferences(
            cuisine=["chicken"],
            budget=BudgetLevel.cheap,
        ),
    )


@pytest.mark.parametrize("ingredient_source", ["local", "api"])
def test_plan_from_text_happy_path(monkeypatch, ingredient_source):
    cfg = _cfg()
    expected_profile = user_profile_from_planner_config(cfg)

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
    # Deterministic mode must not call any LLM parsing logic.
    monkeypatch.setattr("src.api.server.build_llm_client", lambda: (_ for _ in ()).throw(AssertionError("LLM client should not be built in deterministic mode")))
    monkeypatch.setattr("src.api.server.parse_nl_config", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("parse_nl_config should not be called in deterministic mode")))
    monkeypatch.setattr("src.api.server.RecipeDB", DummyRecipeDB)

    dummy_provider = DummyProvider()
    monkeypatch.setattr("src.api.server.build_usda_provider", lambda: dummy_provider)
    if ingredient_source == "api":
        pass
    else:
        monkeypatch.setattr("src.api.server.NutritionDB", lambda _: object())
        monkeypatch.setattr(
            "src.api.server.LocalIngredientProvider", lambda _: dummy_provider
        )

    monkeypatch.setattr(
        "src.api.server.plan_meals",
        lambda profile, recipe_pool, days: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
        ),
    )

    client = TestClient(app)
    prompt_json = json.dumps(cfg.model_dump(), sort_keys=True)
    resp = client.post(
        "/api/plan-from-text",
        json={"prompt": prompt_json, "ingredient_source": ingredient_source},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["days"] == 1

    goals = data["goals"]
    assert goals["daily_calories"] == expected_profile.daily_calories
    assert goals["daily_protein_g"] == pytest.approx(expected_profile.daily_protein_g)
    assert goals["daily_fat_g_min"] == pytest.approx(expected_profile.daily_fat_g[0])
    assert goals["daily_fat_g_max"] == pytest.approx(expected_profile.daily_fat_g[1])
    assert goals["daily_carbs_g"] == pytest.approx(expected_profile.daily_carbs_g)


def test_plan_from_text_parse_failure_returns_schema_validation_error(monkeypatch):
    cfg = _cfg()

    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=True,
        ),
    )
    monkeypatch.setattr("src.api.server.build_llm_client", lambda: object())

    def _raise(*args, **kwargs):
        raise PlannerConfigParsingError(
            error_code="LLM_SCHEMA_VALIDATION_ERROR",
            message="bad nl config",
            details={"field_errors": ["x"]},
        )

    monkeypatch.setattr("src.api.server.parse_nl_config", _raise)
    client = TestClient(app)

    resp = client.post(
        "/api/plan-from-text",
        json={"prompt": "bad nl config", "planning_mode": "assisted"},
    )
    assert resp.status_code == 422
    body = resp.json()["error"]
    assert body["code"] == "SCHEMA_VALIDATION_ERROR"
    assert body["details"]["field_errors"] == ["x"]


@pytest.mark.parametrize("ingredient_source", ["local", "api"])
def test_plan_from_text_planning_mode_deterministic_routes_to_plan_meals(
    monkeypatch, ingredient_source
):
    cfg = _cfg()

    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=True,
        ),
    )
    # Deterministic mode MUST not call any LLM logic.
    monkeypatch.setattr(
        "src.api.server.build_llm_client",
        lambda: (_ for _ in ()).throw(AssertionError("LLM client should not be built in deterministic mode")),
    )
    monkeypatch.setattr(
        "src.api.server.parse_nl_config",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("parse_nl_config should not be called in deterministic mode")),
    )
    monkeypatch.setattr("src.api.server.RecipeDB", DummyRecipeDB)

    monkeypatch.setattr("src.api.server.extract_ingredient_names", lambda recipes: [])
    monkeypatch.setattr("src.api.server.convert_recipes", lambda _recipes, _calc: [])
    monkeypatch.setattr("src.api.server.NutritionCalculator", lambda _provider: object())

    monkeypatch.setattr(
        "src.api.server.format_result_json",
        lambda *_args, **_kwargs: {"ok": True},
    )

    dummy_provider = DummyProvider()
    monkeypatch.setattr("src.api.server.build_usda_provider", lambda: dummy_provider)
    if ingredient_source == "api":
        pass
    else:
        monkeypatch.setattr("src.api.server.NutritionDB", lambda _: object())
        monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda _: dummy_provider)

    called = {"plan_meals": 0, "orchestrator": 0}

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

    def _should_not_call(*_args, **_kwargs):
        raise AssertionError("orchestrator should not be called in deterministic mode")

    monkeypatch.setattr("src.api.server.plan_with_llm_feedback", _should_not_call)

    client = TestClient(app)
    prompt_json = json.dumps(cfg.model_dump(), sort_keys=True)
    resp = client.post(
        "/api/plan-from-text",
        json={
            "prompt": prompt_json,
            "ingredient_source": ingredient_source,
            "planning_mode": "deterministic",
        },
    )

    assert resp.status_code == 200


@pytest.mark.parametrize("ingredient_source", ["local", "api"])
def test_plan_from_text_planning_mode_assisted_cached_routes_to_orchestrator(
    monkeypatch, ingredient_source
):
    cfg = _cfg()

    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=True,
        ),
    )
    monkeypatch.setattr("src.api.server.build_llm_client", lambda: object())
    monkeypatch.setattr("src.api.server.parse_nl_config", lambda client, text: cfg)
    monkeypatch.setattr("src.api.server.RecipeDB", DummyRecipeDB)

    monkeypatch.setattr("src.api.server.extract_ingredient_names", lambda recipes: [])
    monkeypatch.setattr("src.api.server.convert_recipes", lambda _recipes, _calc: [])
    monkeypatch.setattr("src.api.server.NutritionCalculator", lambda _provider: object())

    monkeypatch.setattr(
        "src.api.server.format_result_json",
        lambda *_args, **_kwargs: {"ok": True},
    )

    dummy_provider = DummyProvider()
    monkeypatch.setattr("src.api.server.build_usda_provider", lambda: dummy_provider)
    if ingredient_source == "api":
        pass
    else:
        monkeypatch.setattr("src.api.server.NutritionDB", lambda _: object())
        monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda _: dummy_provider)

    captured = {}

    def fake_plan_with_llm_feedback(*_args, **kwargs):
        captured["deterministic_strict_override"] = kwargs.get(
            "deterministic_strict_override"
        )
        captured["use_feedback_cache"] = kwargs.get("use_feedback_cache")
        captured["force_live_generation"] = kwargs.get("force_live_generation")
        return MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        )

    monkeypatch.setattr("src.api.server.plan_with_llm_feedback", fake_plan_with_llm_feedback)
    monkeypatch.setattr(
        "src.api.server.plan_meals",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("plan_meals should not be called")),
    )

    client = TestClient(app)
    resp = client.post(
        "/api/plan-from-text",
        json={
            "prompt": "some prompt",
            "ingredient_source": ingredient_source,
            "planning_mode": "assisted_cached",
        },
    )

    assert resp.status_code == 200, resp.text
    assert captured["deterministic_strict_override"] is True
    assert captured["use_feedback_cache"] is True
    assert captured["force_live_generation"] is False

