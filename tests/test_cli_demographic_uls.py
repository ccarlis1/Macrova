"""Sprint 2 BE-17: the CLI passes daily ULs for the profile YAML's ``demographic``.

No demographic means no ULs (what the CLI actually did before: the hard-coded
``adult_male`` limits were built and never passed). The planner calls are spied,
so nothing is planned or written.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest
import yaml

from src import cli
from src.config.llm_settings import LLMSettings
from src.data_layer.upper_limits import upper_limits
from src.planning.orchestrator import ParityPlanContext


class _Stop(Exception):
    pass


def _write_inputs(tmp_path, demographic) -> Dict[str, str]:
    profile: Dict[str, Any] = {
        "nutrition_goals": {
            "daily_calories": 2000,
            "daily_protein_g": 100,
            "daily_fat_g": {"min": 60, "max": 80},
        },
        "schedule": {"08:00": 2, "13:00": 3, "19:00": 3},
        "preferences": {"liked_foods": [], "disliked_foods": [], "allergies": []},
    }
    if demographic is not None:
        profile["demographic"] = demographic
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(yaml.safe_dump(profile), encoding="utf-8")
    recipes_path = tmp_path / "recipes.json"
    recipes_path.write_text(
        json.dumps(
            {
                "recipes": [
                    {
                        "id": "r-cli-ul",
                        "name": "CLI UL Bowl",
                        "ingredients": [{"name": "cream of rice", "quantity": 100, "unit": "g"}],
                        "cooking_time_minutes": 5,
                        "instructions": ["Prepare."],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    tags_path = tmp_path / "recipe_tags.json"
    tags_path.write_text(json.dumps({"tag_registry": {}, "tag_aliases": {}, "tags_by_id": {}}), encoding="utf-8")
    return {"profile": str(profile_path), "recipes": str(recipes_path), "tags": str(tags_path)}


def _run(monkeypatch, paths, *extra_args) -> None:
    monkeypatch.setattr(
        "src.cli.hydrate_parity_plan_context",
        lambda **_kw: ParityPlanContext(active_batches=[], persisted_pins=[], seed=None, batch_locks=[]),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["plan_meals", "--profile", paths["profile"], "--recipes", paths["recipes"],
         "--recipe-tags-path", paths["tags"], "--days", "1", *extra_args],
    )
    with pytest.raises((_Stop, SystemExit)):
        cli.main()


def _spy(seen: Dict[str, Any]):
    def _capture(*_args, **kwargs):
        seen["kwargs"] = kwargs
        raise _Stop()

    return _capture


@pytest.mark.parametrize(
    ("demographic", "expected"),
    [("adult_male", {"resolved_ul": upper_limits("adult_male")}), (None, {})],
)
def test_cli_deterministic_passes_resolved_ul_for_yaml_demographic(tmp_path, monkeypatch, demographic, expected):
    seen: Dict[str, Any] = {}
    monkeypatch.setattr("src.cli.plan_meals", _spy(seen))
    _run(monkeypatch, _write_inputs(tmp_path, demographic))
    assert seen["kwargs"] == expected


@pytest.mark.parametrize("demographic", ["adult_female", None])
def test_cli_assisted_passes_resolved_ul_for_yaml_demographic(tmp_path, monkeypatch, demographic):
    seen: Dict[str, Any] = {}
    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy", model="dummy", timeout_seconds=1.0, max_retries=0, rate_limit_qps=1.0, enabled=True
        ),
    )
    monkeypatch.setattr("src.cli.LLMClient", lambda *_a, **_k: object())
    monkeypatch.setattr("src.cli.USDAClient.from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr("src.cli.CachedIngredientLookup", lambda **_k: object())
    monkeypatch.setattr("src.cli.APIIngredientProvider", lambda *_a, **_k: object())
    monkeypatch.setattr("src.cli.plan_meals", lambda *_a, **_k: pytest.fail("assisted mode must use the orchestrator"))
    monkeypatch.setattr("src.cli.plan_with_llm_feedback", _spy(seen))
    _run(monkeypatch, _write_inputs(tmp_path, demographic), "--planning-mode", "assisted")
    if demographic is None:
        assert "resolved_ul" not in seen["kwargs"]
    else:
        assert seen["kwargs"]["resolved_ul"] == upper_limits(demographic)
