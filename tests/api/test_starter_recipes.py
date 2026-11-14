"""Sprint 2 BE-22: starter pack list/import and the empty-pool message."""

from __future__ import annotations

import contextlib
import io
import json

import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer import user_data

_ONE_DAY_TWO_MEALS = {
    "daily_calories": 1400,
    "daily_protein_g": 80.0,
    "daily_fat_g_min": 25.0,
    "daily_fat_g_max": 50.0,
    "schedule_days": [
        {"day_index": 1, "meals": [{"index": 1, "busyness_level": 4}, {"index": 2, "busyness_level": 4}]}
    ],
    "days": 1,
    "planning_mode": "deterministic",
}


@pytest.fixture
def user_folder(tmp_path, monkeypatch):
    """A fresh user data folder wired into the API, as MACROVA_DATA_DIR would be."""
    folder = tmp_path / "ud"
    assert user_data.setup_user_data(folder)
    monkeypatch.setattr("src.api.server.recipes_path", str(folder / "recipes.json"))
    monkeypatch.setattr("src.api.server.DEFAULT_TAG_PATH", str(folder / "recipe_tags.json"))
    return folder


def test_list_returns_the_18_starters_with_real_nutrition():
    res = TestClient(app).get("/api/v1/starter_recipes")
    assert res.status_code == 200, res.text
    recipes = res.json()["recipes"]

    assert len(recipes) == 18
    assert [r["id"] for r in recipes] == [f"recipe_{i:03d}" for i in range(1, 19)]
    for r in recipes:
        assert set(r) == {
            "id", "name", "cooking_time_minutes", "calories_per_serving", "protein_g_per_serving",
            "tag_slugs_by_type", "ready_for_planning", "unresolved",
        }
        assert r["tag_slugs_by_type"], r["id"]
        if r["ready_for_planning"]:
            # Catches a regression of the BE-21 zero-nutrition bug.
            assert r["calories_per_serving"] > 0 and r["protein_g_per_serving"] > 0
            assert r["unresolved"] == []
        else:
            assert r["calories_per_serving"] is None and r["unresolved"]


def test_empty_pool_plan_says_add_recipes_or_import_the_starter_pack(user_folder):
    body = TestClient(app).post("/api/v1/plan", json=_ONE_DAY_TWO_MEALS).json()

    assert body["plan_status"] != "success"
    (failure,) = body["report"]["failures"]
    assert failure["code"] == "FM-1"
    assert "starter pack" in failure["fix"]
    cause = body["report"]["failure_cause"]
    assert cause["cause"] == "EMPTY_POOL"
    assert cause["recipe_could_help"] is True


def test_import_then_plan_succeeds(user_folder):
    client = TestClient(app)
    res = client.post("/api/v1/starter_recipes/import", json={"recipe_ids": ["recipe_001", "recipe_002"]})
    assert res.status_code == 200, res.text
    assert res.json() == {"imported": ["recipe_001", "recipe_002"], "skipped": []}

    pool = json.loads((user_folder / "recipes.json").read_text())["recipes"]
    assert [r["id"] for r in pool] == ["recipe_001", "recipe_002"]
    tags = json.loads((user_folder / "recipe_tags.json").read_text())["tags_by_id"]
    assert set(tags) == {"recipe_001", "recipe_002"}
    assert tags["recipe_001"]["tag_slugs_by_type"]["context"] == ["lunch", "dinner"]

    body = client.post("/api/v1/plan", json=_ONE_DAY_TWO_MEALS).json()
    assert body["plan_status"] == "success", body["report"]
    planned = {m["recipe_id"] for day in body["daily_plans"] for m in day["meals"]}
    assert planned <= {"recipe_001", "recipe_002"}


def test_import_is_idempotent_and_skips_unknown_ids(user_folder):
    client = TestClient(app)
    client.post("/api/v1/starter_recipes/import", json={"recipe_ids": ["recipe_001"]})
    before = (user_folder / "recipes.json").read_text()

    res = client.post(
        "/api/v1/starter_recipes/import",
        json={"recipe_ids": ["recipe_001", "not-a-recipe", "recipe_001"]},
    )
    assert res.status_code == 200
    assert res.json() == {
        "imported": [],
        "skipped": [
            {"id": "recipe_001", "reason": "already_in_pool"},
            {"id": "not-a-recipe", "reason": "not_a_starter_recipe"},
        ],
    }
    assert (user_folder / "recipes.json").read_text() == before


def test_cli_prints_one_line_for_an_empty_pool(tmp_path, monkeypatch):
    from src import cli

    recipes = tmp_path / "recipes.json"
    recipes.write_text('{"recipes": []}', encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["plan_meals", "--profile", "config/user_profile.yaml.example", "--recipes", str(recipes)],
    )
    err = io.StringIO()
    exit_code = 0
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        try:
            cli.main()
        except SystemExit as exc:
            exit_code = exc.code or 0

    lines = [line for line in err.getvalue().splitlines() if line.startswith("No recipes in")]
    assert len(lines) == 1
    assert str(recipes) in lines[0] and "starter pack" in lines[0]
    assert exit_code == 0  # unchanged: the CLI still exits 0 on a failed plan
