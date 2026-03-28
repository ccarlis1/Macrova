"""API integration: ``schedule_days`` flows into ``PlanningUserProfile`` with workout gaps."""

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
    usda_capable = True

    def resolve_all(self, ingredient_names):
        return None


def test_api_plan_schedule_days_wires_workout_gaps(monkeypatch):
    """``POST /api/plan`` with ``schedule_days`` → planner profile has explicit gap list."""
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

    captured: dict = {}

    def _fake_plan_meals(profile, recipe_pool, days):
        captured["profile"] = profile
        captured["days"] = days
        return MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        )

    monkeypatch.setattr("src.api.server.plan_meals", _fake_plan_meals)
    monkeypatch.setattr("src.api.server.format_result_json", lambda *args, **kwargs: {"ok": True})

    payload = {
        "daily_calories": 2400,
        "daily_protein_g": 150.0,
        "daily_fat_g_min": 50.0,
        "daily_fat_g_max": 100.0,
        "liked_foods": [],
        "disliked_foods": [],
        "allergies": [],
        "days": 1,
        "ingredient_source": "local",
        "schedule_days": [
            {
                "day_index": 1,
                "meals": [
                    {"index": 1, "busyness_level": 2, "tags": ["breakfast"]},
                    {"index": 2, "busyness_level": 3, "tags": ["dinner"]},
                ],
                "workouts": [
                    {"after_meal_index": 1, "type": "PM", "intensity": "moderate"}
                ],
            }
        ],
    }

    client = TestClient(app)
    resp = client.post("/api/plan", json=payload)
    assert resp.status_code == 200
    prof = captured["profile"]
    assert prof.workout_after_meal_indices_by_day == [[1]]
    assert len(prof.schedule[0]) == 2
    assert prof.schedule[0][0].busyness_level == 2
    assert prof.schedule[0][1].busyness_level == 3
