"""Provider abstraction layer for ingredient data lookup.

This package decouples the NutritionCalculator and planner from
concrete data sources (local JSON vs. external API).
"""

from src.providers.ingredient_provider import IngredientDataProvider
from src.providers.local_provider import LocalIngredientProvider
from src.providers.api_provider import APIIngredientProvider

__all__ = [
    "IngredientDataProvider",
    "LocalIngredientProvider",
    "APIIngredientProvider",
]
