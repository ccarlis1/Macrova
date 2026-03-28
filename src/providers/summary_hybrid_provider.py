"""Ingredient provider for draft nutrition summary: local hub JSON, then USDA cache/API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.data_layer.nutrition_db import NutritionDB
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.providers.api_provider import APIIngredientProvider
from src.providers.ingredient_provider import IngredientDataProvider
from src.providers.local_provider import LocalIngredientProvider


class SummaryHybridIngredientProvider(IngredientDataProvider):
    """Try [custom_ingredients.json] first; on miss, resolve via [CachedIngredientLookup].

    Used by ``POST /api/v1/nutrition/summary`` so free-text recipe lines are not silently
    dropped when absent from the local hub (see ``NutritionCalculator.calculate_recipe_nutrition``).
    """

    def __init__(
        self,
        nutrition_db: NutritionDB,
        cached_lookup: CachedIngredientLookup,
    ) -> None:
        self._local = LocalIngredientProvider(nutrition_db)
        self._lookup = cached_lookup
        self._usda_hits: Dict[str, Dict[str, Any]] = {}

    def resolve_all(self, ingredient_names: List[str]) -> None:
        return

    def get_ingredient_info(self, name: str) -> Optional[Dict[str, Any]]:
        raw = (name or "").strip()
        if not raw:
            return None

        loc = self._local.get_ingredient_info(raw)
        if loc is not None:
            return loc

        key = raw.lower()
        if key in self._usda_hits:
            return self._usda_hits[key]

        entry = self._lookup.lookup(key)
        if entry is None:
            return None

        payload = APIIngredientProvider._entry_to_dict(raw, entry)
        self._usda_hits[key] = payload
        return payload
