import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.config.llm_settings import LLMSettings
from src.llm.usda_contract import USDAProviderRequiredError


class DummyRecipeDB:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def get_all_recipes(self):
        return []


class DummyProvider:
    usda_capable = True

    def resolve_all(self, ingredient_names):
        return None


def _base_plan_request(*, ingredient_source: str = "local", days: int = 1):
    return {
        "daily_calories": 2400,
        "daily_protein_g": 150.0,
        "daily_fat_g_min": 50.0,
        "daily_fat_g_max": 100.0,
        "schedule": {"07:00": 2, "12:00": 3, "18:00": 3},
        "liked_foods": ["egg"],
        "disliked_foods": ["mushroom"],
        "allergies": [],
        "days": days,
        "ingredient_source": ingredient_source,
        "micronutrient_goals": None,
    }


def test_api_plan_maps_usda_provider_required_to_422(monkeypatch):
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

    def _raise_usda(*args, **kwargs):
        raise USDAProviderRequiredError(message="usda required", provider_type="Dummy")

    monkeypatch.setattr("src.api.server.plan_with_llm_feedback", _raise_usda)

    client = TestClient(app)
    resp = client.post("/api/plan", json=_base_plan_request())

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INGREDIENT_VALIDATION_ERROR"


def test_api_plan_maps_unknown_exception_to_pipeline_execution_error(monkeypatch):
    monkeypatch.setattr("src.api.server.RecipeDB", DummyRecipeDB)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda _: DummyProvider())

    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="",
            model="",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    def _raise_unknown(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.api.server.plan_meals", _raise_unknown)

    client = TestClient(app)
    resp = client.post("/api/plan", json=_base_plan_request())

    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "PIPELINE_EXECUTION_ERROR"

