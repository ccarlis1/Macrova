"""Recipe database for loading recipes from JSON."""
import json
from pathlib import Path
from typing import List, Optional

from src.data_layer.models import Recipe, Ingredient


class RecipeDB:
    """Database for managing recipes loaded from JSON."""

    def __init__(self, json_path: str):
        """Initialize recipe database from JSON file.

        Args:
            json_path: Path to JSON file containing recipes
        """
        self.json_path = Path(json_path)
        self._recipes: List[Recipe] = []
        self._load_recipes()

    def _load_recipes(self):
        """Load recipes from JSON file."""
        with open(self.json_path, "r") as f:
            data = json.load(f)

        recipes_data = data.get("recipes", [])
        for recipe_data in recipes_data:
            recipe = self._parse_recipe(recipe_data)
            self._recipes.append(recipe)

    def _parse_recipe(self, recipe_data: dict) -> Recipe:
        """Parse a single recipe from dictionary data.

        Args:
            recipe_data: Dictionary containing recipe data

        Returns:
            Recipe object
        """
        ingredients = []
        for ing_data in recipe_data.get("ingredients", []):
            ingredient = self._parse_ingredient(ing_data)
            ingredients.append(ingredient)

        return Recipe(
            id=recipe_data["id"],
            name=recipe_data["name"],
            ingredients=ingredients,
            cooking_time_minutes=recipe_data["cooking_time_minutes"],
            instructions=recipe_data.get("instructions", []),
        )

    def _parse_ingredient(self, ing_data: dict) -> Ingredient:
        """Parse a single ingredient from dictionary data.

        Args:
            ing_data: Dictionary containing ingredient data

        Returns:
            Ingredient object
        """
        unit = ing_data.get("unit", "")
        is_to_taste = unit == "to taste" or "to taste" in unit.lower()

        # For "to taste" ingredients, set quantity to 0
        quantity = 0.0 if is_to_taste else float(ing_data.get("quantity", 0.0))

        return Ingredient(
            name=ing_data["name"],
            quantity=quantity,
            unit=unit,
            is_to_taste=is_to_taste,
            normalized_unit=unit,  # Will be normalized later by unit converter
            normalized_quantity=quantity,  # Will be normalized later by unit converter
        )

    def get_all_recipes(self) -> List[Recipe]:
        """Get all recipes in the database.

        Returns:
            List of all Recipe objects
        """
        return self._recipes.copy()

    def get_recipe_by_id(self, recipe_id: str) -> Optional[Recipe]:
        """Get a recipe by its ID.

        Args:
            recipe_id: Unique recipe identifier

        Returns:
            Recipe object if found, None otherwise
        """
        for recipe in self._recipes:
            if recipe.id == recipe_id:
                return recipe
        return None

