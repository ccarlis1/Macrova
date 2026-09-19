"""Stage 2: provenance travels from the USDA cache through the provider boundary."""
from __future__ import annotations

import json

from src.data_layer.models import MicronutrientProfile
from src.ingestion.ingredient_cache import CacheEntry, CachedIngredientLookup, IngredientCache
from src.ingestion.nutrient_mapper import MappedNutrition, MAPPER_VERSION
from src.ingestion.usda_client import FoodDetailsResult
from src.llm.ingredient_matcher import validate_matches
from src.llm.schemas import IngredientMatchResult
from src.providers.api_provider import APIIngredientProvider


def _nut():
    return MappedNutrition(calories=10.0, protein_g=1.0, fat_g=0.5, carbs_g=2.0, micronutrients=MicronutrientProfile())


def test_legacy_cache_entry_without_provenance_loads_and_is_labelled(tmp_path):
    cache = IngredientCache(cache_dir=str(tmp_path))
    legacy = CacheEntry(canonical_name="oats", fdc_id=173576, description="Oil, oat", data_type="SR Legacy", nutrition=_nut())
    cache.write(legacy)
    raw = json.load(open(tmp_path / "oats.json"))
    assert "provenance" not in raw
    loaded = cache.read("oats")
    assert loaded.provenance is None
    rec = loaded.provenance_record()
    assert rec["method"] == "legacy_cache" and rec["fdc_id"] == 173576 and rec["mapper_version"] is None


class _FakeUSDA:
    def search_candidates(self, q, *, page_size, include_branded, **kw):
        return [{"fdcId": 1, "description": "Oats", "dataType": "SR Legacy"}, {"fdcId": 2, "description": "Oil, oat", "dataType": "SR Legacy"}]

    def get_food_details(self, fdc_id):
        return FoodDetailsResult(success=True, fdc_id=fdc_id, raw_payload={"foodNutrients": [{"nutrient": {"id": 1008}, "amount": 389.0}]})


def test_new_cache_entries_record_provenance(tmp_path):
    lookup = CachedIngredientLookup(cache_dir=str(tmp_path), usda_client=_FakeUSDA())
    entry = lookup.lookup("oats")
    assert entry.provenance["method"] == "deterministic"
    assert entry.provenance["fdc_id"] == entry.fdc_id
    assert entry.provenance["mapper_version"] == MAPPER_VERSION
    assert entry.provenance["description"] == entry.description
    on_disk = json.load(open(tmp_path / "oats.json"))
    assert on_disk["provenance"]["query"] == "oats"
    # round-trip
    assert lookup.cache.read("oats").provenance == entry.provenance


def test_provider_dict_exposes_provenance_additively(tmp_path):
    lookup = CachedIngredientLookup(cache_dir=str(tmp_path), usda_client=_FakeUSDA())
    provider = APIIngredientProvider(lookup)
    provider.resolve_all(["oats"])
    info = provider.get_ingredient_info("oats")
    assert set(info.keys()) == {"name", "per_100g", "provenance"}
    assert info["per_100g"]["calories"] == 389.0
    assert info["provenance"]["fdc_id"] == 1


def test_matcher_canonical_name_is_the_resolved_description(tmp_path):
    lookup = CachedIngredientLookup(cache_dir=str(tmp_path), usda_client=_FakeUSDA())
    provider = APIIngredientProvider(lookup)
    accepted, rejected = validate_matches([IngredientMatchResult(query="rolled oats", normalized_name="oats", confidence=0.9)], provider)
    assert rejected == []
    assert accepted[0].canonical_name == "Oats"
