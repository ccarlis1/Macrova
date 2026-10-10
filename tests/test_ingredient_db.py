"""Tests for src/data_layer/ingredient_db.py — JSON-backed ingredient metadata."""

import json

import pytest

from src.data_layer.ingredient_db import IngredientDB


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "ingredients.json"
    path.write_text(
        json.dumps(
            {
                "ingredients": [
                    {
                        "name": "Oats",
                        "aliases": ["rolled oats", "old fashioned oats"],
                        "per_100g": {"calories": 379.0, "protein_g": 13.2, "fat_g": 6.5, "carbs_g": 67.7},
                    },
                    {
                        "name": "banana",
                        "per_100g": {"calories": 89.0, "protein_g": 1.1, "fat_g": 0.3, "carbs_g": 22.8},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return str(path)


def test_loads_all_ingredients(db_path):
    db = IngredientDB(db_path)
    names = [i["name"] for i in db.get_all_ingredients()]
    assert names == ["Oats", "banana"]


def test_get_all_returns_a_copy_not_internal_state(db_path):
    db = IngredientDB(db_path)
    listing = db.get_all_ingredients()
    listing.clear()
    assert len(db.get_all_ingredients()) == 2


def test_lookup_by_name_is_case_insensitive(db_path):
    db = IngredientDB(db_path)
    assert db.get_ingredient_by_name("OATS")["name"] == "Oats"
    assert db.get_ingredient_by_name("Banana")["name"] == "banana"


def test_lookup_matches_aliases_case_insensitively(db_path):
    db = IngredientDB(db_path)
    assert db.get_ingredient_by_name("Rolled Oats")["name"] == "Oats"


def test_unknown_ingredient_returns_none(db_path):
    db = IngredientDB(db_path)
    assert db.get_ingredient_by_name("dragonfruit") is None


def test_empty_ingredients_key_yields_empty_db(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({}), encoding="utf-8")
    db = IngredientDB(str(path))
    assert db.get_all_ingredients() == []
