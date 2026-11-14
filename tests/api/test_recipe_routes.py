"""BE-11 / BE-15: ``/api/v1/recipes`` HTTP contracts.

Maps to sprint docs:

- Create typed tags + ``default_servings`` → ``test_create_roundtrip_returns_typed_tags_and_default_servings``
- Update typed tags + ``default_servings`` → ``test_put_roundtrip_updates_default_servings_and_derivation``
- Detail includes typed tags, ``default_servings``, ``is_meal_prep_capable`` → same create + detail assertions
- Invalid ``default_servings`` → ``test_default_servings_invalid_values_return_invalid_request``
- Unknown tag → ``test_unknown_tag_is_rejected_with_structured_error`` (``TAG_NOT_FOUND``)
- Unknown tag repeatability → ``test_unknown_tag_error_is_stable_across_requests``
"""

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


def test_unknown_tag_error_is_stable_across_requests(monkeypatch, tmp_path):
    """Unknown slug resolves deterministically to the same structured ``TAG_NOT_FOUND``."""
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    base = {
        "name": "Unknown Tag Stable",
        "ingredients": [{"name": "cream of rice", "quantity": 100, "unit": "g"}],
        "tag_slugs_by_type": {"context": ["not-a-real-tag"]},
    }
    first = client.post("/api/v1/recipes", json={**base, "id": "r-unk-a"})
    second = client.post("/api/v1/recipes", json={**base, "id": "r-unk-b"})
    assert first.status_code == second.status_code == 404
    assert first.json()["error"]["code"] == second.json()["error"]["code"] == "TAG_NOT_FOUND"


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


# --- Sprint 2 BE-21: detail returns real per-100 g nutrition and unit conversions ---

import json

import pytest

from src.data_layer.nutrition_db import NutritionDB
from src.providers.local_provider import LocalIngredientProvider


_BE21_LINES = [
    {"name": "almond butter unsalted", "quantity": 2, "unit": "tbsp"},
    {"name": "banana", "quantity": 1, "unit": "large"},
    {"name": "almonds", "quantity": 30, "unit": "g"},
    {"name": "salt", "quantity": 0, "unit": "to taste"},
    {"name": "almonds", "quantity": 1, "unit": "cup"},  # no conversion on the record
    {"name": "be21 not a real ingredient", "quantity": 50, "unit": "g"},
]


def _write_be21_recipe(monkeypatch, tmp_path) -> str:
    _configure_paths(monkeypatch, tmp_path)
    rid = "r-be21-detail"
    (tmp_path / "recipes.json").write_text(
        json.dumps(
            {
                "recipes": [
                    {
                        "id": rid,
                        "name": "BE-21 detail fixture",
                        "ingredients": _BE21_LINES,
                        "cooking_time_minutes": 5,
                        "instructions": ["Mix."],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return rid


def _record(name: str) -> dict:
    import src.api.server as server

    info = LocalIngredientProvider(NutritionDB(server.ingredients_path)).get_ingredient_info(name)
    assert info is not None, name
    return info


def test_detail_returns_record_per_100g_and_unit_conversions(monkeypatch, tmp_path):
    rid = _write_be21_recipe(monkeypatch, tmp_path)
    res = TestClient(app).get(f"/api/v1/recipes/{rid}")
    assert res.status_code == 200, res.text
    lines = res.json()["ingredients"]
    assert len(lines) == len(_BE21_LINES)

    for line in lines[:3]:
        rec = _record(line["ingredient_name"])
        per_100g = rec["per_100g"]
        assert line["resolved"] is True
        assert line["calories_per_100g"] == pytest.approx(per_100g["calories"], abs=1e-6)
        assert line["protein_per_100g"] == pytest.approx(per_100g["protein_g"], abs=1e-6)
        assert line["carbs_per_100g"] == pytest.approx(per_100g["carbs_g"], abs=1e-6)
        assert line["fat_per_100g"] == pytest.approx(per_100g["fat_g"], abs=1e-6)
        expected = {"g": 1.0, **{k: float(v) for k, v in (rec.get("grams_per_unit") or {}).items()}}
        assert line["unit_conversions"] == expected

    assert lines[0]["unit_conversions"]["tbsp"] == 16.0
    assert lines[1]["unit_conversions"]["large"] == 118.0


def test_detail_to_taste_line_is_resolved_zero(monkeypatch, tmp_path):
    rid = _write_be21_recipe(monkeypatch, tmp_path)
    salt = TestClient(app).get(f"/api/v1/recipes/{rid}").json()["ingredients"][3]
    assert salt["unit"] == "to taste"
    assert salt["resolved"] is True
    assert salt["calories_per_100g"] == 0.0


def test_detail_unresolved_lines_are_returned_with_resolved_false(monkeypatch, tmp_path):
    rid = _write_be21_recipe(monkeypatch, tmp_path)
    lines = TestClient(app).get(f"/api/v1/recipes/{rid}").json()["ingredients"]

    bad_unit, unknown = lines[4], lines[5]
    assert bad_unit["ingredient_name"] == "almonds" and bad_unit["unit"] == "cup"
    assert bad_unit["resolved"] is False
    assert bad_unit["calories_per_100g"] == 0.0
    # The record is known, so its real conversions are still sent.
    assert bad_unit["unit_conversions"] == {"g": 1.0}

    assert unknown["resolved"] is False
    assert unknown["unit_conversions"] == {}
    assert unknown["calories_per_100g"] == 0.0


def test_detail_unexpected_calculator_error_is_500_envelope(monkeypatch, tmp_path):
    rid = _write_be21_recipe(monkeypatch, tmp_path)

    def _boom(self, *args, **kwargs):
        raise AttributeError("simulated calculator bug")

    monkeypatch.setattr("src.nutrition.calculator.NutritionCalculator.to_grams", _boom)
    res = TestClient(app).get(f"/api/v1/recipes/{rid}")
    assert res.status_code == 500
    body = res.json()
    assert "error" in body and body["error"]["code"]
    assert "ingredients" not in body
