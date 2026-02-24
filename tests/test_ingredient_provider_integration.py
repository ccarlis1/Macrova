"""Integration tests for the Ingredient Provider abstraction.

Ensures the planner works identically with LocalIngredientProvider and
APIIngredientProvider (mocked), fail-fast behaviour, and no API calls
during planning.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.data_layer.models import (
    Recipe,
    Ingredient,
    UserProfile,
    NutritionProfile,
    MicronutrientProfile,
)
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.recipe_db import RecipeDB
from src.ingestion.ingredient_cache import CachedIngredientLookup, CacheEntry
from src.ingestion.nutrient_mapper import MappedNutrition
from src.nutrition.calculator import NutritionCalculator
from src.nutrition.aggregator import NutritionAggregator
from src.scoring.recipe_scorer import RecipeScorer
from src.ingestion.recipe_retriever import RecipeRetriever
from src.planning.meal_planner import MealPlanner, DailySchedule, PlanningResult
from src.providers.local_provider import LocalIngredientProvider
from src.providers.api_provider import APIIngredientProvider, IngredientResolutionError
from src.cli import extract_ingredient_names


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = "tests/fixtures"


def _user_profile() -> UserProfile:
    return UserProfile(
        daily_calories=2400,
        daily_protein_g=150.0,
        daily_fat_g=(50.0, 100.0),
        daily_carbs_g=300.0,
        schedule={"07:00": 2, "12:00": 3, "18:00": 3},
        liked_foods=["egg", "salmon"],
        disliked_foods=["mushroom"],
        allergies=["peanut"],
    )


def _schedule() -> DailySchedule:
    return DailySchedule(
        breakfast_time="07:00",
        breakfast_busyness=2,
        lunch_time="12:00",
        lunch_busyness=3,
        dinner_time="18:00",
        dinner_busyness=3,
        workout_time=None,
    )


def _planner_with_provider(provider):
    """Build MealPlanner using the given IngredientDataProvider."""
    calculator = NutritionCalculator(provider)
    aggregator = NutritionAggregator()
    scorer = RecipeScorer(calculator)
    recipe_db = RecipeDB(FIXTURES_DIR + "/test_recipes.json")
    retriever = RecipeRetriever(recipe_db)
    return MealPlanner(scorer, retriever, aggregator), recipe_db


def _make_cache_entry(name: str, calories: float, protein_g: float, fat_g: float, carbs_g: float) -> CacheEntry:
    """Build a CacheEntry with per-100g macros (micronutrients zero)."""
    micro = MicronutrientProfile()
    nutrition = MappedNutrition(
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
        micronutrients=micro,
    )
    return CacheEntry(
        canonical_name=name,
        fdc_id=0,
        description=name,
        data_type="SR Legacy",
        nutrition=nutrition,
    )


# ---------------------------------------------------------------------------
# Test 1 — Local provider regression
# ---------------------------------------------------------------------------


class TestLocalProviderRegression:
    """Planner works identically using LocalIngredientProvider."""

    def test_planner_with_local_provider_produces_valid_result(self):
        nutrition_db = NutritionDB(FIXTURES_DIR + "/test_ingredients.json")
        provider = LocalIngredientProvider(nutrition_db)
        planner, recipe_db = _planner_with_provider(provider)

        all_recipes = recipe_db.get_all_recipes()
        all_ingredient_names = extract_ingredient_names(all_recipes)
        provider.resolve_all(all_ingredient_names)

        result = planner.plan_daily_meals(
            user_profile=_user_profile(),
            schedule=_schedule(),
            available_recipes=all_recipes,
        )

        assert isinstance(result, PlanningResult)
        assert result.daily_plan is not None
        assert len(result.daily_plan.meals) == 3
        assert result.total_nutrition is not None
        assert "calories" in result.target_adherence
        assert "protein" in result.target_adherence
        assert result.total_nutrition.calories >= 0
        assert result.total_nutrition.protein_g >= 0


# ---------------------------------------------------------------------------
# Test 2 — API provider (mocked)
# ---------------------------------------------------------------------------


class TestAPIProviderMocked:
    """Planner runs with APIIngredientProvider when lookup is mocked."""

    def test_planner_with_mocked_api_provider_succeeds(self):
        # Per-100g values matching test_ingredients.json for ingredients used in test recipes
        mock_entries = {
            "egg": _make_cache_entry("egg", 143.0, 12.6, 9.5, 0.7),  # approx per 100g
            "salmon": _make_cache_entry("salmon", 208.0, 25.4, 12.4, 0.0),
            "cream of rice": _make_cache_entry("cream of rice", 370.0, 7.0, 0.5, 82.0),
            "chicken breast": _make_cache_entry("chicken breast", 165.0, 31.0, 3.6, 0.0),
            "white rice": _make_cache_entry("white rice", 130.0, 2.7, 0.3, 28.0),
            "broccoli": _make_cache_entry("broccoli", 34.0, 2.8, 0.4, 7.0),
            "olive oil": _make_cache_entry("olive oil", 884.0, 0.0, 100.0, 0.0),
            "potato": _make_cache_entry("potato", 77.0, 2.0, 0.1, 17.0),
            "whey protein powder": _make_cache_entry("whey protein powder", 400.0, 80.0, 3.3, 10.0),  # per 100g equiv
            "blueberries": _make_cache_entry("blueberries", 57.0, 0.7, 0.3, 14.5),
            "water": _make_cache_entry("water", 0.0, 0.0, 0.0, 0.0),
            "teriyaki sauce": _make_cache_entry("teriyaki sauce", 89.0, 5.9, 0.0, 15.6),
        }

        def default_entry(name: str) -> CacheEntry:
            return _make_cache_entry(name, 100.0, 10.0, 5.0, 10.0)

        mock_lookup = MagicMock(spec=CachedIngredientLookup)
        def lookup(name: str):
            key = name.lower()
            return mock_entries.get(key) or default_entry(name)

        mock_lookup.lookup = lookup

        provider = APIIngredientProvider(mock_lookup)
        planner, recipe_db = _planner_with_provider(provider)

        all_recipes = recipe_db.get_all_recipes()
        all_ingredient_names = extract_ingredient_names(all_recipes)
        provider.resolve_all(all_ingredient_names)

        result = planner.plan_daily_meals(
            user_profile=_user_profile(),
            schedule=_schedule(),
            available_recipes=all_recipes,
        )

        assert isinstance(result, PlanningResult)
        assert result.daily_plan is not None
        assert len(result.daily_plan.meals) == 3
        assert result.total_nutrition is not None
        assert result.total_nutrition.calories >= 0


# ---------------------------------------------------------------------------
# Test 3 — Deterministic identical output
# ---------------------------------------------------------------------------


class TestDeterministicIdenticalOutput:
    """Local and API providers produce identical planning when data matches."""

    def test_local_and_api_provider_same_result_for_per_100g_recipes(self):
        """Use recipes that only use per_100g ingredients so both providers match."""
        # Cooking times ≤15 min so all meals (busyness 2 = 15 min max) have candidates
        recipes_per_100g_only = [
            Recipe(
                id="r1",
                name="Salmon Bowl",
                ingredients=[
                    Ingredient(name="salmon", quantity=200.0, unit="g", is_to_taste=False),
                    Ingredient(name="white rice", quantity=150.0, unit="g", is_to_taste=False),
                ],
                cooking_time_minutes=15,
                instructions=[],
            ),
            Recipe(
                id="r2",
                name="Chicken Rice",
                ingredients=[
                    Ingredient(name="chicken breast", quantity=150.0, unit="g", is_to_taste=False),
                    Ingredient(name="white rice", quantity=200.0, unit="g", is_to_taste=False),
                ],
                cooking_time_minutes=15,
                instructions=[],
            ),
            Recipe(
                id="r3",
                name="Broccoli Rice",
                ingredients=[
                    Ingredient(name="broccoli", quantity=100.0, unit="g", is_to_taste=False),
                    Ingredient(name="white rice", quantity=250.0, unit="g", is_to_taste=False),
                ],
                cooking_time_minutes=10,
                instructions=[],
            ),
        ]

        # Local path
        nutrition_db = NutritionDB(FIXTURES_DIR + "/test_ingredients.json")
        local_provider = LocalIngredientProvider(nutrition_db)
        local_planner, _ = _planner_with_provider(local_provider)
        names = extract_ingredient_names(recipes_per_100g_only)
        local_provider.resolve_all(names)
        result_local = local_planner.plan_daily_meals(
            user_profile=_user_profile(),
            schedule=_schedule(),
            available_recipes=recipes_per_100g_only,
        )

        # API path: mock with same per_100g as local JSON
        mock_entries = {
            "salmon": _make_cache_entry("salmon", 208.0, 25.4, 12.4, 0.0),
            "white rice": _make_cache_entry("white rice", 130.0, 2.7, 0.3, 28.0),
            "chicken breast": _make_cache_entry("chicken breast", 165.0, 31.0, 3.6, 0.0),
            "broccoli": _make_cache_entry("broccoli", 34.0, 2.8, 0.4, 7.0),
        }
        def default_entry(name: str) -> CacheEntry:
            return _make_cache_entry(name, 100.0, 10.0, 5.0, 10.0)
        mock_lookup = MagicMock(spec=CachedIngredientLookup)
        mock_lookup.lookup = lambda n: mock_entries.get(n.lower()) or default_entry(n)
        api_provider = APIIngredientProvider(mock_lookup)
        api_provider.resolve_all(names)
        api_planner, _ = _planner_with_provider(api_provider)
        result_api = api_planner.plan_daily_meals(
            user_profile=_user_profile(),
            schedule=_schedule(),
            available_recipes=recipes_per_100g_only,
        )

        assert result_local.daily_plan is not None
        assert result_api.daily_plan is not None
        assert result_local.success == result_api.success
        assert len(result_local.daily_plan.meals) == len(result_api.daily_plan.meals)
        for m_local, m_api in zip(result_local.daily_plan.meals, result_api.daily_plan.meals):
            assert m_local.meal_type == m_api.meal_type
            assert m_local.recipe.id == m_api.recipe.id
        assert abs(result_local.total_nutrition.calories - result_api.total_nutrition.calories) < 1.0
        assert abs(result_local.total_nutrition.protein_g - result_api.total_nutrition.protein_g) < 0.5


# ---------------------------------------------------------------------------
# Test 4 — No API calls after resolve_all
# ---------------------------------------------------------------------------


class TestNoAPICallsAfterResolveAll:
    """USDA client is never called during planning."""

    def test_no_usda_calls_during_planning(self):
        mock_entries = {
            "egg": _make_cache_entry("egg", 143.0, 12.6, 9.5, 0.7),
            "salmon": _make_cache_entry("salmon", 208.0, 25.4, 12.4, 0.0),
            "cream of rice": _make_cache_entry("cream of rice", 370.0, 7.0, 0.5, 82.0),
            "chicken breast": _make_cache_entry("chicken breast", 165.0, 31.0, 3.6, 0.0),
            "white rice": _make_cache_entry("white rice", 130.0, 2.7, 0.3, 28.0),
            "broccoli": _make_cache_entry("broccoli", 34.0, 2.8, 0.4, 7.0),
            "olive oil": _make_cache_entry("olive oil", 884.0, 0.0, 100.0, 0.0),
            "potato": _make_cache_entry("potato", 77.0, 2.0, 0.1, 17.0),
            "whey protein powder": _make_cache_entry("whey protein powder", 400.0, 80.0, 3.3, 10.0),
            "blueberries": _make_cache_entry("blueberries", 57.0, 0.7, 0.3, 14.5),
            "water": _make_cache_entry("water", 0.0, 0.0, 0.0, 0.0),
            "teriyaki sauce": _make_cache_entry("teriyaki sauce", 89.0, 5.9, 0.0, 15.6),
        }
        def default_entry(name: str) -> CacheEntry:
            return _make_cache_entry(name, 100.0, 10.0, 5.0, 10.0)
        mock_lookup = MagicMock(spec=CachedIngredientLookup)
        mock_lookup.lookup = lambda n: mock_entries.get(n.lower()) or default_entry(n)

        provider = APIIngredientProvider(mock_lookup)
        planner, recipe_db = _planner_with_provider(provider)
        all_recipes = recipe_db.get_all_recipes()
        names = extract_ingredient_names(all_recipes)
        provider.resolve_all(names)

        with patch("src.ingestion.usda_client.requests") as mock_requests:
            mock_requests.get = MagicMock()
            mock_requests.post = MagicMock()
            result = planner.plan_daily_meals(
                user_profile=_user_profile(),
                schedule=_schedule(),
                available_recipes=all_recipes,
            )

        assert result.daily_plan is not None
        assert len(result.daily_plan.meals) == 3
        mock_requests.get.assert_not_called()
        mock_requests.post.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5 — Failure raises IngredientResolutionError
# ---------------------------------------------------------------------------


class TestFailureRaisesIngredientResolutionError:
    """resolve_all fails fast and raises IngredientResolutionError."""

    def test_resolve_all_raises_when_lookup_returns_none(self):
        mock_lookup = MagicMock(spec=CachedIngredientLookup)
        mock_lookup.lookup = lambda n: None

        provider = APIIngredientProvider(mock_lookup)
        with pytest.raises(IngredientResolutionError, match="Failed to resolve ingredient"):
            provider.resolve_all(["unknown ingredient"])

    def test_resolve_all_raises_when_lookup_raises(self):
        mock_lookup = MagicMock(spec=CachedIngredientLookup)
        def lookup(_n):
            raise ConnectionError("network error")
        mock_lookup.lookup = lookup

        provider = APIIngredientProvider(mock_lookup)
        with pytest.raises(IngredientResolutionError, match="Failed to resolve ingredient"):
            provider.resolve_all(["chicken breast"])

    def test_resolve_all_fail_fast_does_not_partially_populate(self):
        # Sorted order is ["broccoli", "chicken breast", "salmon"]. Fail on first so cache stays empty.
        call_log = []
        def lookup(name: str):
            call_log.append(name)
            if name == "broccoli":
                raise ValueError("API error for broccoli")
            return _make_cache_entry(name, 100.0, 10.0, 5.0, 10.0)

        mock_lookup = MagicMock(spec=CachedIngredientLookup)
        mock_lookup.lookup = lookup

        provider = APIIngredientProvider(mock_lookup)
        with pytest.raises(IngredientResolutionError):
            provider.resolve_all(["chicken breast", "salmon", "broccoli"])

        assert "broccoli" in call_log
        assert len(provider._resolved) == 0
