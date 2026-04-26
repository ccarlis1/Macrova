"""Recipe database for loading recipes from JSON."""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.data_layer.models import Recipe, Ingredient
from src.llm import tag_repository
from src.llm.schemas import RecipeTagsJson


logger = logging.getLogger(__name__)


class RecipeDB:
    """Database for managing recipes loaded from JSON."""

    def __init__(self, json_path: str, tag_repo_path: Optional[str] = None):
        """Initialize recipe database from JSON file.

        Args:
            json_path: Path to JSON file containing recipes
            tag_repo_path: Path to canonical tag repository payload used by
                tag_repository.resolve(). Defaults to data/recipes/recipe_tags.json.
        """
        self.json_path = Path(json_path)
        if tag_repo_path is None:
            self.tag_repo_path = Path("data/recipes/recipe_tags.json")
        else:
            self.tag_repo_path = Path(tag_repo_path)
        self._recipes: List[Recipe] = []
        self._canonical_tags_by_id: Dict[str, RecipeTagsJson] = {}
        self._load_recipes()

    def _load_recipes(self):
        """Load recipes from JSON file."""
        with open(self.json_path, "r") as f:
            data = json.load(f)

        self._canonical_tags_by_id = tag_repository.load_recipe_tags(
            str(self.tag_repo_path)
        )
        self._recipes = []
        recipes_data = data.get("recipes", [])
        for recipe_data in recipes_data:
            recipe = self._parse_recipe(recipe_data)
            self._recipes.append(recipe)

    def _derive_tags_from_canonical(self, recipe_id: str) -> List[Dict[str, str]]:
        """Derive lightweight compatibility tags from canonical tags_by_id only."""
        recipe_tags = self._canonical_tags_by_id.get(recipe_id)
        if recipe_tags is None:
            return []

        slugs_by_type = recipe_tags.tag_slugs_by_type or {}
        parsed: List[Dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for tag_type in sorted(slugs_by_type.keys()):
            raw_slugs = slugs_by_type.get(tag_type) or []
            normalized_slugs = sorted({str(s).strip() for s in raw_slugs if str(s).strip()})
            for slug in normalized_slugs:
                try:
                    resolved = tag_repository.resolve(slug, str(self.tag_repo_path))
                except ValueError:
                    logger.warning(
                        "Dropping unknown canonical tag slug '%s' for recipe '%s'.",
                        slug,
                        recipe_id,
                    )
                    continue
                if resolved.tag_type != tag_type:
                    logger.warning(
                        "Dropping canonical tag '%s' with mismatched type '%s' for recipe '%s'.",
                        resolved.slug,
                        tag_type,
                        recipe_id,
                    )
                    continue
                key = (resolved.slug, resolved.tag_type)
                if key in seen:
                    continue
                seen.add(key)
                parsed.append({"slug": resolved.slug, "type": resolved.tag_type})
        return parsed

    def _parse_recipe(self, recipe_data: dict) -> Recipe:
        """Parse a single recipe from dictionary data.

        Args:
            recipe_data: Dictionary containing recipe data

        Returns:
            Recipe object
        """
        recipe_id = str(recipe_data["id"])
        ingredients = []
        for ing_data in recipe_data.get("ingredients", []):
            ingredient = self._parse_ingredient(ing_data)
            ingredients.append(ingredient)

        return Recipe(
            id=recipe_id,
            name=recipe_data["name"],
            ingredients=ingredients,
            cooking_time_minutes=recipe_data["cooking_time_minutes"],
            instructions=recipe_data.get("instructions", []),
            default_servings=int(recipe_data.get("default_servings", 1)),
            tags=self._derive_tags_from_canonical(recipe_id),
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

    def save(self) -> None:
        """Persist recipes to JSON file.

        Note: ``Recipe.tags`` is a derived compatibility projection from
        canonical ``recipe_tags.json`` and is never persisted here.
        """
        recipes_payload = []
        for recipe in self._recipes:
            recipes_payload.append(
                {
                    "id": recipe.id,
                    "name": recipe.name,
                    "ingredients": [
                        {
                            "name": ing.name,
                            "quantity": ing.quantity,
                            "unit": ing.unit,
                        }
                        for ing in recipe.ingredients
                    ],
                    "cooking_time_minutes": recipe.cooking_time_minutes,
                    "instructions": list(recipe.instructions),
                    "default_servings": int(recipe.default_servings),
                }
            )

        payload = {"recipes": recipes_payload}
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

