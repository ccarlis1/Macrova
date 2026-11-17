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

    def get_ingredient_info(self, ingredient_name: str) -> Optional[Dict[str, Any]]:
        """Get full ingredient information including aliases and unit sizes.

        Args:
            ingredient_name: Name of the ingredient (can be alias)

        Returns:
            Full ingredient dictionary or None if not found
        """
        return self.ingredient_db.get_ingredient_by_name(ingredient_name)

