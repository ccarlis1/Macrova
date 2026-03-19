import pytest

from src.data_layer.models import MicronutrientProfile
from src.ingestion.ingredient_cache import CacheEntry, CachedIngredientLookup
from src.ingestion.nutrient_mapper import MappedNutrition
from src.providers.api_provider import APIIngredientProvider, IngredientResolutionError


def _make_cache_entry(name: str) -> CacheEntry:
    """Build a minimal CacheEntry with per-100g macros only."""
    nutrition = MappedNutrition(
        calories=100.0,
        protein_g=10.0,
        fat_g=5.0,
        carbs_g=10.0,
        micronutrients=MicronutrientProfile(),
    )
    return CacheEntry(
        canonical_name=name.lower(),
        fdc_id=0,
        description=name,
        data_type="SR Legacy",
        nutrition=nutrition,
    )


class TestAPIIngredientProviderBaselineContracts:
    def test_resolve_all_sorts_and_calls_lookup_in_order(self):
        # Using MagicMock via import to avoid pulling unittest in this file.
        from unittest.mock import MagicMock

        lookup = MagicMock(spec=CachedIngredientLookup)
        # Return a deterministic cache entry based on the passed name.
        lookup.lookup.side_effect = lambda name: _make_cache_entry(name)

        provider = APIIngredientProvider(lookup)
        provider.resolve_all(["b", "a", "c"])

        assert lookup.lookup.call_count == 3
        assert [c.args[0] for c in lookup.lookup.call_args_list] == ["a", "b", "c"]

    def test_resolve_all_deduplicates_case_insensitively(self):
        from unittest.mock import MagicMock

        lookup = MagicMock(spec=CachedIngredientLookup)
        lookup.lookup.side_effect = lambda name: _make_cache_entry(name)

        provider = APIIngredientProvider(lookup)
        provider.resolve_all(["Egg", "egg", "EGG"])

        assert lookup.lookup.call_count == 1
        # Python sorts case-sensitively, so "EGG" comes first and is used.
        assert [c.args[0] for c in lookup.lookup.call_args_list] == ["EGG"]

    def test_get_ingredient_info_is_case_insensitive_after_resolve(self):
        from unittest.mock import MagicMock

        lookup = MagicMock(spec=CachedIngredientLookup)
        lookup.lookup.side_effect = lambda name: _make_cache_entry(name)

        provider = APIIngredientProvider(lookup)
        provider.resolve_all(["Chicken Breast"])

        info = provider.get_ingredient_info("chicken breast")
        assert info["name"] == "Chicken Breast"
        assert info["per_100g"]["protein_g"] == 10.0

    def test_get_ingredient_info_raises_if_not_resolved(self):
        from unittest.mock import MagicMock

        lookup = MagicMock(spec=CachedIngredientLookup)
        provider = APIIngredientProvider(lookup)

        with pytest.raises(RuntimeError, match="was not resolved before planning began"):
            provider.get_ingredient_info("egg")

    def test_resolve_all_fails_fast_when_lookup_returns_none(self):
        from unittest.mock import MagicMock

        lookup = MagicMock(spec=CachedIngredientLookup)

        def side_effect(name: str):
            if name.lower() == "b":
                return None
            return _make_cache_entry(name)

        lookup.lookup.side_effect = side_effect
        provider = APIIngredientProvider(lookup)

        with pytest.raises(IngredientResolutionError, match="Failed to resolve ingredient"):
            provider.resolve_all(["a", "b", "c"])

