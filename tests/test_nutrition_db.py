"""Tests for src/data_layer/nutrition_db.py — nutrition lookups over IngredientDB."""

import json

import pytest

from src.data_layer.nutrition_db import NutritionDB

PER_100G = {"calories": 379.0, "protein_g": 13.2, "fat_g": 6.5, "carbs_g": 67.7}
PER_SCOOP = {"calories": 120.0, "protein_g": 24.0, "fat_g": 1.5, "carbs_g": 3.0}


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "ingredients.json"
    path.write_text(
        json.dumps(
            {
                "ingredients": [
                    {
                        "name": "whey protein",
                        "aliases": ["protein powder"],
                        "per_100g": PER_100G,
                        "per_scoop": PER_SCOOP,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return NutritionDB(str(path))


def test_default_unit_key_is_per_100g(db):
    assert db.get_nutrition("whey protein") == PER_100G


def test_alternate_unit_key(db):
    assert db.get_nutrition("whey protein", unit_key="per_scoop") == PER_SCOOP


def test_lookup_works_via_alias(db):
    assert db.get_nutrition("protein powder") == PER_100G


def test_returned_dict_is_a_copy(db):
    first = db.get_nutrition("whey protein")
    first["calories"] = -1.0
    assert db.get_nutrition("whey protein")["calories"] == PER_100G["calories"]


def test_unknown_ingredient_returns_none(db):
    assert db.get_nutrition("dragonfruit") is None


def test_missing_unit_key_returns_none(db):
    assert db.get_nutrition("whey protein", unit_key="per_large") is None


def test_get_ingredient_info_returns_full_record(db):
    info = db.get_ingredient_info("whey protein")
    assert info["name"] == "whey protein"
    assert info["per_100g"] == PER_100G
    assert info["per_scoop"] == PER_SCOOP
    assert db.get_ingredient_info("dragonfruit") is None
