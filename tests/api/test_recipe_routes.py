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
    # BE-19: every saved recipe gets a tags_by_id entry with the derived time slug (0 min).
    assert detail["tag_slugs_by_type"] == {"time": ["time-0"]}
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


# --- Sprint 2 BE-18: `to taste` only for seasonings at save time ---


def _to_taste_item(rid: str, name: str) -> dict:
    return {
        "id": rid,
        "name": "To taste fixture",
        "ingredients": [
            {"name": "almonds", "quantity": 30, "unit": "g"},
            {"name": name, "quantity": 0, "unit": "to taste"},
        ],
    }


def _assert_quantity_required(res, ingredient: str):
    assert res.status_code == 422, res.text
    err = res.json()["error"]
    assert err["code"] == "INGREDIENT_QUANTITY_REQUIRED"
    assert err["details"] == {"ingredient": ingredient}


@pytest.mark.parametrize("route", ["sync", "create", "put"])
def test_save_rejects_non_seasoning_to_taste(route, monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    item = _to_taste_item("r-be18", "rolled oats")
    if route == "sync":
        res = client.post("/api/v1/recipes/sync", json={"recipes": [item]})
    elif route == "create":
        res = client.post("/api/v1/recipes", json=item)
    else:
        res = client.put("/api/v1/recipes/r-be18", json=item)

    _assert_quantity_required(res, "rolled oats")
    # Nothing was stored: the request is rejected before the write.
    assert json.loads((tmp_path / "recipes.json").read_text())["recipes"] == []


def test_sync_rejects_whole_batch_when_one_line_needs_grams(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    good = {"id": "r-good", "name": "Good", "ingredients": [{"name": "almonds", "quantity": 30, "unit": "g"}]}
    res = TestClient(app).post(
        "/api/v1/recipes/sync", json={"recipes": [good, _to_taste_item("r-bad", "cherry tomatoes")]}
    )
    _assert_quantity_required(res, "cherry tomatoes")
    assert json.loads((tmp_path / "recipes.json").read_text())["recipes"] == []


def test_save_accepts_seasoning_to_taste(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    res = TestClient(app).post("/api/v1/recipes", json=_to_taste_item("r-salt", "salt"))
    assert res.status_code == 200, res.text
    stored = json.loads((tmp_path / "recipes.json").read_text())["recipes"][0]
    assert stored["ingredients"][1] == {"name": "salt", "quantity": 0.0, "unit": "to taste"}


# --- Sprint 2 BE-19: saves are plannable (unit conversions, rejection, sync errors, tags) ---

from src.llm.tag_filter import filter_recipe_ids_by_preferences
from src.llm.tag_repository import load_recipe_tags, upsert_recipe_tags
from src.llm.schemas import RecipeTagsJson


def _be19_item(rid: str, *lines: dict, **extra) -> dict:
    return {
        "id": rid,
        "name": f"BE-19 {rid}",
        "ingredients": list(lines) or [{"name": "almonds", "quantity": 30, "unit": "g"}],
        "cooking_time_minutes": 10,
        **extra,
    }


def _stored(tmp_path) -> list:
    return json.loads((tmp_path / "recipes.json").read_text())["recipes"]


def _tags(tmp_path) -> dict:
    return load_recipe_tags(str(tmp_path / "recipe_tags.json"))


def test_line_grams_per_unit_round_trips_to_detail_unit_conversions(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    item = _be19_item(
        "r-be19-gpu",
        {"name": "almonds", "quantity": 1, "unit": "cup", "grams_per_unit": 143},
        {"name": "almonds", "quantity": 30, "unit": "g"},
    )
    res = client.post("/api/v1/recipes/sync", json={"recipes": [item]})
    assert res.status_code == 200, res.text
    assert res.json() == {"synced_ids": ["r-be19-gpu"], "errors": []}

    lines = _stored(tmp_path)[0]["ingredients"]
    assert lines[0] == {"name": "almonds", "quantity": 1.0, "unit": "cup", "grams_per_unit": 143.0}
    # Persisted only when set (additive).
    assert "grams_per_unit" not in lines[1]

    detail = client.get("/api/v1/recipes/r-be19-gpu").json()["ingredients"]
    assert detail[0]["unit_conversions"] == {"g": 1.0, "cup": 143.0}
    assert detail[0]["resolved"] is True
    assert detail[1]["unit_conversions"] == {"g": 1.0}


def test_line_grams_per_unit_must_be_positive(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    item = _be19_item("r-be19-zero", {"name": "almonds", "quantity": 1, "unit": "cup", "grams_per_unit": 0})
    res = TestClient(app).post("/api/v1/recipes", json=item)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_REQUEST"


def test_record_conversion_wins_and_line_not_needed(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    item = _be19_item("r-be19-rec", {"name": "almond butter unsalted", "quantity": 2, "unit": "tbsp"})
    res = TestClient(app).post("/api/v1/recipes", json=item)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize("route", ["create", "put"])
def test_single_save_rejects_unit_without_conversion(route, monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    item = _be19_item("r-be19-cup", {"name": "almonds", "quantity": 1, "unit": "cup"})
    if route == "create":
        res = client.post("/api/v1/recipes", json=item)
    else:
        res = client.put("/api/v1/recipes/r-be19-cup", json=item)
    assert res.status_code == 400, res.text
    err = res.json()["error"]
    assert err["code"] == "UNIT_NOT_CONVERTIBLE"
    assert err["details"] == {"ingredient": "almonds", "unit": "cup"}
    assert _stored(tmp_path) == []
    assert "r-be19-cup" not in _tags(tmp_path)


@pytest.mark.parametrize("route", ["create", "put"])
def test_single_save_rejects_unknown_ingredient(route, monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    item = _be19_item("r-be19-unk", {"name": "be19 not a real ingredient", "quantity": 50, "unit": "g"})
    if route == "create":
        res = client.post("/api/v1/recipes", json=item)
    else:
        res = client.put("/api/v1/recipes/r-be19-unk", json=item)
    assert res.status_code == 400, res.text
    err = res.json()["error"]
    assert err["code"] == "INGREDIENT_UNRESOLVED"
    assert err["details"] == {"ingredient": "be19 not a real ingredient", "unit": "g"}
    assert _stored(tmp_path) == []


def test_sync_skips_unplannable_items_and_reports_errors(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    good = _be19_item("r-be19-good")
    bad_unit = _be19_item("r-be19-bad-unit", {"name": "almonds", "quantity": 1, "unit": "cup"})
    bad_name = _be19_item("r-be19-bad-name", {"name": "be19 not a real ingredient", "quantity": 5, "unit": "g"})
    res = TestClient(app).post("/api/v1/recipes/sync", json={"recipes": [bad_unit, good, bad_name]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["synced_ids"] == ["r-be19-good"]
    assert len(body["errors"]) == 2
    unit_msg, name_msg = body["errors"]
    for msg, rid, ing, unit in (
        (unit_msg, "r-be19-bad-unit", "almonds", "cup"),
        (name_msg, "r-be19-bad-name", "be19 not a real ingredient", "g"),
    ):
        assert rid in msg and ing in msg and f"'{unit}'" in msg
    assert unit_msg.startswith("r-be19-bad-unit: UNIT_NOT_CONVERTIBLE: ")
    assert name_msg.startswith("r-be19-bad-name: INGREDIENT_UNRESOLVED: ")
    assert [r["id"] for r in _stored(tmp_path)] == ["r-be19-good"]
    assert set(_tags(tmp_path)) == {"r-be19-good"}


def test_sync_untagged_recipe_gets_derived_time_tags_and_passes_pool_filter(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    tags_path = str(tmp_path / "recipe_tags.json")
    upsert_recipe_tags(
        tags_path,
        {
            "r-curated": RecipeTagsJson(
                cuisine="italian",
                cost_level="cheap",
                prep_time_bucket="quick_meal",
                dietary_flags=["vegetarian"],
                tag_slugs_by_type={"context": ["meal-prep"]},
            )
        },
    )
    res = TestClient(app).post("/api/v1/recipes/sync", json={"recipes": [_be19_item("r-be19-app")]})
    assert res.status_code == 200, res.text

    tags = _tags(tmp_path)
    app_tags = tags["r-be19-app"]
    assert app_tags.prep_time_bucket.value == "quick_meal"
    assert app_tags.tag_slugs_by_type == {"time": ["time-2"]}
    assert (app_tags.cuisine, app_tags.cost_level.value, app_tags.dietary_flags) == ("unknown", "standard", [])
    # Merge mode: the unrelated curated entry survives untouched.
    assert tags["r-curated"].cuisine == "italian"
    assert tags["r-curated"].tag_slugs_by_type == {"context": ["meal-prep"]}

    kept = filter_recipe_ids_by_preferences(tags, {"prep_time_bucket": "quick_meal"})
    assert "r-be19-app" in kept
    assert "r-be19-app" in filter_recipe_ids_by_preferences(tags, {"cost_level": "standard"})


def test_tagged_new_recipe_uses_derived_bucket_not_weeknight_default(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    item = _be19_item("r-be19-long", tag_slugs_by_type={"context": ["meal-prep"]}, cooking_time_minutes=45)
    assert TestClient(app).post("/api/v1/recipes", json=item).status_code == 200
    tags = _tags(tmp_path)["r-be19-long"]
    assert tags.prep_time_bucket.value == "meal_prep"
    assert tags.tag_slugs_by_type == {"context": ["meal-prep"], "time": ["time-4"]}


def test_sync_cuisine_cost_and_dietary_flags_round_trip_and_persist(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    first = _be19_item(
        "r-be19-meta",
        cuisine="mexican",
        cost_level="cheap",
        dietary_flags=["vegetarian", "gluten_free"],
        tag_slugs_by_type={"context": ["meal-prep"]},
    )
    assert client.post("/api/v1/recipes/sync", json={"recipes": [first]}).status_code == 200
    tags = _tags(tmp_path)["r-be19-meta"]
    assert tags.cuisine == "mexican"
    assert tags.cost_level.value == "cheap"
    assert [f.value for f in tags.dietary_flags] == ["vegetarian", "gluten_free"]

    # Omitted fields keep the prior value; a new cook time re-derives the bucket.
    second = _be19_item("r-be19-meta", cooking_time_minutes=3)
    assert client.put("/api/v1/recipes/r-be19-meta", json=second).status_code == 200
    tags = _tags(tmp_path)["r-be19-meta"]
    assert (tags.cuisine, tags.cost_level.value) == ("mexican", "cheap")
    assert [f.value for f in tags.dietary_flags] == ["vegetarian", "gluten_free"]
    assert tags.prep_time_bucket.value == "snack"
    assert tags.tag_slugs_by_type == {"context": ["meal-prep"], "time": ["time-1"]}

    third = _be19_item("r-be19-meta", cost_level="premium", dietary_flags=[])
    assert client.post("/api/v1/recipes", json=third).status_code == 200
    tags = _tags(tmp_path)["r-be19-meta"]
    assert (tags.cuisine, tags.cost_level.value, tags.dietary_flags) == ("mexican", "premium", [])


@pytest.mark.parametrize(
    "field,value",
    [("cuisine", "martian"), ("cost_level", "free"), ("dietary_flags", ["keto"])],
)
def test_out_of_vocabulary_tag_fields_are_invalid_request(field, value, monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    res = TestClient(app).post(
        "/api/v1/recipes/sync", json={"recipes": [_be19_item("r-be19-oov", **{field: value})]}
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_REQUEST"
    assert _stored(tmp_path) == []


def test_line_grams_per_unit_survives_recipe_db_save(monkeypatch, tmp_path):
    """Deleting another recipe rewrites the store via RecipeDB.save; line weights stay."""
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    keep = _be19_item("r-be19-keep", {"name": "almonds", "quantity": 1, "unit": "cup", "grams_per_unit": 143})
    gone = _be19_item("r-be19-gone")
    assert client.post("/api/v1/recipes/sync", json={"recipes": [keep, gone]}).json()["errors"] == []
    assert client.delete("/api/v1/recipes/r-be19-gone").status_code == 200
    (row,) = _stored(tmp_path)
    assert row["ingredients"][0]["grams_per_unit"] == 143.0


# --- BE-19 follow-up: sent dietary_flags pass the tagger's ingredient-consistency gate ---


def _vegan_honey_item(rid: str) -> dict:
    return _be19_item(
        rid,
        {"name": "almonds", "quantity": 30, "unit": "g"},
        {"name": "honey", "quantity": 1, "unit": "tbsp"},
        dietary_flags=["vegetarian", "vegan"],
    )


@pytest.mark.parametrize("route", ["create", "put"])
def test_single_save_rejects_dietary_flag_contradicted_by_ingredient(route, monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    client = TestClient(app)
    item = _vegan_honey_item("r-be19-vegan")
    if route == "create":
        res = client.post("/api/v1/recipes", json=item)
    else:
        res = client.put("/api/v1/recipes/r-be19-vegan", json=item)
    assert res.status_code == 400, res.text
    err = res.json()["error"]
    assert err["code"] == "INVALID_REQUEST"
    assert "'vegan'" in err["message"] and "'honey'" in err["message"]
    # vegetarian is consistent with honey and is not named.
    assert "vegetarian" not in err["message"]
    assert _stored(tmp_path) == []
    assert "r-be19-vegan" not in _tags(tmp_path)


def test_sync_skips_item_whose_dietary_flag_is_contradicted(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    good = _be19_item("r-be19-flag-ok", dietary_flags=["vegan", "gluten_free"])
    bad = _vegan_honey_item("r-be19-flag-bad")
    res = TestClient(app).post("/api/v1/recipes/sync", json={"recipes": [bad, good]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["synced_ids"] == ["r-be19-flag-ok"]
    (msg,) = body["errors"]
    assert msg.startswith("r-be19-flag-bad: INVALID_REQUEST: ")
    assert "'vegan'" in msg and "'honey'" in msg
    assert [r["id"] for r in _stored(tmp_path)] == ["r-be19-flag-ok"]
    tags = _tags(tmp_path)
    assert set(tags) == {"r-be19-flag-ok"}
    assert [f.value for f in tags["r-be19-flag-ok"].dietary_flags] == ["vegan", "gluten_free"]


# --- BE-19 follow-up: client tag types replace stored ones; tag_metadata follows ---


def test_client_tag_types_replace_stored_and_prune_tag_metadata(monkeypatch, tmp_path):
    from src.llm.recipe_tagger import _quarantined_metadata
    from src.llm.tag_repository import _raw_recipe_tag_slug_set, _recipe_tag_slug_set

    _configure_paths(monkeypatch, tmp_path)
    tags_path = str(tmp_path / "recipe_tags.json")
    # Tagger-style prior entry: LLM-proposed slugs carry per-recipe tag_metadata.
    upsert_recipe_tags(
        tags_path,
        {
            "r-be19-llm": RecipeTagsJson(
                cuisine="italian",
                cost_level="cheap",
                prep_time_bucket="quick_meal",
                tag_slugs_by_type={
                    "context": ["meal-prep"],
                    "nutrition": ["high-fiber"],
                    "time": ["time-2"],
                },
                tag_metadata=_quarantined_metadata(["meal-prep", "high-fiber"], tags_path),
            )
        },
    )
    item = _be19_item("r-be19-llm", tag_slugs_by_type={"context": ["meal-prep"]})
    assert TestClient(app).post("/api/v1/recipes/sync", json={"recipes": [item]}).status_code == 200

    entry = _tags(tmp_path)["r-be19-llm"]
    # Sent types replace the stored types as a whole: the nutrition type is gone.
    assert entry.tag_slugs_by_type == {"context": ["meal-prep"], "time": ["time-2"]}
    # Metadata of the removed slug is pruned; the surviving slug stays proposed.
    assert set(entry.tag_metadata or {}) == {"meal-prep"}
    assert entry.tag_metadata["meal-prep"].eligibility == "proposed"
    assert entry.tag_metadata["meal-prep"].source == "llm"
    assert "high-fiber" not in _recipe_tag_slug_set(entry)

    raw = json.loads((tmp_path / "recipe_tags.json").read_text())["tags_by_id"]["r-be19-llm"]
    assert "high-fiber" not in _raw_recipe_tag_slug_set(raw)
    assert entry.cuisine == "italian"
