"""Tests for src/providers/local_provider.py — JSON-backed IngredientDataProvider."""

import json

import pytest

from src.data_layer.nutrition_db import NutritionDB
from src.providers.ingredient_provider import IngredientDataProvider
from src.providers.local_provider import LocalIngredientProvider

PER_100G = {"calories": 89.0, "protein_g": 1.1, "fat_g": 0.3, "carbs_g": 22.8}


@pytest.fixture
def provider(tmp_path):
    path = tmp_path / "ingredients.json"
    path.write_text(
        json.dumps({"ingredients": [{"name": "banana", "per_100g": PER_100G}]}),
        encoding="utf-8",
    )
    return LocalIngredientProvider(NutritionDB(str(path)))


def test_implements_provider_interface(provider):
    assert isinstance(provider, IngredientDataProvider)


def test_get_ingredient_info_delegates_to_nutrition_db(provider):
    info = provider.get_ingredient_info("Banana")
    assert info["name"] == "banana"
    assert info["per_100g"] == PER_100G


def test_unknown_ingredient_returns_none(provider):
    assert provider.get_ingredient_info("dragonfruit") is None


def test_resolve_all_is_a_noop_for_local_data(provider):
    # Must not raise and must not affect subsequent lookups.
    provider.resolve_all(["banana", "dragonfruit"])
    assert provider.get_ingredient_info("banana") is not None
