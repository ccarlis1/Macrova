"""Shared pytest setup so CI and local runs behave like a clean checkout.

GitHub Actions runs from the repo root with ``pip install -r requirements.txt`` and:

- ``python -m pytest tests/ -q`` (needs ``httpx`` for FastAPI TestClient)
- ``python scripts/export_openapi.py --check`` (OpenAPI snapshot must match the app)

``config/user_profile.yaml`` is gitignored; CLI/API tests reference it by path.

``data/ingredients/custom_ingredients.json`` is gitignored; copy from ``*.example``
when absent. Default local nutrition is ``data/reference/ingredient_nutrition.json``
(committed). ``data/recipes/recipes.json`` is committed (§4.4); still copy from
``.example`` if a checkout is missing it.
"""

import hashlib
import shutil

import pytest
import yaml
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _copy_if_missing(dest: Path, example: Path) -> None:
    if dest.exists() or not example.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example, dest)


@pytest.fixture(scope="session", autouse=True)
def setup_test_config():
    """Ensure config and default data files exist for API/CLI tests.

    Copies from ``user_profile.yaml.example`` when the file is missing or when
    YAML has no usable ``schedule_days`` or legacy ``schedule`` (avoids CLI
    crashes on empty/commented-out schedules). Paths are anchored to the repo
    root so this works regardless of pytest's current working directory.
    """
    config_dir = _REPO_ROOT / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    profile_file = config_dir / "user_profile.yaml"
    example_file = config_dir / "user_profile.yaml.example"

    needs_copy = not profile_file.exists()
    if not needs_copy and profile_file.exists():
        try:
            data = yaml.safe_load(profile_file.read_text(encoding="utf-8")) or {}
            schedule_days = data.get("schedule_days")
            schedule = data.get("schedule")
            has_valid_schedule_days = isinstance(schedule_days, list) and len(schedule_days) > 0
            has_valid_legacy_schedule = isinstance(schedule, dict) and len(schedule) > 0
            needs_copy = not (has_valid_schedule_days or has_valid_legacy_schedule)
        except Exception:
            needs_copy = True

    if needs_copy and example_file.exists():
        shutil.copy(example_file, profile_file)

    # Gitignored data files required by src.api.server and src.cli defaults.
    _copy_if_missing(
        _REPO_ROOT / "data" / "ingredients" / "custom_ingredients.json",
        _REPO_ROOT / "data" / "ingredients" / "custom_ingredients.json.example",
    )
    _copy_if_missing(
        _REPO_ROOT / "data" / "recipes" / "recipes.json",
        _REPO_ROOT / "data" / "recipes" / "recipes.json.example",
    )


#: Committed user-data stores tests must never write (they redirect to ``tmp_path``).
GUARDED_DATA_FILES = (
    _REPO_ROOT / "data" / "recipes" / "recipes.json",
    _REPO_ROOT / "data" / "recipes" / "recipe_tags.json",
)


def hash_files(paths) -> dict:
    """SHA-256 of each file's bytes (``None`` when absent), keyed by path."""
    out = {}
    for path in paths:
        path = Path(path)
        out[path] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return out


def changed_files(before: dict, after: dict) -> list:
    """Paths whose hash differs between two ``hash_files`` snapshots (sorted)."""
    return sorted(str(p) for p in before.keys() | after.keys() if before.get(p) != after.get(p))


def committed_data_changed_message(changed: list) -> str:
    rel = [str(Path(p).relative_to(_REPO_ROOT)) if Path(p).is_relative_to(_REPO_ROOT) else str(p) for p in changed]
    return (
        "Test session modified committed data file(s): "
        + ", ".join(rel)
        + ". A test wrote to the real store: redirect BOTH the recipes path and the tag "
        "path (src.api.server.recipes_path / DEFAULT_TAG_PATH, or MACROVA_DATA_DIR) to "
        "tmp_path. Inspect the change with `git diff` before restoring anything."
    )


@pytest.fixture(scope="session", autouse=True)
def _guard_committed_recipe_data(setup_test_config):
    """Fail the session if any test changed the committed recipe or tag store.

    Compares start-of-session with end-of-session content, so a pre-existing local
    modification doesn't trip it; only writes made during the run do.
    """
    before = hash_files(GUARDED_DATA_FILES)
    yield
    changed = changed_files(before, hash_files(GUARDED_DATA_FILES))
    if changed:
        pytest.fail(committed_data_changed_message(changed), pytrace=False)


@pytest.fixture(autouse=True)
def _isolate_llm_feedback_cache(tmp_path, monkeypatch):
    """Never let a test read or write the repository's committed feedback cache.

    Tests that need a specific cache path still override the variable themselves;
    this default only guarantees isolation for tests that do not care.
    """
    monkeypatch.setenv("LLM_FEEDBACK_CACHE_PATH", str(tmp_path / "llm_feedback_cache.json"))
