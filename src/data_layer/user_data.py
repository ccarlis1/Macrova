"""Where user-writable data lives (Sprint 2 BE-22, decision W6).

One setting, ``MACROVA_DATA_DIR``, decides where a user's own data is stored:
the recipe pool, the tag store (``tag_registry`` + ``tag_aliases`` +
``tags_by_id``) and meal-prep batches.

- **Unset** (development, tests): today's repo paths, unchanged.
- **Set**: everything user-writable lives in that folder. A new folder starts
  with an **empty** recipe pool; ``setup_user_data`` creates it, and the
  sample recipes are an optional starter pack the user imports from.

Not user data, and never moved: reference data (``data/reference/``), the
shipped tag registry and the starter pack source (``recipes.json.example``).

This module is stdlib-only so any layer (models, LLM, API, CLI) can import it
without cycles. Paths are resolved on every call, never cached at import.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

ENV_VAR = "MACROVA_DATA_DIR"

# Paths used when MACROVA_DATA_DIR is unset (relative to the repo root, as before).
DEFAULT_RECIPES_PATH = "data/recipes/recipes.json"
DEFAULT_RECIPE_TAGS_PATH = "data/recipes/recipe_tags.json"
DEFAULT_MEAL_PREP_BATCHES_PATH = "data/meal_prep/batches.json"

# Shipped, read-only sources.
SHIPPED_RECIPE_TAGS_PATH = DEFAULT_RECIPE_TAGS_PATH
STARTER_RECIPES_PATH = "data/recipes/recipes.json.example"

# File names inside a user data folder.
RECIPES_FILE = "recipes.json"
RECIPE_TAGS_FILE = "recipe_tags.json"
MEAL_PREP_BATCHES_FILE = "meal_prep_batches.json"

#: Gitignored default location for ``scripts/setup_user_data.py``.
DEFAULT_USER_DATA_DIR = "user_data"


def data_dir() -> Optional[Path]:
    """The user data folder, or ``None`` when ``MACROVA_DATA_DIR`` is unset or empty."""
    raw = os.environ.get(ENV_VAR, "").strip()
    return Path(raw).expanduser() if raw else None


def _in_data_dir(file_name: str, default: str) -> str:
    folder = data_dir()
    return str(folder / file_name) if folder is not None else default


def recipes_path() -> str:
    """The user's recipe pool (``{"recipes": [...]}``)."""
    return _in_data_dir(RECIPES_FILE, DEFAULT_RECIPES_PATH)


def recipe_tags_path() -> str:
    """The user's tag store: registry, aliases and per-recipe ``tags_by_id``."""
    return _in_data_dir(RECIPE_TAGS_FILE, DEFAULT_RECIPE_TAGS_PATH)


def meal_prep_batches_path() -> str:
    """The user's meal-prep batch store."""
    return _in_data_dir(MEAL_PREP_BATCHES_FILE, DEFAULT_MEAL_PREP_BATCHES_PATH)


def setup_user_data(folder: Path, *, shipped_tags_path: str = SHIPPED_RECIPE_TAGS_PATH) -> bool:
    """Create a user data folder with an empty pool. Never touches an existing folder.

    Writes ``recipes.json`` (``{"recipes": []}``) and ``recipe_tags.json`` holding the
    shipped ``tag_registry`` and ``tag_aliases`` with an **empty** ``tags_by_id``, so the
    user can use and extend the shared tag vocabulary without inheriting anyone's recipes.
    Meal-prep batches are created on first write by their repository.

    Returns True if the folder was created, False if it already existed (left untouched).
    """
    folder = Path(folder)
    if folder.exists():
        return False
    shipped: Dict[str, Any] = json.loads(Path(shipped_tags_path).read_text(encoding="utf-8"))
    tags_payload = {
        "tag_registry": shipped.get("tag_registry", {}),
        "tag_aliases": shipped.get("tag_aliases", {}),
        "tags_by_id": {},
    }
    folder.mkdir(parents=True)
    (folder / RECIPES_FILE).write_text(json.dumps({"recipes": []}, indent=2) + "\n", encoding="utf-8")
    (folder / RECIPE_TAGS_FILE).write_text(
        json.dumps(tags_payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return True


def load_starter_recipes(path: str = STARTER_RECIPES_PATH) -> List[Dict[str, Any]]:
    """Raw rows of the starter pack (the bundled sample recipes), in file order.

    The one reader of ``recipes.json.example``: the MCP sample tools and the HTTP
    starter-pack routes both build on it.
    """
    with open(path, encoding="utf-8") as f:
        return list(json.load(f)["recipes"])
