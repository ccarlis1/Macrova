"""Sprint 2 BE-22: one setting (MACROVA_DATA_DIR) for user-writable data."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from src.data_layer import user_data

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMITTED = [
    "data/recipes/recipes.json",
    "data/recipes/recipe_tags.json",
    "data/recipes/recipes.json.example",
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_unset_keeps_todays_paths(monkeypatch):
    monkeypatch.delenv(user_data.ENV_VAR, raising=False)
    assert user_data.recipes_path() == "data/recipes/recipes.json"
    assert user_data.recipe_tags_path() == "data/recipes/recipe_tags.json"
    assert user_data.meal_prep_batches_path() == "data/meal_prep/batches.json"


def test_set_moves_every_user_store_into_the_folder(monkeypatch, tmp_path):
    monkeypatch.setenv(user_data.ENV_VAR, str(tmp_path))
    assert user_data.recipes_path() == str(tmp_path / "recipes.json")
    assert user_data.recipe_tags_path() == str(tmp_path / "recipe_tags.json")
    assert user_data.meal_prep_batches_path() == str(tmp_path / "meal_prep_batches.json")


def test_setup_creates_empty_pool_with_shipped_registry(tmp_path):
    folder = tmp_path / "ud"
    assert user_data.setup_user_data(folder) is True

    assert json.loads((folder / "recipes.json").read_text()) == {"recipes": []}
    tags = json.loads((folder / "recipe_tags.json").read_text())
    shipped = json.loads((REPO_ROOT / "data/recipes/recipe_tags.json").read_text())
    assert tags["tags_by_id"] == {}
    assert tags["tag_registry"] == shipped["tag_registry"]
    assert tags["tag_aliases"] == shipped["tag_aliases"]


def test_setup_never_touches_an_existing_folder(tmp_path):
    folder = tmp_path / "ud"
    folder.mkdir()
    (folder / "recipes.json").write_text('{"recipes": [{"id": "mine"}]}')
    before = (folder / "recipes.json").read_text()

    assert user_data.setup_user_data(folder) is False
    assert (folder / "recipes.json").read_text() == before
    assert not (folder / "recipe_tags.json").exists()


def test_no_other_hard_coded_user_data_paths_in_src():
    """Every user-data path goes through user_data; no other module hard-codes one."""
    pattern = re.compile(r"""["']data/(recipes/recipes\.json|recipes/recipe_tags\.json|meal_prep/batches\.json)["']""")
    offenders = [
        str(p.relative_to(REPO_ROOT))
        for p in (REPO_ROOT / "src").rglob("*.py")
        if p.name != "user_data.py" and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


_WRITES_SCRIPT = textwrap.dedent(
    """
    import json, sys
    from fastapi.testclient import TestClient
    from src.api.server import app

    c = TestClient(app)
    recipe = {
        "id": "be22-batchable",
        "name": "BE-22 batch bowl",
        "default_servings": 4,
        "ingredients": [{"name": "almonds", "quantity": 30, "unit": "g"}],
        "tag_slugs_by_type": {"context": ["meal-prep"]},
    }
    results = {
        "sync": c.post("/api/v1/recipes/sync", json={"recipes": [recipe]}).status_code,
        "tag": c.post("/api/v1/tags", json={"display": "BE22 Test Tag", "type": "context"}).status_code,
        "batch": c.post(
            "/api/v1/meal_prep_batches",
            json={"recipe_id": "be22-batchable", "total_servings": 2, "cook_date": "2026-11-16",
                  "assignments": [{"day_index": 0, "slot_index": 0, "servings": 1}]},
        ).status_code,
        "import": c.post("/api/v1/starter_recipes/import", json={"recipe_ids": ["recipe_001"]}).json(),
    }
    print(json.dumps(results))
    """
)


def test_writes_go_to_the_data_folder_and_committed_files_are_untouched(tmp_path):
    folder = tmp_path / "ud"
    user_data.setup_user_data(folder)
    before = {rel: _sha(REPO_ROOT / rel) for rel in COMMITTED}
    batches_default = REPO_ROOT / "data/meal_prep/batches.json"
    batches_before = _sha(batches_default) if batches_default.exists() else None

    env = {**os.environ, user_data.ENV_VAR: str(folder)}
    env.pop("NUTRITION_TAG_REPO_PATH", None)
    proc = subprocess.run(
        [sys.executable, "-c", _WRITES_SCRIPT],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    results = json.loads(proc.stdout.strip().splitlines()[-1])
    assert results["sync"] == 200
    assert results["tag"] in (200, 201)
    assert results["batch"] in (200, 201)
    assert results["import"]["imported"] == ["recipe_001"]

    pool = json.loads((folder / "recipes.json").read_text())["recipes"]
    assert {r["id"] for r in pool} == {"be22-batchable", "recipe_001"}
    tags = json.loads((folder / "recipe_tags.json").read_text())
    assert set(tags["tags_by_id"]) == {"be22-batchable", "recipe_001"}
    assert "be22-test-tag" in tags["tag_registry"]
    batches = json.loads((folder / "meal_prep_batches.json").read_text())
    assert "be22-batchable" in json.dumps(batches)

    assert {rel: _sha(REPO_ROOT / rel) for rel in COMMITTED} == before
    assert (_sha(batches_default) if batches_default.exists() else None) == batches_before


def test_setup_script_creates_then_leaves_alone(tmp_path):
    folder = tmp_path / "via_script"
    cmd = [sys.executable, str(REPO_ROOT / "scripts/setup_user_data.py"), "--dir", str(folder)]
    first = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    second = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    assert first.returncode == 0 and "Created" in first.stdout
    assert second.returncode == 0 and "left it untouched" in second.stdout
    assert json.loads((folder / "recipes.json").read_text()) == {"recipes": []}


@pytest.mark.parametrize("path", ["user_data/", "user_data/recipes.json"])
def test_default_user_data_folder_is_gitignored(path):
    proc = subprocess.run(
        ["git", "check-ignore", "-q", path], cwd=REPO_ROOT, capture_output=True, timeout=30
    )
    assert proc.returncode == 0
