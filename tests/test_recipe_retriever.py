"""Tests for recipe retriever."""
import pytest
from tempfile import NamedTemporaryFile
import json

from src.ingestion.recipe_retriever import RecipeRetriever
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.models import Recipe, Ingredient


class TestRecipeRetriever:
    """Tests for RecipeRetriever."""

    @pytest.fixture
    def recipe_db(self):
        """Create a test recipe database."""
        recipe_data = {
            "recipes": [
                {
                    "id": "recipe_001",
                    "name": "Preworkout Meal",
                    "ingredients": [
                        {"quantity": 200, "unit": "g", "name": "cream of rice"},
                        {"quantity": 1, "unit": "scoop", "name": "whey protein powder"},
                    ],
                    "cooking_time_minutes": 5,
                    "instructions": ["Cook rice", "Add protein"],
                },
                {
                    "id": "recipe_002",
                    "name": "Breakfast Scramble",
                    "ingredients": [
                        {"quantity": 5, "unit": "large", "name": "eggs"},
                        {"quantity": 1, "unit": "oz", "name": "cheese"},
                    ],
                    "cooking_time_minutes": 15,
                    "instructions": ["Scramble eggs"],
                },
                {
                    "id": "recipe_003",
                    "name": "Salmon Dinner",
                    "ingredients": [
                        {"quantity": 4, "unit": "oz", "name": "salmon"},
                        {"quantity": 1, "unit": "cup", "name": "rice"},
                        {"quantity": 1, "unit": "to taste", "name": "shellfish"},
                    ],
                    "cooking_time_minutes": 30,
                    "instructions": ["Cook salmon"],
                },
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(recipe_data, f)
            temp_path = f.name

        db = RecipeDB(temp_path)
        yield db
        import os
        os.unlink(temp_path)

    @pytest.fixture
    def retriever(self, recipe_db):
        """Create a RecipeRetriever instance."""
        return RecipeRetriever(recipe_db)

    def test_search_by_keywords_single(self, retriever):
        """Test keyword search with single keyword."""
        results = retriever.search_by_keywords(["breakfast"])
        assert len(results) > 0
        assert any("breakfast" in r.name.lower() for r in results)

    def test_search_by_keywords_multiple(self, retriever):
        """Test keyword search with multiple keywords."""
        results = retriever.search_by_keywords(["preworkout", "protein"])
        assert len(results) > 0
        # Should find recipes with both keywords
        assert any("preworkout" in r.name.lower() for r in results)

    def test_search_by_keywords_empty(self, retriever):
        """Test empty keyword search returns empty list."""
        results = retriever.search_by_keywords([])
        assert results == []

    def test_search_by_keywords_no_match(self, retriever):
        """Test keyword search with no matches."""
        results = retriever.search_by_keywords(["nonexistent"])
        assert results == []

    def test_filter_by_cooking_time(self, retriever):
        """Test filtering by cooking time."""
        all_recipes = retriever.recipe_db.get_all_recipes()
        filtered = retriever.filter_by_cooking_time(all_recipes, 15)
        assert all(r.cooking_time_minutes <= 15 for r in filtered)
        assert len(filtered) < len(all_recipes)

    def test_filter_by_allergies(self, retriever):
        """Test filtering by allergies."""
        all_recipes = retriever.recipe_db.get_all_recipes()
        filtered = retriever.filter_by_allergies(all_recipes, ["shellfish"])
        # Should remove recipe with shellfish ingredient
        assert all(
            "shellfish" not in ing.name.lower()
            for r in filtered
            for ing in r.ingredients
        )

    def test_filter_by_allergies_empty(self, retriever):
        """Test filtering with empty allergies list."""
        all_recipes = retriever.recipe_db.get_all_recipes()
        filtered = retriever.filter_by_allergies(all_recipes, [])
        assert len(filtered) == len(all_recipes)

    def test_filter_by_allergies_case_insensitive(self, retriever):
        """Test allergy filtering is case-insensitive."""
        all_recipes = retriever.recipe_db.get_all_recipes()
        filtered = retriever.filter_by_allergies(all_recipes, ["SHELLFISH"])
        assert all(
            "shellfish" not in ing.name.lower()
            for r in filtered
            for ing in r.ingredients
        )

    def test_filter_by_dislikes(self, retriever):
        """Test filtering by disliked foods."""
        all_recipes = retriever.recipe_db.get_all_recipes()
        filtered = retriever.filter_by_dislikes(all_recipes, ["cheese"])
        # Should remove recipes with cheese
        assert all(
            "cheese" not in ing.name.lower()
            for r in filtered
            for ing in r.ingredients
        )

    def test_filter_by_dislikes_empty(self, retriever):
        """Test filtering with empty dislikes list."""
        all_recipes = retriever.recipe_db.get_all_recipes()
        filtered = retriever.filter_by_dislikes(all_recipes, [])
        assert len(filtered) == len(all_recipes)

    def test_search_combined_filters(self, retriever):
        """Test comprehensive search with all filters."""
        results = retriever.search(
            keywords=["breakfast"],
            max_cooking_time=20,
            allergies=["shellfish"],
            disliked_foods=["cheese"],
            limit=10,
        )
        # Should apply all filters
        assert all(r.cooking_time_minutes <= 20 for r in results)
        assert all(
            "shellfish" not in ing.name.lower()
            for r in results
            for ing in r.ingredients
        )
        assert all(
            "cheese" not in ing.name.lower()
            for r in results
            for ing in r.ingredients
        )

    def test_search_no_keywords(self, retriever):
        """Test search without keywords returns all recipes (after filtering)."""
        results = retriever.search(max_cooking_time=30)
        assert len(results) > 0

    def test_search_limit(self, retriever):
        """Test search respects limit parameter."""
        results = retriever.search_by_keywords(["breakfast"], limit=1)
        assert len(results) <= 1

    def test_score_recipe_relevance(self, retriever):
        """Test recipe relevance scoring."""
        recipe = Recipe(
            id="test",
            name="Breakfast Protein Meal",
            ingredients=[
                Ingredient(name="eggs", quantity=2.0, unit="large", is_to_taste=False),
                Ingredient(name="protein", quantity=1.0, unit="scoop", is_to_taste=False),
            ],
            cooking_time_minutes=10,
            instructions=[],
        )

        score = retriever._score_recipe_relevance(recipe, ["breakfast", "protein"])
        assert score > 0
        # Name matches should be worth more
        assert score >= 2.0  # At least 2 for name match

    def test_search_empty_keywords_returns_empty(self, retriever):
        """Test that empty keyword list in search() returns empty list."""
        results = retriever.search(keywords=[])
        assert results == []

