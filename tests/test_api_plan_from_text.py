import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer.user_profile import user_profile_from_planner_config
from src.llm.constraint_parser import PlannerConfigParsingError
from src.llm.schemas import BudgetLevel, PlannerConfigJson, PlannerPreferences, PlannerTargets
from src.planning.phase10_reporting import MealPlanResult


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

    monkeypatch.setattr("src.api.server.build_llm_client", lambda: object())
    monkeypatch.setattr("src.api.server.parse_nl_config", lambda client, text: cfg)
    monkeypatch.setattr("src.api.server.RecipeDB", DummyRecipeDB)

    dummy_provider = DummyProvider()
    if ingredient_source == "api":
        monkeypatch.setattr("src.api.server.build_usda_provider", lambda: dummy_provider)
    else:
        monkeypatch.setattr("src.api.server.NutritionDB", lambda _: object())
        monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda _: dummy_provider)

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
    resp = client.post(
        "/api/plan-from-text",
        json={"prompt": "some prompt", "ingredient_source": ingredient_source},
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

    monkeypatch.setattr("src.api.server.build_llm_client", lambda: object())

    def _raise(*args, **kwargs):
        raise PlannerConfigParsingError(
            error_code="LLM_SCHEMA_VALIDATION_ERROR",
            message="bad nl config",
            details={"field_errors": ["x"]},
        )

    monkeypatch.setattr("src.api.server.parse_nl_config", _raise)
    client = TestClient(app)

    resp = client.post("/api/plan-from-text", json={"prompt": "bad nl config"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "SCHEMA_VALIDATION_ERROR"

