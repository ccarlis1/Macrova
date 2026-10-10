"""One-shot migration that assigns canonical time-* tags to recipes."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.llm.time_bucket import time_bucket


def _is_time_tag(tag: Dict[str, Any]) -> bool:
    slug = tag.get("slug")
    return isinstance(slug, str) and slug.startswith("time-")


def _normalize_tags(raw_tags: Any) -> List[Dict[str, str]]:
    if not isinstance(raw_tags, list):
        return []
    normalized: List[Dict[str, str]] = []
    for raw_tag in raw_tags:
        if not isinstance(raw_tag, dict):
            continue
        slug = raw_tag.get("slug")
        tag_type = raw_tag.get("type")
        if not isinstance(slug, str) or not isinstance(tag_type, str):
            continue
        normalized.append({"slug": slug, "type": tag_type})
    return normalized


def migrate_recipes_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int], List[str]]:
    recipes = payload.get("recipes", [])
    if not isinstance(recipes, list):
        raise ValueError("Expected root key 'recipes' to be a list.")

    summary = {"total": 0, "tagged": 0, "changed": 0, "unchanged": 0}
    changes: List[str] = []

    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue
        summary["total"] += 1
        minutes = recipe.get("cooking_time_minutes")
        if not isinstance(minutes, int):
            raise ValueError(
                f"Recipe {recipe.get('id', '<unknown>')} has non-integer cooking_time_minutes."
            )

        new_time_slug = time_bucket(minutes)
        existing_tags = _normalize_tags(recipe.get("tags", []))
        preserved_tags = [tag for tag in existing_tags if not _is_time_tag(tag)]
        new_tags = preserved_tags + [{"slug": new_time_slug, "type": "time"}]
        recipe["tags"] = new_tags
        summary["tagged"] += 1

        recipe_id = str(recipe.get("id", ""))
        recipe_name = str(recipe.get("name", ""))
        if existing_tags != new_tags:
            summary["changed"] += 1
            changes.append(f"{recipe_id}|{recipe_name}: {existing_tags} -> {new_tags}")
        else:
            summary["unchanged"] += 1

    return payload, summary, changes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill recipes.json with canonical time-* tags."
    )
    parser.add_argument(
        "recipes_path",
        nargs="?",
        default="data/recipes/recipes.json",
        help="Path to recipes.json (default: data/recipes/recipes.json)",
    )
    parser.add_argument(
        "--tag-repo-path",
        default="data/recipes/recipe_tags.json",
        help="Path to recipe_tags.json (default: data/recipes/recipe_tags.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print proposed changes without writing files.",
    )
    args = parser.parse_args()

    recipes_path = Path(args.recipes_path)
    if not recipes_path.exists():
        raise FileNotFoundError(f"recipes file not found: {recipes_path}")

    os.environ["NUTRITION_TAG_REPO_PATH"] = str(args.tag_repo_path)

    with recipes_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Expected recipes file root to be a JSON object.")

    migrated, summary, changes = migrate_recipes_payload(payload)

    if args.dry_run:
        for line in changes:
            print(line)
        print(summary)
        return

    backup_path = recipes_path.with_suffix(recipes_path.suffix + ".bak")
    shutil.copy2(recipes_path, backup_path)

    with recipes_path.open("w", encoding="utf-8") as f:
        json.dump(migrated, f, indent=2)
    print(summary)


if __name__ == "__main__":
    main()
