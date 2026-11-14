"""Sprint 2 BE-17: optional ``demographic`` on plan requests enforces daily upper limits.

The pool is inline: one recipe meets the day's calories and macros but carries
50 mg iron (adult UL 45 mg); the other is iron-free but far too small. Without a
demographic the planner takes the iron-heavy recipe; with ``adult_male`` the
daily UL rejects it and the plan fails.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.api import server
from src.api.server import PlanRequest, app
from src.config.llm_settings import LLMSettings
from src.data_layer.models import Ingredient, Recipe, UpperLimits
from src.data_layer.upper_limits import upper_limits
from src.planning.converters import convert_profile
from src.planning.orchestrator import ParityPlanContext

IRON_RECIPE = "r-iron-bowl"
SMALL_RECIPE = "r-small-bowl"

# 2000 kcal, 100 g protein, fat 60–80 g -> derived carbs 242.5 g. 500 g of
# "iron mix" (per 100 g: 400 kcal, 20 P, 14 F, 48.5 C, 10 mg iron) hits it exactly.
PAYLOAD: Dict[str, Any] = {
    "daily_calories": 2000,
    "daily_protein_g": 100.0,
    "daily_fat_g_min": 60.0,
    "daily_fat_g_max": 80.0,
    "days": 1,
    "ingredient_source": "local",
    "planning_mode": "deterministic",
    "schedule_days": [
        {
            "day_index": 1,
            "meals": [{"index": 1, "busyness_level": 4, "tags": ["dinner"]}],
            "workouts": [],
        }
    ],
}

_PER_100G = {
    "iron mix": {"calories": 400.0, "protein_g": 20.0, "fat_g": 14.0, "carbs_g": 48.5, "iron_mg": 10.0},
    "plain mix": {"calories": 400.0, "protein_g": 20.0, "fat_g": 14.0, "carbs_g": 48.5},
}


class _InlineProvider:
    usda_capable = False

    def resolve_all(self, _names):
        return None

    def get_ingredient_info(self, name: str):
        return {"name": name, "per_100g": dict(_PER_100G[name])}


class _InlineRecipeDB:
    def __init__(self, *_a, **_k) -> None:
        pass

    def get_all_recipes(self):
        return [
            Recipe(
                id=IRON_RECIPE,
                name="Iron Bowl",
                ingredients=[Ingredient("iron mix", 500.0, "g", is_to_taste=False)],
                cooking_time_minutes=10,
                instructions=["mix"],
            ),
            Recipe(
                id=SMALL_RECIPE,
                name="Small Bowl",
                ingredients=[Ingredient("plain mix", 100.0, "g", is_to_taste=False)],
                cooking_time_minutes=10,
                instructions=["mix"],
            ),
        ]


@pytest.fixture
def inline_pool(tmp_path, monkeypatch):
    tags = tmp_path / "recipe_tags.json"
    tags.write_text(json.dumps({"tag_registry": {}, "tag_aliases": {}, "tags_by_id": {}}), encoding="utf-8")
    monkeypatch.setattr("src.api.server.DEFAULT_TAG_PATH", str(tags))
    monkeypatch.setattr("src.api.server.recipes_path", str(tmp_path / "recipes.json"))
    monkeypatch.setattr("src.api.server.RecipeDB", _InlineRecipeDB)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda *_a, **_k: object())
    monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda *_a, **_k: _InlineProvider())
    monkeypatch.setattr(
        "src.api.server.hydrate_parity_plan_context",
        lambda seed=None: ParityPlanContext(active_batches=[], persisted_pins=[], seed=None, batch_locks=[]),
    )
    return tags


def _plan(body: Dict[str, Any]):
    return TestClient(app).post("/api/v1/plan", json=body)


def _failure_codes(body: Dict[str, Any]) -> list:
    return [f["code"] for f in (body.get("report") or {}).get("failures") or []]


def test_without_demographic_the_iron_heavy_plan_succeeds(inline_pool):
    resp = _plan(PAYLOAD)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["daily_plans"][0]["meals"][0]["recipe_id"] == IRON_RECIPE


def test_adult_male_ul_rejects_the_only_calorie_feasible_plan(inline_pool):
    resp = _plan({**PAYLOAD, "demographic": "adult_male"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["plan_status"] == "failed"
    # FC-3 (incremental daily UL, phase3_feasibility) prunes the iron bowl; only the
    # 400 kcal bowl is left, so the day can't reach its targets. The planner has no
    # UL-specific failure code: a binding UL surfaces as FM-MACRO-INFEASIBLE.
    assert body["termination_code"] == "TC-2"
    assert _failure_codes(body) == ["FM-MACRO-INFEASIBLE"]


def test_unknown_demographic_is_400_invalid_request(inline_pool):
    resp = _plan({**PAYLOAD, "demographic": "teen_male"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


def test_demographic_passes_resolved_ul_and_sets_no_micronutrient_floors(inline_pool, monkeypatch):
    seen: Dict[str, Any] = {}

    def _spy(profile, pool, days, **kwargs):
        seen["profile"] = profile
        seen["kwargs"] = kwargs
        raise RuntimeError("stop after capture")

    monkeypatch.setattr("src.api.server.plan_meals", _spy)
    _plan({**PAYLOAD, "demographic": "adult_female"})
    assert seen["kwargs"] == {"resolved_ul": upper_limits("adult_female")}
    # RDIs-from-demographic is BE-20's call: no weekly micronutrient floors here.
    assert not seen["profile"].micronutrient_targets

    seen.clear()
    _plan(PAYLOAD)
    assert seen["kwargs"] == {}, "no demographic must leave the plan_meals call unchanged"


def test_demographic_alone_leaves_profile_without_micronutrient_goals():
    request = PlanRequest(**{**PAYLOAD, "demographic": "adult_male"})
    user_profile, _ = server._build_user_profile(request)
    assert user_profile.demographic == "adult_male"
    assert user_profile.daily_micronutrient_targets is None
    assert not convert_profile(user_profile, 1).micronutrient_targets


def _enable_assisted(monkeypatch, seen: Dict[str, Any]) -> None:
    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy", model="dummy", timeout_seconds=1.0, max_retries=0, rate_limit_qps=1.0, enabled=True
        ),
    )
    monkeypatch.setattr("src.api.server.build_llm_client", lambda: object())
    monkeypatch.setattr("src.api.server.build_usda_provider", lambda: _InlineProvider())

    def _spy(profile, pool, days, **kwargs):
        seen["kwargs"] = kwargs
        raise RuntimeError("stop after capture")

    monkeypatch.setattr("src.api.server.plan_with_llm_feedback", _spy)


def test_assisted_plan_passes_resolved_ul_to_orchestrator(inline_pool, monkeypatch):
    seen: Dict[str, Any] = {}
    _enable_assisted(monkeypatch, seen)
    _plan({**PAYLOAD, "planning_mode": "assisted", "demographic": "pregnancy"})
    assert seen["kwargs"]["resolved_ul"] == upper_limits("pregnancy")

    seen.clear()
    _plan({**PAYLOAD, "planning_mode": "assisted"})
    assert "resolved_ul" not in seen["kwargs"]


# --- /api/v1/plan-from-text -------------------------------------------------

_CFG = {
    "days": 1,
    "meals_per_day": 1,
    "targets": {"calories": 2000, "protein": 100.0},
    "preferences": {"cuisine": [], "budget": "cheap"},
}


def _plan_from_text(**extra):
    return TestClient(app).post(
        "/api/v1/plan-from-text", json={"prompt": json.dumps(_CFG), **extra}
    )


def test_plan_from_text_passes_resolved_ul_only_with_demographic(inline_pool, monkeypatch):
    seen: Dict[str, Any] = {}

    def _spy(profile, pool, days, **kwargs):
        seen["kwargs"] = kwargs
        raise RuntimeError("stop after capture")

    monkeypatch.setattr("src.api.server.plan_meals", _spy)
    _plan_from_text(demographic="adult_male")
    assert seen["kwargs"] == {"resolved_ul": upper_limits("adult_male")}

    seen.clear()
    _plan_from_text()
    assert seen["kwargs"] == {}


def test_plan_from_text_assisted_passes_resolved_ul(inline_pool, monkeypatch):
    seen: Dict[str, Any] = {}
    _enable_assisted(monkeypatch, seen)
    from src.llm.schemas import PlannerConfigJson

    monkeypatch.setattr(
        "src.api.server.parse_nl_config", lambda _client, _prompt: PlannerConfigJson.model_validate(_CFG)
    )
    _plan_from_text(planning_mode="assisted", demographic="lactation")
    assert seen["kwargs"]["resolved_ul"] == upper_limits("lactation")


def test_plan_from_text_unknown_demographic_is_400():
    resp = _plan_from_text(demographic="child")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


def test_resolved_ul_is_the_shared_reference_table():
    ul = upper_limits("adult_male")
    assert isinstance(ul, UpperLimits)
    assert ul.iron_mg == 45.0
