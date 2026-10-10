"""Tests for src/providers/summary_hybrid_provider.py — local-first, USDA-fallback lookups."""

import json

import pytest

from src.data_layer.models import MicronutrientProfile
from src.data_layer.nutrition_db import NutritionDB
from src.ingestion.ingredient_cache import CacheEntry
from src.ingestion.nutrient_mapper import MappedNutrition
from src.providers.summary_hybrid_provider import SummaryHybridIngredientProvider

LOCAL_PER_100G = {"calories": 379.0, "protein_g": 13.2, "fat_g": 6.5, "carbs_g": 67.7}


def _entry(name):
    return CacheEntry(
        canonical_name=name,
        fdc_id=999,
        description=f"{name}, raw",
        data_type="SR Legacy",
        nutrition=MappedNutrition(
            calories=52.0,
            protein_g=0.3,
            fat_g=0.2,
            carbs_g=14.0,
            micronutrients=MicronutrientProfile(),
        ),
    )


class FakeLookup:
    def __init__(self, entries=None):
        self.entries = entries or {}
        self.calls = []

    def lookup(self, name):
        self.calls.append(name)
        return self.entries.get(name)


@pytest.fixture
def nutrition_db(tmp_path):
    path = tmp_path / "ingredients.json"
    path.write_text(
        json.dumps({"ingredients": [{"name": "oats", "per_100g": LOCAL_PER_100G}]}),
        encoding="utf-8",
    )
    return NutritionDB(str(path))


def test_local_hub_hit_wins_without_touching_usda(nutrition_db):
    lookup = FakeLookup({"oats": _entry("oats")})
    provider = SummaryHybridIngredientProvider(nutrition_db, lookup)

    info = provider.get_ingredient_info("oats")

    assert info["per_100g"] == LOCAL_PER_100G
    assert lookup.calls == []


def test_local_miss_falls_back_to_usda_lookup(nutrition_db):
    lookup = FakeLookup({"apple": _entry("apple")})
    provider = SummaryHybridIngredientProvider(nutrition_db, lookup)

    info = provider.get_ingredient_info("Apple")

    assert info["name"] == "Apple"
    assert info["per_100g"]["calories"] == 52.0
    assert lookup.calls == ["apple"]


def test_usda_hits_are_memoized_per_provider_instance(nutrition_db):
    lookup = FakeLookup({"apple": _entry("apple")})
    provider = SummaryHybridIngredientProvider(nutrition_db, lookup)

    first = provider.get_ingredient_info("apple")
    second = provider.get_ingredient_info("APPLE")

    assert lookup.calls == ["apple"]
    assert second is first


def test_unresolvable_ingredient_returns_none(nutrition_db):
    provider = SummaryHybridIngredientProvider(nutrition_db, FakeLookup())
    assert provider.get_ingredient_info("dragonfruit") is None


def test_blank_names_return_none_without_lookup(nutrition_db):
    lookup = FakeLookup()
    provider = SummaryHybridIngredientProvider(nutrition_db, lookup)

    assert provider.get_ingredient_info("") is None
    assert provider.get_ingredient_info("   ") is None
    assert lookup.calls == []


def test_resolve_all_is_a_noop(nutrition_db):
    provider = SummaryHybridIngredientProvider(nutrition_db, FakeLookup())
    assert provider.resolve_all(["anything"]) is None
