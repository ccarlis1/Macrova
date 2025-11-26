"""Recipe retriever for searching and filtering recipes."""
from typing import List, Optional

from src.data_layer.models import Recipe
from src.data_layer.recipe_db import RecipeDB


class RecipeRetriever:
    """Retriever for searching and filtering recipes."""

    def __init__(self, recipe_db: RecipeDB):
        """Initialize retriever with recipe database.
        
        Args:
            recipe_db: RecipeDB instance for recipe access
        """
        self.recipe_db = recipe_db

    def search_by_keywords(
        self, keywords: List[str], limit: int = 10
    ) -> List[Recipe]:
        """Search recipes by keywords in name and ingredients.
        
        Args:
            keywords: List of search terms (empty list returns empty list)
            limit: Maximum number of results
        
        Returns:
            List of Recipe objects, sorted by relevance (empty if no keywords)
        """
        if not keywords:
            return []

        all_recipes = self.recipe_db.get_all_recipes()
        scored_recipes = []

        for recipe in all_recipes:
            score = self._score_recipe_relevance(recipe, keywords)
            if score > 0:
                scored_recipes.append((score, recipe))

        # Sort by score (descending) and limit results
        scored_recipes.sort(key=lambda x: x[0], reverse=True)
        return [recipe for _, recipe in scored_recipes[:limit]]

    def filter_by_cooking_time(
        self, recipes: List[Recipe], max_time_minutes: int
    ) -> List[Recipe]:
        """Filter recipes by maximum cooking time.
        
        Args:
            recipes: List of Recipe objects
            max_time_minutes: Maximum allowed cooking time
        
        Returns:
            Filtered list of recipes
        """
        return [
            recipe
            for recipe in recipes
            if recipe.cooking_time_minutes <= max_time_minutes
        ]

    def filter_by_allergies(
        self, recipes: List[Recipe], allergies: List[str]
    ) -> List[Recipe]:
        """Filter out recipes containing allergenic ingredients.
        
        Args:
            recipes: List of Recipe objects
            allergies: List of allergen names (case-insensitive)
        
        Returns:
            Filtered list (recipes with allergens removed)
        """
        if not allergies:
            return recipes

        allergies_lower = [a.lower() for a in allergies]
        filtered = []

        for recipe in recipes:
            has_allergen = False
            for ingredient in recipe.ingredients:
                ingredient_name_lower = ingredient.name.lower()
                # Check if ingredient name contains any allergen
                if any(allergen in ingredient_name_lower for allergen in allergies_lower):
                    has_allergen = True
                    break
            if not has_allergen:
                filtered.append(recipe)

        return filtered

    def filter_by_dislikes(
        self, recipes: List[Recipe], disliked_foods: List[str]
    ) -> List[Recipe]:
        """Filter out recipes containing disliked ingredients.
        
        Args:
            recipes: List of Recipe objects
            disliked_foods: List of disliked food names (case-insensitive)
        
        Returns:
            Filtered list (recipes with dislikes removed)
        """
        if not disliked_foods:
            return recipes

        dislikes_lower = [d.lower() for d in disliked_foods]
        filtered = []

        for recipe in recipes:
            has_dislike = False
            for ingredient in recipe.ingredients:
                ingredient_name_lower = ingredient.name.lower()
                # Check if ingredient name contains any disliked food
                if any(dislike in ingredient_name_lower for dislike in dislikes_lower):
                    has_dislike = True
                    break
            if not has_dislike:
                filtered.append(recipe)

        return filtered

    def search(
        self,
        keywords: Optional[List[str]] = None,
        max_cooking_time: Optional[int] = None,
        allergies: Optional[List[str]] = None,
        disliked_foods: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Recipe]:
        """Comprehensive search with all filters.
        
        Args:
            keywords: Optional search terms (empty list returns empty list)
            max_cooking_time: Optional maximum cooking time
            allergies: Optional list of allergens to exclude
            disliked_foods: Optional list of foods to exclude
            limit: Maximum results
        
        Returns:
            Filtered and sorted list of recipes
        """
        # Start with all recipes or keyword search
        if keywords is not None:
            # Empty list should return empty list
            if len(keywords) == 0:
                return []
            recipes = self.search_by_keywords(keywords, limit=limit * 2)  # Get more for filtering
        else:
            recipes = self.recipe_db.get_all_recipes()

        # Apply filters
        if max_cooking_time is not None:
            recipes = self.filter_by_cooking_time(recipes, max_cooking_time)

        if allergies:
            recipes = self.filter_by_allergies(recipes, allergies)

        if disliked_foods:
            recipes = self.filter_by_dislikes(recipes, disliked_foods)

        # Limit final results
        return recipes[:limit]

    def _score_recipe_relevance(
        self, recipe: Recipe, keywords: List[str]
    ) -> float:
        """Score recipe relevance based on keyword matches.
        
        Args:
            recipe: Recipe object
            keywords: List of search terms
        
        Returns:
            Relevance score (higher = more relevant)
        """
        score = 0.0
        recipe_text_lower = recipe.name.lower()

        # Check name matches (weighted higher)
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in recipe_text_lower:
                score += 2.0  # Name matches worth more

        # Check ingredient matches
        for ingredient in recipe.ingredients:
            ingredient_name_lower = ingredient.name.lower()
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in ingredient_name_lower:
                    score += 1.0  # Ingredient matches worth less

        return score

