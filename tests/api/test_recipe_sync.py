from fastapi.testclient import TestClient

from src.api.server import app


def _configure_paths(monkeypatch, tmp_path):
    recipes_file = tmp_path / "recipes.json"
    recipes_file.write_text('{"recipes": []}', encoding="utf-8")
    tags_file = tmp_path / "recipe_tags.json"
    monkeypatch.setattr("src.api.server.recipes_path", str(recipes_file))
    monkeypatch.setattr("src.api.server.DEFAULT_TAG_PATH", str(tags_file))


def test_sync_roundtrip_tags_and_default_servings(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    rid = "r-sync-roundtrip"

    sync_res = client.post(
        "/api/v1/recipes/sync",
        json={
            "recipes": [
                {
                    "id": rid,
                    "name": "Sync Roundtrip Recipe",
                    "ingredients": [
                        {"name": "cream of rice", "quantity": 100, "unit": "g"},
                    ],
                    "default_servings": 3,
                    "tag_slugs_by_type": {"context": ["meal-prep"]},
                }
            ]
        },
    )
    assert sync_res.status_code == 200
    assert sync_res.json()["synced_ids"] == [rid]

    detail = client.get(f"/api/v1/recipes/{rid}").json()
    assert detail["default_servings"] == 3
    assert detail["tag_slugs_by_type"]["context"] == ["meal-prep"]
    assert detail["is_meal_prep_capable"] is True


def test_sync_unknown_tag_is_rejected(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)

    res = client.post(
        "/api/v1/recipes/sync",
        json={
            "recipes": [
                {
                    "id": "r-sync-unknown",
                    "name": "Sync Unknown Tag",
                    "ingredients": [
                        {"name": "cream of rice", "quantity": 100, "unit": "g"},
                    ],
                    "tag_slugs_by_type": {"context": ["unknown-tag-value"]},
                }
            ]
        },
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "TAG_NOT_FOUND"


def test_sync_backward_compatible_without_new_fields(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    rid = "r-sync-legacy"

    res = client.post(
        "/api/v1/recipes/sync",
        json={
            "recipes": [
                {
                    "id": rid,
                    "name": "Sync Legacy",
                    "ingredients": [
                        {"name": "cream of rice", "quantity": 100, "unit": "g"},
                    ],
                }
            ]
        },
    )
    assert res.status_code == 200
    assert res.json()["synced_ids"] == [rid]

    detail = client.get(f"/api/v1/recipes/{rid}").json()
    assert detail["default_servings"] == 1
    assert detail["tag_slugs_by_type"] == {}
