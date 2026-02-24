"""API-backed ingredient data provider.

Wraps :class:`CachedIngredientLookup` and converts its ``CacheEntry``
objects into the ``Dict[str, Any]`` format that :class:`NutritionCalculator`
expects, so the calculator (and everything downstream) is completely
unaware of the external API.

All network / disk-cache I/O happens inside :meth:`resolve_all`.
After that method returns, :meth:`get_ingredient_info` is a pure
in-memory lookup — no API calls, no disk reads.
"""

from dataclasses import fields as dataclass_fields
from typing import Dict, Any, List, Optional

from src.providers.ingredient_provider import IngredientDataProvider
from src.ingestion.ingredient_cache import CachedIngredientLookup, CacheEntry


class IngredientResolutionError(Exception):
    """Raised when eager ingredient resolution fails.

    Fail-fast: no partial planning. The CLI exits with code 3 when this
    is raised during resolve_all().
    """


class APIIngredientProvider(IngredientDataProvider):
    """Provider that fetches nutrition data from the USDA API (with caching).

    Usage::

        from src.ingestion.ingredient_cache import CachedIngredientLookup
        from src.ingestion.usda_client import USDAClient

        client = USDAClient.from_env()
        lookup = CachedIngredientLookup(usda_client=client)
        provider = APIIngredientProvider(lookup)

        provider.resolve_all(["chicken breast", "rice", "broccoli"])

        info = provider.get_ingredient_info("chicken breast")
        # info == {"name": "chicken breast", "per_100g": { ... }}
    """

    def __init__(self, cached_lookup: CachedIngredientLookup) -> None:
        self._lookup = cached_lookup
        self._resolved: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # IngredientDataProvider interface
    # ------------------------------------------------------------------

    def get_ingredient_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Return the pre-resolved ingredient dict.

        Must only be called *after* :meth:`resolve_all`.  Returns from
        the in-memory cache — never contacts the API.

        Raises:
            RuntimeError: If *name* was not resolved beforehand.
        """
        key = name.lower()
        if key not in self._resolved:
            raise RuntimeError(
                f"Ingredient '{name}' was not resolved before planning began. "
                f"Call resolve_all() with all required ingredient names first."
            )
        return self._resolved[key]

    def resolve_all(self, ingredient_names: List[str]) -> None:
        """Eagerly fetch and cache every ingredient in *ingredient_names*.

        Names are sorted before processing to guarantee deterministic
        ordering of API calls (and therefore deterministic cache behaviour).
        On first failure, raises immediately; does not partially populate cache.

        Raises:
            IngredientResolutionError: If any lookup fails (None or exception).
        """
        for name in sorted(ingredient_names):
            key = name.lower()
            if key in self._resolved:
                continue

            try:
                entry: Optional[CacheEntry] = self._lookup.lookup(name)
            except Exception as e:
                raise IngredientResolutionError(
                    f"Failed to resolve ingredient '{name}': {e}"
                ) from e

            if entry is None:
                raise IngredientResolutionError(
                    f"Failed to resolve ingredient '{name}': no result from API. "
                    "Check that the USDA API key is set and the ingredient name is valid."
                )

            self._resolved[key] = self._entry_to_dict(name, entry)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _entry_to_dict(name: str, entry: CacheEntry) -> Dict[str, Any]:
        """Convert a ``CacheEntry`` into the dict shape NutritionCalculator expects.

        The calculator accesses ``ingredient_info.get("per_100g")`` and then
        reads macro keys (``calories``, ``protein_g``, …) and micronutrient
        keys (``iron_mg``, ``vitamin_a_ug``, …) directly from that sub-dict.
        """
        nutrition = entry.nutrition
        per_100g: Dict[str, Any] = {
            "calories": nutrition.calories,
            "protein_g": nutrition.protein_g,
            "fat_g": nutrition.fat_g,
            "carbs_g": nutrition.carbs_g,
        }

        for field in dataclass_fields(nutrition.micronutrients):
            per_100g[field.name] = getattr(nutrition.micronutrients, field.name)

        return {
            "name": name,
            "per_100g": per_100g,
        }
