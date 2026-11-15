"""Sprint 2 BE-20: read-only ``GET /api/v1/micronutrient_defaults``.

The route exposes the one per-demographic default (``src/data_layer/upper_limits.py``)
that the MCP server applies, so Flutter can show it. It must not change planning:
``/api/v1/plan`` without ``micronutrient_goals`` still applies no floors.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer.upper_limits import (
    DEFAULT_MICRONUTRIENT_WEEKLY_MIN_FRACTION,
    DEMOGRAPHICS,
    default_micronutrient_goals,
    default_micronutrient_left_out,
)
from src.mcp_server import models as mcp_models
from src.mcp_server import tools as mcp_tools
from tests.api.test_plan_demographic_uls import PAYLOAD, inline_pool  # noqa: F401  (fixture)

ROUTE = "/api/v1/micronutrient_defaults"


def _get(**params: Any):
    return TestClient(app).get(ROUTE, params=params)


@pytest.mark.parametrize("demographic", DEMOGRAPHICS)
def test_defaults_match_the_helpers_and_the_mcp_default(demographic):
    res = _get(demographic=demographic)
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"demographic", "micronutrient_goals", "left_out", "micronutrient_weekly_min_fraction"}
    assert body["demographic"] == demographic
    assert body["micronutrient_goals"] == default_micronutrient_goals(demographic)
    assert body["left_out"] == list(default_micronutrient_left_out(demographic))
    assert body["micronutrient_weekly_min_fraction"] == DEFAULT_MICRONUTRIENT_WEEKLY_MIN_FRACTION
    assert not set(body["left_out"]) & set(body["micronutrient_goals"])

    # The MCP server plans with exactly this default when only a demographic is given.
    targets = mcp_models.Targets(
        daily_calories=2400, daily_protein_g=150, daily_fat_g_min=50, daily_fat_g_max=100, demographic=demographic
    )
    goals, left_out = mcp_tools._micronutrient_goals(targets)
    assert goals == body["micronutrient_goals"]
    assert list(goals) == list(body["micronutrient_goals"])
    assert list(left_out) == body["left_out"]


def test_adult_male_leaves_out_the_omegas():
    body = _get(demographic="adult_male").json()
    assert body["left_out"] == ["omega_3_g", "omega_6_g"]
    assert len(body["micronutrient_goals"]) == 23
    assert body["micronutrient_goals"]["vitamin_c_mg"] == 90.0


@pytest.mark.parametrize("params", [{"demographic": "teen_male"}, {}])
def test_unknown_or_missing_demographic_is_400_invalid_request(params):
    res = _get(**params)
    assert res.status_code == 400
    assert res.json() == {"error": {"code": "INVALID_REQUEST", "message": "Invalid request schema."}}


def test_plan_without_goals_still_applies_no_floors(inline_pool, monkeypatch):  # noqa: F811
    seen: Dict[str, Any] = {}

    def _spy(profile, pool, days, **kwargs):
        seen["profile"] = profile
        raise RuntimeError("stop after capture")

    monkeypatch.setattr("src.api.server.plan_meals", _spy)
    client = TestClient(app)
    assert client.get(ROUTE, params={"demographic": "adult_male"}).status_code == 200
    for body in (PAYLOAD, {**PAYLOAD, "demographic": "adult_male"}):
        seen.clear()
        client.post("/api/v1/plan", json=body)
        assert seen["profile"].micronutrient_targets == {}, body
