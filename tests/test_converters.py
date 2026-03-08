"""Tests for the planning conversion layer (converters.py)."""

import pytest

from src.data_layer.models import (
    Recipe,
    Ingredient,
    UserProfile,
    NutritionProfile,
    WeeklyNutritionTargets,
)
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.recipe_db import RecipeDB
from src.nutrition.calculator import NutritionCalculator
from src.planning.converters import (
    extract_ingredient_names,
    convert_recipes,
    convert_profile,
)
from src.planning.phase0_models import PlanningRecipe, MealSlot
from src.providers.local_provider import LocalIngredientProvider


FIXTURES_DIR = "tests/fixtures"


# ---------------------------------------------------------------------------
# extract_ingredient_names
# ---------------------------------------------------------------------------


class TestExtractIngredientNames:
    """Match behavior used in test_ingredient_provider_integration; uniqueness, sorting, filtering."""

    def test_skips_to_taste(self):
        recipes = [
            Recipe(
                id="r1",
                name="R1",
                ingredients=[
                    Ingredient("salt", 0.0, "to taste", is_to_taste=True),
                    Ingredient("egg", 2.0, "large", is_to_taste=False),
                ],
                cooking_time_minutes=5,
                instructions=[],
            )
        ]
        names = extract_ingredient_names(recipes)
        assert names == ["egg"]
        assert "salt" not in names

    def test_uniqueness(self):
        recipes = [
            Recipe("r1", "R1", [Ingredient("egg", 1.0, "large", False)], 5, []),
            Recipe("r2", "R2", [Ingredient("egg", 2.0, "large", False)], 5, []),
        ]
        names = extract_ingredient_names(recipes)
        assert names == ["egg"]

    def test_sorted(self):
        recipes = [
            Recipe("r1", "R1", [Ingredient("zucchini", 1.0, "g", False)], 5, []),
            Recipe("r2", "R2", [Ingredient("apple", 1.0, "g", False)], 5, []),
        ]
        names = extract_ingredient_names(recipes)
        assert names == ["apple", "zucchini"]

    def test_skips_none_or_empty_name(self):
        recipes = [
            Recipe(
                "r1",
                "R1",
                [
                    Ingredient("egg", 1.0, "large", False),
                    Ingredient("", 1.0, "g", False),
                    Ingredient("  ", 1.0, "g", False),
                ],
                cooking_time_minutes=5,
                instructions=[],
            )
        ]
        names = extract_ingredient_names(recipes)
        assert names == ["egg"]

    def test_empty_recipes_returns_empty_list(self):
        assert extract_ingredient_names([]) == []

    def test_deterministic_same_input_twice(self):
        recipes = [
            Recipe("r1", "R1", [Ingredient("b", 1.0, "g", False)], 5, []),
            Recipe("r2", "R2", [Ingredient("a", 1.0, "g", False)], 5, []),
        ]
        out1 = extract_ingredient_names(recipes)
        out2 = extract_ingredient_names(recipes)
        assert out1 == out2 == ["a", "b"]


# ---------------------------------------------------------------------------
# convert_recipes
# ---------------------------------------------------------------------------


class TestConvertRecipes:
    """Use fixture recipes and real NutritionCalculator backed by LocalIngredientProvider."""

    @pytest.fixture
    def recipe_db(self):
        return RecipeDB(FIXTURES_DIR + "/test_recipes.json")

    @pytest.fixture
    def provider(self):
        nutrition_db = NutritionDB(FIXTURES_DIR + "/test_ingredients.json")
        return LocalIngredientProvider(nutrition_db)

    @pytest.fixture
    def calculator(self, provider):
        return NutritionCalculator(provider)

    def test_nutrition_attached(self, recipe_db, provider, calculator):
        all_recipes = recipe_db.get_all_recipes()
        names = extract_ingredient_names(all_recipes)
        provider.resolve_all(names)
        pool = convert_recipes(all_recipes, calculator)
        assert len(pool) == len(all_recipes)
        for pr in pool:
            assert isinstance(pr, PlanningRecipe)
            assert pr.nutrition is not None
            assert hasattr(pr.nutrition, "calories")
            assert pr.nutrition.calories >= 0
            assert pr.primary_carb_contribution is None
            assert pr.primary_carb_source is None

    def test_sorted_by_id(self, recipe_db, provider, calculator):
        all_recipes = recipe_db.get_all_recipes()
        names = extract_ingredient_names(all_recipes)
        provider.resolve_all(names)
        pool = convert_recipes(all_recipes, calculator)
        ids = [p.id for p in pool]
        assert ids == sorted(ids)

    def test_deterministic_output(self, recipe_db, provider, calculator):
        all_recipes = recipe_db.get_all_recipes()
        names = extract_ingredient_names(all_recipes)
        provider.resolve_all(names)
        pool1 = convert_recipes(all_recipes, calculator)
        pool2 = convert_recipes(all_recipes, calculator)
        assert len(pool1) == len(pool2)
        for p1, p2 in zip(pool1, pool2):
            assert p1.id == p2.id
            assert p1.nutrition.calories == p2.nutrition.calories


# ---------------------------------------------------------------------------
# convert_profile
# ---------------------------------------------------------------------------


def _user_profile_no_weekly() -> UserProfile:
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


def _user_profile_with_weekly_targets() -> UserProfile:
    weekly = WeeklyNutritionTargets(iron_mg=70.0, vitamin_c_mg=700.0)
    return UserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=200.0,
        schedule={"08:00": 2, "13:00": 3, "19:00": 4},
        liked_foods=["chicken"],
        disliked_foods=[],
        allergies=["shellfish"],
        weekly_targets=weekly,
    )


class TestConvertProfile:
    """With/without weekly_targets, D=1, D=7, schedule replication, excluded, defaults, determinism."""

    def test_excluded_ingredients_combined(self):
        profile = _user_profile_no_weekly()
        planning = convert_profile(profile, days=1)
        assert "peanut" in planning.excluded_ingredients
        assert "mushroom" in planning.excluded_ingredients
        assert set(planning.excluded_ingredients) == {"peanut", "mushroom"}

    def test_without_weekly_targets_empty_micro(self):
        profile = _user_profile_no_weekly()
        planning = convert_profile(profile, days=1)
        assert planning.micronutrient_targets == {}

    def test_with_weekly_targets_extracts_daily(self):
        profile = _user_profile_with_weekly_targets()
        planning = convert_profile(profile, days=1)
        assert "iron_mg" in planning.micronutrient_targets
        assert planning.micronutrient_targets["iron_mg"] == pytest.approx(70.0 / 7.0)
        assert planning.micronutrient_targets["vitamin_c_mg"] == pytest.approx(700.0 / 7.0)

    def test_d1_schedule_length_one_day(self):
        profile = _user_profile_no_weekly()
        planning = convert_profile(profile, days=1)
        assert len(planning.schedule) == 1
        assert len(planning.schedule[0]) == 3
        assert planning.schedule[0][0].meal_type == "breakfast"
        assert planning.schedule[0][1].meal_type == "lunch"
        assert planning.schedule[0][2].meal_type == "dinner"

    def test_d7_schedule_replicated_seven_days(self):
        profile = _user_profile_no_weekly()
        planning = convert_profile(profile, days=7)
        assert len(planning.schedule) == 7
        for d in range(7):
            assert len(planning.schedule[d]) == 3
            assert planning.schedule[d][0].time == "07:00"
            assert planning.schedule[d][0].busyness_level == 2

    def test_default_demographic(self):
        profile = _user_profile_no_weekly()
        planning = convert_profile(profile, days=1)
        assert planning.demographic == "adult_male"

    def test_pass_through_macros_and_calories(self):
        profile = _user_profile_no_weekly()
        profile = UserProfile(
            daily_calories=1800,
            daily_protein_g=90.0,
            daily_fat_g=(40.0, 70.0),
            daily_carbs_g=200.0,
            schedule={"07:00": 2, "12:00": 3, "18:00": 3},
            liked_foods=[],
            disliked_foods=[],
            allergies=[],
            max_daily_calories=1900,
        )
        planning = convert_profile(profile, days=1)
        assert planning.daily_calories == 1800
        assert planning.daily_protein_g == 90.0
        assert planning.daily_fat_g == (40.0, 70.0)
        assert planning.daily_carbs_g == 200.0
        assert planning.max_daily_calories == 1900

    def test_meal_types_per_day_override(self):
        profile = _user_profile_no_weekly()
        meal_types_per_day = [
            ["breakfast", "lunch", "dinner"],
            ["brunch", "snack", "dinner"],
        ]
        planning = convert_profile(profile, days=2, meal_types_per_day=meal_types_per_day)
        assert planning.schedule[0][0].meal_type == "breakfast"
        assert planning.schedule[0][1].meal_type == "lunch"
        assert planning.schedule[1][0].meal_type == "brunch"
        assert planning.schedule[1][1].meal_type == "snack"

    def test_deterministic_same_input_twice(self):
        profile = _user_profile_with_weekly_targets()
        p1 = convert_profile(profile, days=3)
        p2 = convert_profile(profile, days=3)
        assert len(p1.schedule) == len(p2.schedule) == 3
        assert p1.micronutrient_targets == p2.micronutrient_targets
        assert p1.excluded_ingredients == p2.excluded_ingredients


# ---------------------------------------------------------------------------
# Determinism (cross-function)
# ---------------------------------------------------------------------------


class TestConvertersDeterminism:
    """Same input twice yields identical output."""

    def test_convert_recipes_and_convert_profile_determinism(self):
        recipe_db = RecipeDB(FIXTURES_DIR + "/test_recipes.json")
        nutrition_db = NutritionDB(FIXTURES_DIR + "/test_ingredients.json")
        provider = LocalIngredientProvider(nutrition_db)
        all_recipes = recipe_db.get_all_recipes()
        names = extract_ingredient_names(all_recipes)
        provider.resolve_all(names)
        calculator = NutritionCalculator(provider)

        pool1 = convert_recipes(all_recipes, calculator)
        pool2 = convert_recipes(all_recipes, calculator)
        assert [p.id for p in pool1] == [p.id for p in pool2]
        assert [p.nutrition.calories for p in pool1] == [p.nutrition.calories for p in pool2]

        profile = _user_profile_no_weekly()
        plan1 = convert_profile(profile, days=2)
        plan2 = convert_profile(profile, days=2)
        assert len(plan1.schedule) == len(plan2.schedule)
        assert plan1.daily_calories == plan2.daily_calories
