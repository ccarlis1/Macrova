import json

from fastapi.testclient import TestClient

import src.api.tag_routes as tag_routes
from src.api.server import app
from src.llm.tag_repository import (
    TagRegistry,
    load_recipe_tag_slugs,
    upsert_recipe_tag_slugs,
)


def _write_recipes(path):
    path.write_text(
        json.dumps(
            {
                "recipes": [
                    {
                        "id": "r1",
                        "name": "Recipe 1",
                        "ingredients": [
                            {"name": "chicken", "quantity": 100.0, "unit": "g"},
                        ],
                        "cooking_time_minutes": 10,
                        "instructions": ["Cook."],
                    },
                    {
                        "id": "r2",
                        "name": "Recipe 2",
                        "ingredients": [
                            {"name": "rice", "quantity": 100.0, "unit": "g"},
                        ],
                        "cooking_time_minutes": 10,
                        "instructions": ["Cook."],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


def _client_with_paths(monkeypatch, tmp_path):
    tag_path = tmp_path / "recipe_tags.json"
    recipes_path = tmp_path / "recipes.json"
    _write_recipes(recipes_path)
    monkeypatch.setattr(tag_routes, "_tag_path_getter", lambda: str(tag_path))
    monkeypatch.setattr(tag_routes, "_recipes_path_getter", lambda: str(recipes_path))
    return TestClient(app), str(tag_path)


def test_create_tag_and_duplicate_conflict(monkeypatch, tmp_path):
    client, _tag_path = _client_with_paths(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/tags",
        json={"display": "Meal Prep", "type": "context"},
    )
    assert response.status_code == 200
    assert response.json()["slug"] == "meal-prep"
    assert response.json()["source"] == "user"

    conflict = client.post(
        "/api/v1/tags",
        json={"display": "Meal Prep", "type": "context"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "TAG_CONFLICT"


def test_list_tags_filters_by_type_and_counts_live_recipes(monkeypatch, tmp_path):
    client, tag_path = _client_with_paths(monkeypatch, tmp_path)
    registry = TagRegistry(tag_path)
    registry.create(display="Meal Prep", type="context")
    upsert_recipe_tag_slugs(
        tag_path, {"r1": ["high-fiber", "meal-prep"], "missing": ["high-fiber"]}
    )

    response = client.get("/api/v1/tags", params={"type": "nutrition"})

    assert response.status_code == 200
    high_fiber = next(tag for tag in response.json() if tag["slug"] == "high-fiber")
    assert high_fiber["recipe_count"] == 1
    assert all(tag["type"] == "nutrition" for tag in response.json())


def test_alias_and_alias_conflict(monkeypatch, tmp_path):
    client, _tag_path = _client_with_paths(monkeypatch, tmp_path)
    client.post("/api/v1/tags", json={"display": "Meal Prep", "type": "context"})
    client.post("/api/v1/tags", json={"display": "Batch Cooking", "type": "context"})

    response = client.post(
        "/api/v1/tags/meal-prep/alias",
        json={"alias_slug": "prep-ahead"},
    )
    assert response.status_code == 200
    assert "prep-ahead" in response.json()["aliases"]

    conflict = client.post(
        "/api/v1/tags/meal-prep/alias",
        json={"alias_slug": "batch-cooking"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "TAG_CONFLICT"


def test_merge_rewrites_assignments(monkeypatch, tmp_path):
    client, tag_path = _client_with_paths(monkeypatch, tmp_path)
    client.post("/api/v1/tags", json={"display": "Meal Prep", "type": "context"})
    client.post("/api/v1/tags", json={"display": "Batch Cooking", "type": "context"})
    upsert_recipe_tag_slugs(tag_path, {"r1": ["batch-cooking"], "r2": ["meal-prep"]})

    response = client.post("/api/v1/tags/batch-cooking/merge_into/meal-prep")

    assert response.status_code == 200
    assert load_recipe_tag_slugs(tag_path) == {"r1": ["meal-prep"], "r2": ["meal-prep"]}
    assert TagRegistry(tag_path).resolve("batch-cooking").slug == "meal-prep"
