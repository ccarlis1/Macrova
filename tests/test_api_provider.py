"""Tests for src/providers/api_provider.py — USDA-backed provider with eager resolution."""

import pytest

from src.data_layer.models import MicronutrientProfile
from src.ingestion.ingredient_cache import CacheEntry
from src.ingestion.nutrient_mapper import MappedNutrition
from src.providers.api_provider import APIIngredientProvider, IngredientResolutionError


def _entry(name, calories=100.0):
    return CacheEntry(
        canonical_name=name,
        fdc_id=12345,
        description=f"{name}, raw",
        data_type="SR Legacy",
        nutrition=MappedNutrition(
            calories=calories,
            protein_g=10.0,
            fat_g=5.0,
            carbs_g=20.0,
            micronutrients=MicronutrientProfile(),
        ),
    )


class FakeLookup:
    """CachedIngredientLookup stand-in that records lookup order."""

    def __init__(self, entries=None, error_on=None):
        self.entries = entries or {}
        self.error_on = error_on
        self.calls = []

    def lookup(self, name):
        self.calls.append(name)
        if self.error_on is not None and name == self.error_on:
            raise RuntimeError("simulated USDA failure")
        return self.entries.get(name)


def test_resolve_all_processes_names_in_sorted_order():
    lookup = FakeLookup({n: _entry(n) for n in ["rice", "banana", "oats"]})
    provider = APIIngredientProvider(lookup)

    provider.resolve_all(["rice", "banana", "oats"])

    assert lookup.calls == ["banana", "oats", "rice"]


def test_get_ingredient_info_shape_matches_calculator_contract():
    lookup = FakeLookup({"banana": _entry("banana", calories=89.0)})
    provider = APIIngredientProvider(lookup)
    provider.resolve_all(["banana"])

    info = provider.get_ingredient_info("Banana")

    assert info["name"] == "banana"
    per_100g = info["per_100g"]
    assert per_100g["calories"] == 89.0
    assert per_100g["protein_g"] == 10.0
    # Micronutrient fields are flattened into per_100g.
    assert "iron_mg" in per_100g


def test_get_before_resolve_raises_runtime_error():
    provider = APIIngredientProvider(FakeLookup())

    with pytest.raises(RuntimeError, match="not resolved before planning"):
        provider.get_ingredient_info("banana")


def test_already_resolved_names_are_not_looked_up_again():
    lookup = FakeLookup({"banana": _entry("banana")})
    provider = APIIngredientProvider(lookup)

    provider.resolve_all(["banana"])
    provider.resolve_all(["banana"])

    assert lookup.calls == ["banana"]


def test_missing_ingredient_fails_fast_with_resolution_error():
    provider = APIIngredientProvider(FakeLookup({}))

    with pytest.raises(IngredientResolutionError, match="no result from API"):
        provider.resolve_all(["dragonfruit"])


def test_lookup_exception_is_wrapped_in_resolution_error():
    lookup = FakeLookup({"banana": _entry("banana")}, error_on="banana")
    provider = APIIngredientProvider(lookup)

    with pytest.raises(IngredientResolutionError, match="banana"):
        provider.resolve_all(["banana"])
