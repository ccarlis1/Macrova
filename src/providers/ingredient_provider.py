"""Abstract base class for ingredient data providers.

All consumers of ingredient data (NutritionCalculator, RecipeScorer, etc.)
must depend ONLY on this interface. Concrete implementations supply data
from local JSON files or external APIs without changing downstream logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class IngredientDataProvider(ABC):
    """Abstraction for ingredient nutrition data lookup.

    Implementations may fetch from local JSON or an external API,
    but must return the exact dict shape that NutritionCalculator expects::

        {
            "name": str,
            "per_100g": {
                "calories": float,
                "protein_g": float,
                "fat_g": float,
                "carbs_g": float,
                # optional micronutrient fields (e.g. "iron_mg", "vitamin_a_ug")
            },
            # may contain other keys ("per_scoop", "aliases", etc.)
        }
    """

    @abstractmethod
    def get_ingredient_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Return full ingredient dict for *name*.

        The returned dict must be compatible with the shape currently
        produced by ``NutritionDB.get_ingredient_info``.

        Args:
            name: Ingredient name (case-insensitive matching encouraged).

        Returns:
            Ingredient dictionary or ``None`` if not found.
        """
        ...

    @abstractmethod
    def resolve_all(self, ingredient_names: List[str]) -> None:
        """Eagerly resolve / prefetch all ingredients before planning begins.

        For local providers this is typically a no-op (data already loaded).
        For API-backed providers this issues all network calls upfront so
        that no I/O occurs during the planning search loop.

        Must raise on failure (fail-fast semantics).

        Args:
            ingredient_names: All ingredient names that will be needed.
        """
        ...
