"""Nutrition database for loading nutrition data from JSON."""
import json
from pathlib import Path
from typing import Optional, Dict, Any

from src.data_layer.ingredient_db import IngredientDB


class NutritionDB:
    """Database for managing nutrition data loaded from JSON."""

    def __init__(self, json_path: str):
        """Initialize nutrition database from JSON file.

        Args:
            json_path: Path to JSON file containing nutrition data
        """
        self.json_path = Path(json_path)
        self.ingredient_db = IngredientDB(json_path)

    def get_nutrition(
        self, ingredient_name: str, unit_key: str = "per_100g"
    ) -> Optional[Dict[str, float]]:
        """Get nutrition data for an ingredient.

        Args:
            ingredient_name: Name of the ingredient (can be alias)
            unit_key: Key for nutrition data (e.g., "per_100g", "per_scoop", "per_large")

        Returns:
            Dictionary with nutrition values (calories, protein_g, fat_g, carbs_g)
            or None if ingredient not found
        """
        ingredient = self.ingredient_db.get_ingredient_by_name(ingredient_name)
        if ingredient is None:
            return None

        # Get nutrition data for the specified unit
        nutrition_data = ingredient.get(unit_key)
        if nutrition_data is None:
            return None

        return nutrition_data.copy()

    def get_ingredient_info(self, ingredient_name: str) -> Optional[Dict[str, Any]]:
        """Get full ingredient information including aliases and unit sizes.

        Args:
            ingredient_name: Name of the ingredient (can be alias)

        Returns:
            Full ingredient dictionary or None if not found
        """
        return self.ingredient_db.get_ingredient_by_name(ingredient_name)

