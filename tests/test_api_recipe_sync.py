"""Tests for src/api/recipe_sync.py — atomic upsert-by-id into the recipe store."""

import json

import pytest
from pydantic import ValidationError

from src.api.recipe_sync import (
    RecipeSyncIngredientLine,
    RecipeSyncItem,
    atomic_upsert_recipes_by_id,
)


def _item(recipe_id="r1", name="Oatmeal", unit="g", quantity=80.0):
    return RecipeSyncItem(
        id=recipe_id,
        name=name,
        ingredients=[RecipeSyncIngredientLine(name="oats", quantity=quantity, unit=unit)],
        cooking_time_minutes=10,
        instructions=["cook"],
    )


def _read_store(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_insert_into_missing_file_creates_store(tmp_path):
    path = tmp_path / "recipes.json"

    synced = atomic_upsert_recipes_by_id(path=str(path), items=[_item()])

    assert synced == ["r1"]
    stored = _read_store(path)
    assert [r["id"] for r in stored["recipes"]] == ["r1"]


def test_upsert_replaces_existing_id_and_appends_new(tmp_path):
    path = tmp_path / "recipes.json"
    atomic_upsert_recipes_by_id(path=str(path), items=[_item("r1", name="Old name")])

    synced = atomic_upsert_recipes_by_id(
        path=str(path),
        items=[_item("r1", name="New name"), _item("r2", name="Banana")],
    )

    assert synced == ["r1", "r2"]
    stored = _read_store(path)["recipes"]
    assert [r["id"] for r in stored] == ["r1", "r2"]
    assert stored[0]["name"] == "New name"


def test_to_taste_units_normalize_quantity_to_zero(tmp_path):
    path = tmp_path / "recipes.json"
    item = RecipeSyncItem(
        id="r1",
        name="Soup",
        ingredients=[
            RecipeSyncIngredientLine(name="salt", quantity=5.0, unit="To Taste"),
        ],
    )

    atomic_upsert_recipes_by_id(path=str(path), items=[item])

    line = _read_store(path)["recipes"][0]["ingredients"][0]
    assert line["quantity"] == 0.0
    assert line["unit"] == "to taste"


def test_no_tmp_residue_after_write(tmp_path):
    path = tmp_path / "recipes.json"
    atomic_upsert_recipes_by_id(path=str(path), items=[_item()])

    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "recipes.json"]
    assert leftovers == []


def test_item_fields_are_stripped_and_empty_rejected():
    item = RecipeSyncItem(
        id="  r1  ",
        name="  Oatmeal ",
        ingredients=[RecipeSyncIngredientLine(name=" oats ", quantity=1.0, unit=" g ")],
    )
    assert item.id == "r1"
    assert item.name == "Oatmeal"
    assert item.ingredients[0].name == "oats"

    with pytest.raises(ValidationError):
        RecipeSyncItem(id="   ", name="x", ingredients=[
            RecipeSyncIngredientLine(name="oats", quantity=1.0, unit="g")
        ])

    with pytest.raises(ValidationError):
        RecipeSyncItem(id="r1", name="x", ingredients=[])


def test_non_object_store_file_raises_value_error(tmp_path):
    path = tmp_path / "recipes.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    with pytest.raises(ValueError):
        atomic_upsert_recipes_by_id(path=str(path), items=[_item()])
