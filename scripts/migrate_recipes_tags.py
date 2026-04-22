"""Backfill recipes.json with DM-2 recipe fields.

Adds missing:
- default_servings: 1
- tags: []
Creates a .bak backup before overwrite.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict


def migrate_recipes_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    recipes = payload.get("recipes", [])
    if not isinstance(recipes, list):
        raise ValueError("Expected root key 'recipes' to be a list.")

    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue
        recipe.setdefault("default_servings", 1)
        recipe.setdefault("tags", [])
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill recipe tags/default_servings in recipes.json."
    )
    parser.add_argument(
        "recipes_path",
        nargs="?",
        default="data/recipes/recipes.json",
        help="Path to recipes.json (default: data/recipes/recipes.json)",
    )
    args = parser.parse_args()

    recipes_path = Path(args.recipes_path)
    if not recipes_path.exists():
        raise FileNotFoundError(f"recipes file not found: {recipes_path}")

    with recipes_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Expected recipes file root to be a JSON object.")

    migrated = migrate_recipes_payload(payload)

    backup_path = recipes_path.with_suffix(recipes_path.suffix + ".bak")
    shutil.copy2(recipes_path, backup_path)

    with recipes_path.open("w", encoding="utf-8") as f:
        json.dump(migrated, f, indent=2)


if __name__ == "__main__":
    main()
