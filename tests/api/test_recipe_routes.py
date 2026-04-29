from fastapi.testclient import TestClient

from src.api.server import app


def _configure_paths(monkeypatch, tmp_path):
    recipes_file = tmp_path / "recipes.json"
    recipes_file.write_text('{"recipes": []}', encoding="utf-8")
    tags_file = tmp_path / "recipe_tags.json"
    monkeypatch.setattr("src.api.server.recipes_path", str(recipes_file))
    monkeypatch.setattr("src.api.server.DEFAULT_TAG_PATH", str(tags_file))


def test_create_roundtrip_returns_typed_tags_and_default_servings(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    rid = "r-route-create"

    create_res = client.post(
        "/api/v1/recipes",
        json={
            "id": rid,
            "name": "Route Create Recipe",
            "ingredients": [{"name": "cream of rice", "quantity": 100, "unit": "g"}],
            "default_servings": 2,
            "tag_slugs_by_type": {"context": ["meal-prep"]},
        },
    )
    assert create_res.status_code == 200
    assert create_res.json()["synced_ids"] == [rid]

    detail_res = client.get(f"/api/v1/recipes/{rid}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["default_servings"] == 2
    assert detail["servings"] == 2
    assert detail["tag_slugs_by_type"]["context"] == ["meal-prep"]
    assert detail["is_meal_prep_capable"] is True


def test_put_roundtrip_updates_default_servings_and_derivation(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    rid = "r-route-put"

    client.post(
        "/api/v1/recipes",
        json={
            "id": rid,
            "name": "Route Put Recipe",
            "ingredients": [{"name": "cream of rice", "quantity": 100, "unit": "g"}],
            "default_servings": 2,
            "tag_slugs_by_type": {"context": ["meal-prep"]},
        },
    )

    put_res = client.put(
        f"/api/v1/recipes/{rid}",
        json={
            "id": rid,
            "name": "Route Put Recipe",
            "ingredients": [{"name": "cream of rice", "quantity": 100, "unit": "g"}],
            "default_servings": 1,
            "tag_slugs_by_type": {"context": ["meal-prep"]},
        },
    )
    assert put_res.status_code == 200

    detail = client.get(f"/api/v1/recipes/{rid}").json()
    assert detail["default_servings"] == 1
    assert detail["is_meal_prep_capable"] is False


def test_unknown_tag_is_rejected_with_structured_error(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)

    res = client.post(
        "/api/v1/recipes",
        json={
            "id": "r-route-unknown-tag",
            "name": "Unknown Tag Recipe",
            "ingredients": [{"name": "cream of rice", "quantity": 100, "unit": "g"}],
            "tag_slugs_by_type": {"context": ["not-a-real-tag"]},
        },
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "TAG_NOT_FOUND"


def test_default_servings_invalid_values_return_invalid_request(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)

    invalid_values = [0, -1, 1.5, "2"]
    for value in invalid_values:
        res = client.post(
            "/api/v1/recipes",
            json={
                "id": f"r-invalid-{value}",
                "name": "Invalid Servings Recipe",
                "ingredients": [{"name": "cream of rice", "quantity": 100, "unit": "g"}],
                "default_servings": value,
            },
        )
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_REQUEST"


def test_legacy_payload_still_works_with_defaults(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    rid = "r-route-legacy"

    res = client.post(
        "/api/v1/recipes",
        json={
            "id": rid,
            "name": "Legacy Payload Recipe",
            "ingredients": [{"name": "cream of rice", "quantity": 100, "unit": "g"}],
        },
    )
    assert res.status_code == 200

    detail = client.get(f"/api/v1/recipes/{rid}").json()
    assert detail["default_servings"] == 1
    assert detail["tag_slugs_by_type"] == {}
    assert detail["is_meal_prep_capable"] is False
