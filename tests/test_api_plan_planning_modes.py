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


def _base_plan_request(*, planning_mode: str | None = None):
    payload = {
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
    }
    if planning_mode is not None:
        payload["planning_mode"] = planning_mode
    return payload


def test_api_plan_planning_mode_deterministic_overrides_llm_enabled(monkeypatch):
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

    called = {"plan_meals": 0, "orchestrator": 0}

    def _fake_plan_meals(*args, **kwargs):
        called["plan_meals"] += 1
        return MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        )

    def _fake_orchestrator(*args, **kwargs):
        called["orchestrator"] += 1
        return _fake_plan_meals()

    monkeypatch.setattr("src.api.server.plan_meals", _fake_plan_meals)
    monkeypatch.setattr("src.api.server.plan_with_llm_feedback", _fake_orchestrator)

    monkeypatch.setattr("src.api.server.format_result_json", lambda *args, **kwargs: {"ok": True})

    client = TestClient(app)
    resp = client.post(
        "/api/plan",
        json=_base_plan_request(planning_mode="deterministic"),
    )
    assert resp.status_code == 200
    assert called["plan_meals"] == 1
    assert called["orchestrator"] == 0


def test_api_plan_planning_mode_assisted_cached_abort_on_cache_miss(
    monkeypatch,
    tmp_path,
):
    # Ensure strict mode isn't controlled by env in this test.
    monkeypatch.delenv("LLM_DETERMINISTIC_STRICT", raising=False)

    cache_path = str(tmp_path / "feedback_cache.json")
    monkeypatch.setenv("LLM_FEEDBACK_CACHE_PATH", cache_path)

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
        raise AssertionError("LLM generation should not run on deterministic cache miss.")

    monkeypatch.setattr(
        "src.planning.orchestrator.suggest_targeted_recipe_drafts",
        _should_not_call_llm,
    )

    client = TestClient(app)
    resp = client.post(
        "/api/plan",
        json=_base_plan_request(planning_mode="assisted_cached"),
    )

    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "DETERMINISTIC_CACHE_MISS"

