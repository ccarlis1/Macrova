"""Sprint 2 BE-20 (D-A): one new-user micronutrient default, used by MCP and the example YAML."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.upper_limits import (
    DEFAULT_MICRONUTRIENT_LEFT_OUT,
    DEFAULT_MICRONUTRIENT_WEEKLY_MIN_FRACTION,
    DEMOGRAPHICS,
    daily_rdis,
    default_micronutrient_goals,
    default_micronutrient_left_out,
)
from src.data_layer.user_profile import UserProfileLoader
from src.mcp_server import models as mcp_models
from src.mcp_server import tools
from src.planning.orchestrator import build_plan_request_from_profile

_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = _ROOT / "config" / "user_profile.yaml.example"
COMMITTED_POOL = _ROOT / "data" / "recipes" / "recipes.json"

MACROS = {"daily_calories": 2400, "daily_protein_g": 150, "daily_fat_g_min": 50, "daily_fat_g_max": 100}


def test_default_is_the_rdis_minus_the_left_out_list_for_every_demographic():
    assert set(DEFAULT_MICRONUTRIENT_LEFT_OUT) == set(DEMOGRAPHICS)
    assert DEFAULT_MICRONUTRIENT_WEEKLY_MIN_FRACTION == 1.0
    for demographic in DEMOGRAPHICS:
        rdis = daily_rdis(demographic)
        left_out = default_micronutrient_left_out(demographic)
        assert set(left_out) <= set(rdis)
        assert default_micronutrient_goals(demographic) == {
            k: v for k, v in rdis.items() if k not in left_out
        }


def test_mcp_path_and_yaml_example_agree_on_the_default():
    raw = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    demographic = raw["demographic"]
    expected = default_micronutrient_goals(demographic)

    assert {k: float(v) for k, v in raw["micronutrient_goals"].items()} == expected
    assert raw["nutrition_goals"]["micronutrient_weekly_min_fraction"] == DEFAULT_MICRONUTRIENT_WEEKLY_MIN_FRACTION

    goals, left_out = tools._micronutrient_goals(mcp_models.Targets(**MACROS, demographic=demographic))
    assert goals == expected
    assert left_out == default_micronutrient_left_out(demographic)

    # What the loaded example actually sends to the planner matches too.
    profile = UserProfileLoader(str(EXAMPLE)).load()
    request = build_plan_request_from_profile(profile, [], [], None, days=7)
    assert request["micronutrient_goals"] == expected
    assert request["micronutrient_weekly_min_fraction"] == DEFAULT_MICRONUTRIENT_WEEKLY_MIN_FRACTION


def test_example_profile_is_canonical_three_meal_schedule_days():
    raw = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    assert "schedule" not in raw
    (day,) = raw["schedule_days"]
    assert [m["index"] for m in day["meals"]] == [1, 2, 3]
    assert [m["tags"] for m in day["meals"]] == [["breakfast"], ["lunch"], ["dinner"]]
    profile = UserProfileLoader(str(EXAMPLE)).load()
    assert profile.schedule_days and len(profile.schedule_days[0].meals) == 3
    assert profile.demographic == "adult_male"


@pytest.mark.parametrize("days", [3, 7])
def test_example_profile_plans_on_the_committed_pool_with_uls_on(days):
    profile = UserProfileLoader(str(EXAMPLE)).load()
    recipes = RecipeDB(str(COMMITTED_POOL)).get_all_recipes()
    body = build_plan_request_from_profile(profile, recipes, [], None, days=days)
    body.pop("active_batches", None)
    body["planning_mode"] = "deterministic"
    assert body["demographic"] == "adult_male"  # daily ULs are enforced
    out = TestClient(app).post("/api/v1/plan", json=body).json()
    assert out["plan_status"] == "success", out.get("report", {}).get("failures")
