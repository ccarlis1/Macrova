"""Sprint 2 BE-17: one demographic -> daily UL path for the API, CLI and MCP server."""

from __future__ import annotations

from typing import Any, Dict, get_args

import pytest
import yaml

from src.data_layer import upper_limits as ul_module
from src.data_layer.models import UpperLimits
from src.data_layer.upper_limits import (
    DEMOGRAPHICS,
    RDI_PATH,
    UL_PATH,
    Demographic,
    daily_rdis,
    upper_limits,
    upper_limits_for,
)
from src.data_layer.user_profile import UserProfileLoader
from src.mcp_server import models as mcp_models
from src.mcp_server import nutrients
from src.planning import orchestrator
from src.planning.orchestrator import build_plan_request_from_profile, plan_with_llm_feedback
from src.planning.phase10_reporting import MealPlanResult


# --- shared helpers ---------------------------------------------------------


def test_mcp_reexports_the_data_layer_helpers():
    assert nutrients.upper_limits is upper_limits
    assert nutrients.daily_rdis is daily_rdis
    assert nutrients.Demographic is Demographic
    assert nutrients.UL_PATH == UL_PATH and nutrients.RDI_PATH == RDI_PATH
    # The MCP Targets model types against the same literal: no second enum.
    assert mcp_models.Demographic is Demographic


def test_demographics_match_both_reference_tables():
    import json

    for path in (UL_PATH, RDI_PATH):
        table = json.loads(path.read_text(encoding="utf-8"))["demographics"]
        assert sorted(table) == sorted(DEMOGRAPHICS)
    assert DEMOGRAPHICS == get_args(Demographic)


def test_upper_limits_for_none_and_set():
    assert upper_limits_for(None) is None
    assert upper_limits_for("") is None
    ul = upper_limits_for("adult_female")
    assert isinstance(ul, UpperLimits)
    assert ul == upper_limits("adult_female")
    with pytest.raises(KeyError):
        upper_limits_for("teen_male")


# --- UserProfileLoader ------------------------------------------------------


def _profile_yaml(tmp_path, **extra) -> str:
    data: Dict[str, Any] = {
        "nutrition_goals": {
            "daily_calories": 2000,
            "daily_protein_g": 100,
            "daily_fat_g": {"min": 60, "max": 80},
        },
        "schedule": {"08:00": 2, "13:00": 3, "19:00": 3},
        "preferences": {"liked_foods": [], "disliked_foods": [], "allergies": []},
        **extra,
    }
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def test_loader_reads_optional_demographic(tmp_path):
    assert UserProfileLoader(_profile_yaml(tmp_path)).load().demographic is None
    assert UserProfileLoader(_profile_yaml(tmp_path, demographic=None)).load().demographic is None
    loaded = UserProfileLoader(_profile_yaml(tmp_path, demographic="pregnancy")).load()
    assert loaded.demographic == "pregnancy"
    # A demographic sets ULs only, never micronutrient goals (BE-20's call).
    assert loaded.daily_micronutrient_targets is None


def test_loader_rejects_unsupported_demographic(tmp_path):
    with pytest.raises(ValueError, match="teen_male"):
        UserProfileLoader(_profile_yaml(tmp_path, demographic="teen_male")).load()


# --- build_plan_request_from_profile ---------------------------------------


def test_plan_request_builder_carries_demographic_only_when_set(tmp_path):
    from src.api.server import PlanRequest

    plain = UserProfileLoader(_profile_yaml(tmp_path)).load()
    payload = build_plan_request_from_profile(plain, [], [], None)
    assert "demographic" not in payload

    with_demo = UserProfileLoader(_profile_yaml(tmp_path, demographic="adult_male")).load()
    payload = build_plan_request_from_profile(with_demo, [], [], None)
    assert payload["demographic"] == "adult_male"
    assert PlanRequest.model_validate(payload).demographic == "adult_male"


# --- plan_with_llm_feedback threads resolved_ul -----------------------------


def _success() -> MealPlanResult:
    return MealPlanResult(
        success=True, termination_code="TC-1", plan=[], daily_trackers={}, report={},
        stats={"attempts": 1, "backtracks": 0},
    )


def test_orchestrator_passes_resolved_ul_to_plan_meals(monkeypatch):
    calls = []
    monkeypatch.setattr(
        orchestrator, "plan_meals", lambda *args, **kwargs: (calls.append(kwargs), _success())[1]
    )
    ul = upper_limits("adult_male")
    plan_with_llm_feedback(object(), [], 1, resolved_ul=ul)
    assert calls == [{"resolved_ul": ul}]

    calls.clear()
    plan_with_llm_feedback(object(), [], 1)
    assert calls == [{}], "no ULs must leave the plan_meals call unchanged"


def test_ul_module_has_one_loader_path():
    # The helper builds on the existing loader; no second UL loader.
    assert ul_module.upper_limits("lactation") == ul_module.resolve_upper_limits(
        ul_module.UpperLimitsLoader(str(UL_PATH)), demographic="lactation"
    )
