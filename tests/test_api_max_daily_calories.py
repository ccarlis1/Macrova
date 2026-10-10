"""API: max_daily_calories on PlanRequest maps into UserProfile and HC-5 over HTTP."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.api.server import PlanRequest, _build_user_profile, app
from src.data_layer.models import (
    Ingredient,
    MicronutrientProfile,
    NutritionProfile,
    Recipe,
)
from src.planning.converters import convert_profile
from src.planning.orchestrator import ParityPlanContext


def _base_request(**overrides: Any) -> PlanRequest:
    kw: Dict[str, Any] = dict(
        daily_calories=2000,
        daily_protein_g=130.0,
        daily_fat_g_min=50.0,
        daily_fat_g_max=70.0,
        schedule={"07:30": 3, "12:30": 3, "18:30": 4},
        days=1,
    )
    kw.update(overrides)
    return PlanRequest(**kw)


def test_build_user_profile_passes_max_daily_calories():
    req = _base_request(max_daily_calories=1700)
    profile, _ = _build_user_profile(req)
    assert profile.max_daily_calories == 1700
    planning = convert_profile(profile, days=1)
    assert planning.max_daily_calories == 1700


def test_build_user_profile_defaults_max_daily_calories_to_none():
    req = _base_request()
    profile, _ = _build_user_profile(req)
    assert profile.max_daily_calories is None
    planning = convert_profile(profile, days=1)
    assert planning.max_daily_calories is None


def test_plan_request_accepts_ceiling_below_daily_calories():
    """MB-054-style inputs must reach the planner, not 422."""
    req = _base_request(daily_calories=2000, max_daily_calories=1700)
    assert req.max_daily_calories == 1700


class _StubRecipeDB:
    def __init__(self, recipes: List[Recipe]):
        self._recipes = recipes

    def get_all_recipes(self) -> List[Recipe]:
        return list(self._recipes)


class _StubCalc:
    """Fixed per-recipe nutrition: ~2100 kcal / 130 g protein / 60 g fat total.

    Without a ceiling the day fits the ±10% window around 2000. With ceiling 1900
    the only combo exceeds HC-5, so search attributes FM-2 (not an empty
    pre-search window like ceiling 1700 → [1800,1700]).
    """

    _NUTRITION = {
        "r_breakfast": NutritionProfile(
            700.0, 40.0, 20.0, 80.0, MicronutrientProfile()
        ),
        "r_lunch": NutritionProfile(
            700.0, 45.0, 20.0, 80.0, MicronutrientProfile()
        ),
        "r_dinner": NutritionProfile(
            700.0, 45.0, 20.0, 80.0, MicronutrientProfile()
        ),
    }

    def calculate_recipe_nutrition(self, recipe: Recipe) -> NutritionProfile:
        return self._NUTRITION[recipe.id]


def _make_recipe(rid: str, name: str) -> Recipe:
    return Recipe(
        id=rid,
        name=name,
        ingredients=[
            Ingredient(
                name="cream of rice",
                quantity=100.0,
                unit="g",
                normalized_unit="g",
                normalized_quantity=100.0,
            )
        ],
        cooking_time_minutes=15,
        instructions=[],
    )


def _empty_parity_ctx(**_kwargs: Any) -> ParityPlanContext:
    return ParityPlanContext(
        active_batches=[],
        persisted_pins=[],
        seed=None,
        batch_locks=[],
    )


def _plan_payload(*, max_daily_calories: Optional[int] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "daily_calories": 2000,
        "daily_protein_g": 130.0,
        "daily_fat_g_min": 50.0,
        "daily_fat_g_max": 70.0,
        "schedule": {"07:30": 3, "12:30": 3, "18:30": 4},
        "days": 1,
        "ingredient_source": "local",
        "recipe_ids": ["r_breakfast", "r_lunch", "r_dinner"],
        "planning_mode": "deterministic",
    }
    if max_daily_calories is not None:
        body["max_daily_calories"] = max_daily_calories
    return body


def test_plan_endpoint_hc5_ceiling_returns_fm2(monkeypatch):
    """Pool is feasible without a ceiling; ceiling 1900 → FM-2 (HC-5)."""
    recipes = [
        _make_recipe("r_breakfast", "Breakfast Bowl"),
        _make_recipe("r_lunch", "Lunch Plate"),
        _make_recipe("r_dinner", "Dinner Bowl"),
    ]
    monkeypatch.setattr(
        "src.api.server.RecipeDB",
        lambda *_a, **_k: _StubRecipeDB(recipes),
    )
    monkeypatch.setattr("src.api.server.NutritionDB", lambda *_a, **_k: object())
    monkeypatch.setattr(
        "src.api.server.LocalIngredientProvider",
        lambda *_a, **_k: MagicMock(resolve_all=lambda _names: None),
    )
    monkeypatch.setattr("src.api.server.NutritionCalculator", lambda *_a, **_k: _StubCalc())
    monkeypatch.setattr(
        "src.api.server.hydrate_parity_plan_context",
        _empty_parity_ctx,
    )
    # Avoid tag-file I/O; empty maps keep all recipes eligible.
    monkeypatch.setattr(
        "src.api.server.load_canonical_recipe_tag_slugs",
        lambda *_a, **_k: {},
    )
    monkeypatch.setattr(
        "src.api.server.load_hard_eligible_recipe_tag_slugs",
        lambda *_a, **_k: {},
    )
    monkeypatch.setattr(
        "src.api.server._apply_recipe_tag_filter_pre_convert",
        lambda recipes, **_k: (recipes, {"filtered": False}),
    )

    client = TestClient(app)

    control = client.post("/api/v1/plan", json=_plan_payload())
    assert control.status_code == 200, control.text
    assert control.json()["success"] is True

    ceiling = client.post(
        "/api/v1/plan", json=_plan_payload(max_daily_calories=1900)
    )
    assert ceiling.status_code == 200, ceiling.text
    body = ceiling.json()
    assert body["success"] is False
    # FM-2 is the planner failure_mode; the user-facing failures[] entry is
    # FM-MACRO-INFEASIBLE. diagnosis.code carries the attributed FM-2.
    assert body["report"]["diagnosis"]["code"] == "FM-2"
    codes = [f["code"] for f in body.get("report", {}).get("failures", [])]
    assert "FM-MACRO-INFEASIBLE" in codes, codes
