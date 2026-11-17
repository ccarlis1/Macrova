"""Shared pytest setup so CI and local runs behave like a clean checkout.

GitHub Actions runs from the repo root with ``pip install -r requirements.txt`` and:

- ``python -m pytest tests/ -q`` (needs ``httpx`` for FastAPI TestClient)
- ``python scripts/export_openapi.py --check`` (OpenAPI snapshot must match the app)

``config/user_profile.yaml`` is personal and untracked; tests use the ``.example``
or a ``tmp_path`` fixture, never the real file.

``data/ingredients/custom_ingredients.json`` is gitignored; copy from ``*.example``
when absent. Default local nutrition is ``data/reference/ingredient_nutrition.json``
(committed). ``data/recipes/recipes.json`` is committed (§4.4); still copy from
``.example`` if a checkout is missing it.
"""

import hashlib
import shutil

import pytest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _copy_if_missing(dest: Path, example: Path) -> None:
    if dest.exists() or not example.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example, dest)


@pytest.fixture(scope="session", autouse=True)
def setup_test_config():
    """Ensure local data files that some tests open exist (copied from ``*.example``).

    ``config/user_profile.yaml`` is the owner's personal, untracked profile (Sprint 2
    W7): tests never read, create or overwrite it. They use
    ``config/user_profile.yaml.example`` or a ``tmp_path`` fixture instead.
    """
    # custom_ingredients.json: gitignored, legacy; some tests pass it explicitly (not a
    # CLI/server default -- that is data/reference/ingredient_nutrition.json).
    # recipes.json: committed CLI/server default; restored only if a checkout lacks it.
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


#: The owner's personal profile (untracked, W7). Tests must neither create nor change it.
PERSONAL_PROFILE = _REPO_ROOT / "config" / "user_profile.yaml"


@pytest.fixture(scope="session", autouse=True)
def _guard_personal_profile():
    """Fail the session if any test created, changed or deleted ``config/user_profile.yaml``."""
    before = hash_files([PERSONAL_PROFILE])
    yield
    if changed_files(before, hash_files([PERSONAL_PROFILE])):
        pytest.fail(
            "Test session modified config/user_profile.yaml (the owner's personal profile). "
            "Point the test at config/user_profile.yaml.example or a tmp_path copy "
            "(--profile, yaml_path=, or NUTRITION_USER_PROFILE_PATH).",
            pytrace=False,
        )


@pytest.fixture(autouse=True)
def _isolate_user_profile_path(tmp_path, monkeypatch):
    """Server pin/schedule routes default to a per-test path that doesn't exist yet.

    Tests that need a profile still set ``NUTRITION_USER_PROFILE_PATH`` themselves.
    """
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(tmp_path / "user_profile.yaml"))


@pytest.fixture(autouse=True)
def _isolate_llm_feedback_cache(tmp_path, monkeypatch):
    """Never let a test read or write the repository's committed feedback cache.

    Tests that need a specific cache path still override the variable themselves;
    this default only guarantees isolation for tests that do not care.
    """
    monkeypatch.setenv("LLM_FEEDBACK_CACHE_PATH", str(tmp_path / "llm_feedback_cache.json"))
