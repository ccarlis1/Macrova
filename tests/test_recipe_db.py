"""Tests for src/data_layer/recipe_db.py — JSON-backed recipe store parsing."""

import json

import pytest

from src.data_layer.recipe_db import RecipeDB


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "recipes.json"
    path.write_text(
        json.dumps(
            {
                "recipes": [
                    {
                        "id": "r1",
                        "name": "Oatmeal",
                        "cooking_time_minutes": 10,
                        "ingredients": [
                            {"name": "oats", "quantity": 80, "unit": "g"},
                            {"name": "salt", "quantity": 1, "unit": "to taste"},
                        ],
                        "instructions": ["boil water", "add oats"],
                    },
                    {
                        "id": "r2",
                        "name": "Banana",
                        "cooking_time_minutes": 0,
                        "ingredients": [{"name": "banana", "quantity": 118, "unit": "g"}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return RecipeDB(str(path))


def test_loads_all_recipes_in_file_order(db):
    assert [r.id for r in db.get_all_recipes()] == ["r1", "r2"]


def test_regular_ingredient_parsing(db):
    oats = db.get_recipe_by_id("r1").ingredients[0]
    assert oats.name == "oats"
    assert oats.quantity == 80.0
    assert oats.unit == "g"
    assert oats.is_to_taste is False


def test_to_taste_ingredient_zeroes_quantity_and_flags(db):
    salt = db.get_recipe_by_id("r1").ingredients[1]
    assert salt.is_to_taste is True
    assert salt.quantity == 0.0
    assert salt.unit == "to taste"


def test_missing_instructions_default_to_empty_list(db):
    assert db.get_recipe_by_id("r2").instructions == []


def test_get_recipe_by_id_unknown_returns_none(db):
    assert db.get_recipe_by_id("nope") is None


def test_get_all_returns_a_copy(db):
    listing = db.get_all_recipes()
    listing.clear()
    assert len(db.get_all_recipes()) == 2
