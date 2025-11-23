"""Ingredient database for loading ingredient metadata from JSON."""
import json
from pathlib import Path
from typing import List, Dict, Any


class IngredientDB:
    """Database for managing ingredient metadata loaded from JSON."""

    def __init__(self, json_path: str):
        """Initialize ingredient database from JSON file.

        Args:
            json_path: Path to JSON file containing ingredient data
        """
        self.json_path = Path(json_path)
        self._ingredients: List[Dict[str, Any]] = []
        self._load_ingredients()

    def _load_ingredients(self):
        """Load ingredients from JSON file."""
        with open(self.json_path, "r") as f:
            data = json.load(f)

        self._ingredients = data.get("ingredients", [])

    def get_all_ingredients(self) -> List[Dict[str, Any]]:
        """Get all ingredients in the database.

        Returns:
            List of all ingredient dictionaries
        """
        return self._ingredients.copy()

    def get_ingredient_by_name(self, name: str) -> Dict[str, Any]:
        """Get an ingredient by its name (case-insensitive).

        Args:
            name: Ingredient name to search for

        Returns:
            Ingredient dictionary if found, None otherwise
        """
        name_lower = name.lower()
        for ingredient in self._ingredients:
            if ingredient["name"].lower() == name_lower:
                return ingredient
            # Check aliases
            aliases = ingredient.get("aliases", [])
            if any(alias.lower() == name_lower for alias in aliases):
                return ingredient
        return None

