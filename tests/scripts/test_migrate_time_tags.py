from __future__ import annotations

import json
from pathlib import Path

from scripts.migrate_recipes_time_tags import migrate_recipes_payload


def _write_tag_repo(path: Path) -> None:
    payload = {
        "tags_by_id": {},
        "tag_registry": {
            "time-0": {
                "slug": "time-0",
                "display": "Instant",
                "tag_type": "time",
                "source": "system",
                "created_at": "1970-01-01T00:00:00Z",
                "aliases": [],
            },
            "time-1": {
                "slug": "time-1",
                "display": "Quick",
                "tag_type": "time",
                "source": "system",
                "created_at": "1970-01-01T00:00:00Z",
                "aliases": [],
            },
            "time-2": {
                "slug": "time-2",
                "display": "Fast",
                "tag_type": "time",
                "source": "system",
                "created_at": "1970-01-01T00:00:00Z",
                "aliases": [],
            },
            "time-3": {
                "slug": "time-3",
                "display": "Medium",
                "tag_type": "time",
                "source": "system",
                "created_at": "1970-01-01T00:00:00Z",
                "aliases": [],
            },
            "time-4": {
                "slug": "time-4",
                "display": "Long",
                "tag_type": "time",
                "source": "system",
                "created_at": "1970-01-01T00:00:00Z",
                "aliases": [],
            },
        },
        "tag_aliases": {},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _time_slugs(recipe: dict) -> list[str]:
    tags = recipe.get("tags", [])
    out: list[str] = []
    if not isinstance(tags, list):
        return out
    for tag in tags:
        if isinstance(tag, dict) and str(tag.get("slug", "")).startswith("time-"):
            out.append(str(tag["slug"]))
    return out


def test_migration_assigns_buckets_and_cleans_duplicates(monkeypatch, tmp_path: Path) -> None:
    tag_repo = tmp_path / "recipe_tags.json"
    _write_tag_repo(tag_repo)
    monkeypatch.setenv("NUTRITION_TAG_REPO_PATH", str(tag_repo))

    payload = {
        "recipes": [
            {
                "id": "r0",
                "name": "Zero",
                "cooking_time_minutes": 0,
                "ingredients": [],
                "instructions": [],
                "tags": [{"slug": "time-4", "type": "time"}],
            },
            {
                "id": "r2",
                "name": "Two",
                "cooking_time_minutes": 2,
                "ingredients": [],
                "instructions": [],
                "tags": [
                    {"slug": "time-1", "type": "time"},
                    {"slug": "time-3", "type": "time"},
                    {"slug": "high-fiber", "type": "nutrition"},
                ],
            },
            {
                "id": "r20",
                "name": "Twenty",
                "cooking_time_minutes": 20,
                "ingredients": [],
                "instructions": [],
                "tags": [{"slug": "meal-prep", "type": "context"}],
            },
            {
                "id": "r45",
                "name": "FortyFive",
                "cooking_time_minutes": 45,
                "ingredients": [],
                "instructions": [],
            },
        ]
    }

    migrated, summary, _ = migrate_recipes_payload(payload)
    recipes = migrated["recipes"]

    assert summary == {"total": 4, "tagged": 4, "changed": 4, "unchanged": 0}
    assert _time_slugs(recipes[0]) == ["time-0"]
    assert _time_slugs(recipes[1]) == ["time-1"]
    assert _time_slugs(recipes[2]) == ["time-3"]
    assert _time_slugs(recipes[3]) == ["time-4"]

    assert {"slug": "high-fiber", "type": "nutrition"} in recipes[1]["tags"]
    assert {"slug": "meal-prep", "type": "context"} in recipes[2]["tags"]
    for recipe in recipes:
        assert len(_time_slugs(recipe)) == 1


def test_migration_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    tag_repo = tmp_path / "recipe_tags.json"
    _write_tag_repo(tag_repo)
    monkeypatch.setenv("NUTRITION_TAG_REPO_PATH", str(tag_repo))

    payload = {
        "recipes": [
            {
                "id": "stable",
                "name": "Stable",
                "cooking_time_minutes": 15,
                "ingredients": [],
                "instructions": [],
                "tags": [{"slug": "time-2", "type": "time"}],
            }
        ]
    }

    first, first_summary, _ = migrate_recipes_payload(payload)
    second, second_summary, _ = migrate_recipes_payload(first)

    assert first["recipes"][0]["tags"] == second["recipes"][0]["tags"]
    assert first_summary == {"total": 1, "tagged": 1, "changed": 0, "unchanged": 1}
    assert second_summary == {"total": 1, "tagged": 1, "changed": 0, "unchanged": 1}
