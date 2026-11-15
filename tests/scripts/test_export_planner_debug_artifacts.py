"""BE-17: the debug-artifact script's local plan uses the same daily ULs as its HTTP body."""

from __future__ import annotations

import importlib
import os
import shutil
from pathlib import Path

import pytest

from src.data_layer.upper_limits import upper_limits

_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLE = _ROOT / "config" / "user_profile.yaml.example"


class _Stop(Exception):
    pass


def _import_script():
    """Import the script without keeping the repo ``.env`` values it loads at import time."""
    saved = dict(os.environ)
    try:
        return importlib.import_module("scripts.export_planner_debug_artifacts")
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _run(tmp_path, monkeypatch, profile_text: str) -> dict:
    profile = tmp_path / "user_profile.yaml"
    profile.write_text(profile_text, encoding="utf-8")
    recipes = tmp_path / "recipes.json"
    shutil.copy(_ROOT / "data" / "recipes" / "recipes.json.example", recipes)
    debug_export = _import_script()
    seen: dict = {}

    def _spy(_profile, _pool, _days, **kwargs):
        seen.update(kwargs)
        raise _Stop

    monkeypatch.setattr(debug_export, "plan_meals", _spy)
    with pytest.raises(_Stop):
        debug_export._run_planner(
            profile_yaml=str(profile),
            recipes_path=str(recipes),
            ingredients_path=str(_ROOT / "data" / "reference" / "ingredient_nutrition.json"),
            days=1,
            ingredient_source="local",
            seed=None,
        )
    return seen


def test_local_plan_gets_resolved_ul_for_profile_demographic(tmp_path, monkeypatch):
    text = _EXAMPLE.read_text(encoding="utf-8")
    assert _run(tmp_path, monkeypatch, text) == {"resolved_ul": upper_limits("adult_male")}


def test_local_plan_gets_no_ul_without_demographic(tmp_path, monkeypatch):
    text = "\n".join(
        line for line in _EXAMPLE.read_text(encoding="utf-8").splitlines()
        if not line.startswith("demographic:")
    )
    assert _run(tmp_path, monkeypatch, text) == {}
