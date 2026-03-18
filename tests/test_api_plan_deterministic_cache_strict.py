import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.config.llm_settings import LLMSettings
from src.planning.phase10_reporting import MealPlanResult


class DummyRecipeDB:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def get_all_recipes(self):
        return []


class DummyProvider:
    # Used by orchestrator assert_usda_capable_provider().
    usda_capable = True

    def resolve_all(self, ingredient_names):
        return None


def test_api_plan_strict_deterministic_cache_miss_is_mapped(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_DETERMINISTIC_STRICT", "true")
    monkeypatch.setenv("LLM_MODEL", "model-A")
    monkeypatch.setenv("LLM_FEEDBACK_CACHE_PATH", str(tmp_path / "feedback_cache.json"))

    monkeypatch.setattr("src.api.server.RecipeDB", DummyRecipeDB)
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
            enabled=True,
        ),
    )
    monkeypatch.setattr("src.api.server.build_llm_client", lambda: object())
    monkeypatch.setattr("src.api.server.build_usda_provider", lambda: DummyProvider())

    failure = MealPlanResult(
        success=False,
        termination_code="TC-2",
        failure_mode="FM-2",
        plan=[],
        daily_trackers={},
        weekly_tracker=None,
        report={},
        stats={"attempts": 0, "backtracks": 0},
    )

    monkeypatch.setattr("src.planning.orchestrator.plan_meals", lambda *args, **kwargs: failure)

    def _should_not_call_llm(*args, **kwargs):
        raise AssertionError("LLM generation should not run in strict deterministic mode on cache miss.")

    monkeypatch.setattr(
        "src.planning.orchestrator.suggest_targeted_recipe_drafts",
        _should_not_call_llm,
    )

    client = TestClient(app)
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

    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "DETERMINISTIC_CACHE_MISS"

