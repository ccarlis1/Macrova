"""Integration tests for the public planning entry point (plan_meals)."""

import pytest

from src.data_layer.models import UserProfile
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.recipe_db import RecipeDB
from src.nutrition.calculator import NutritionCalculator
from src.planning.converters import convert_recipes, convert_profile, extract_ingredient_names
from src.planning.planner import plan_meals
from src.planning.phase0_models import PlanningUserProfile
from src.providers.local_provider import LocalIngredientProvider


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


class TestPlanMealsEndToEnd:
    """Real integration path: fixtures -> convert -> plan_meals."""

    def test_e2e_one_day_success(self):
        recipe_db = RecipeDB(FIXTURES_DIR + "/test_recipes.json")
        nutrition_db = NutritionDB(FIXTURES_DIR + "/test_ingredients.json")
        provider = LocalIngredientProvider(nutrition_db)
        all_recipes = recipe_db.get_all_recipes()
        names = extract_ingredient_names(all_recipes)
        provider.resolve_all(names)
        calculator = NutritionCalculator(provider)
        recipe_pool = convert_recipes(all_recipes, calculator)
        profile = convert_profile(_user_profile(), days=1)
        result = plan_meals(profile, recipe_pool, days=1)
        assert result.success is True

    def test_e2e_two_days_success(self):
        """Same pipeline as 1-day but days=2; verifies plan_meals returns valid MealPlanResult."""
        recipe_db = RecipeDB(FIXTURES_DIR + "/test_recipes.json")
        nutrition_db = NutritionDB(FIXTURES_DIR + "/test_ingredients.json")
        provider = LocalIngredientProvider(nutrition_db)
        all_recipes = recipe_db.get_all_recipes()
        names = extract_ingredient_names(all_recipes)
        provider.resolve_all(names)
        calculator = NutritionCalculator(provider)
        recipe_pool = convert_recipes(all_recipes, calculator)
        profile = convert_profile(_user_profile(), days=2)
        result = plan_meals(profile, recipe_pool, days=2)
        assert result.termination_code in ("TC-1", "TC-2", "TC-3", "TC-4")
        if result.success:
            assert result.plan is not None
            assert result.daily_trackers is not None
            assert len(result.daily_trackers) == 2

    def test_e2e_three_days_smoke(self):
        """D=3 smoke: plan_meals runs and returns valid result."""
        recipe_db = RecipeDB(FIXTURES_DIR + "/test_recipes.json")
        nutrition_db = NutritionDB(FIXTURES_DIR + "/test_ingredients.json")
        provider = LocalIngredientProvider(nutrition_db)
        all_recipes = recipe_db.get_all_recipes()
        names = extract_ingredient_names(all_recipes)
        provider.resolve_all(names)
        calculator = NutritionCalculator(provider)
        recipe_pool = convert_recipes(all_recipes, calculator)
        profile = convert_profile(_user_profile(), days=3)
        result = plan_meals(profile, recipe_pool, days=3)
        assert result.termination_code in ("TC-1", "TC-2", "TC-3", "TC-4")
        if result.success:
            assert result.plan is not None
            assert result.daily_trackers is not None
            assert len(result.daily_trackers) == 3


class TestPlanMealsValidation:
    """Validation: days and schedule length."""

    def test_days_zero_raises(self):
        profile = convert_profile(_user_profile(), days=1)
        recipe_pool = []
        with pytest.raises(ValueError, match="days must be 1--7"):
            plan_meals(profile, recipe_pool, days=0)

    def test_days_eight_raises(self):
        profile = convert_profile(_user_profile(), days=1)
        recipe_pool = []
        with pytest.raises(ValueError, match="days must be 1--7"):
            plan_meals(profile, recipe_pool, days=8)

    def test_schedule_length_mismatch_raises(self):
        profile = convert_profile(_user_profile(), days=1)
        recipe_pool = []
        with pytest.raises(ValueError, match="profile.schedule length"):
            plan_meals(profile, recipe_pool, days=2)


class TestPlanMealsStructuralInfeasibility:
    """Structurally infeasible micronutrient target exits early as FM-4."""

    def test_infeasible_micronutrient_target_exits_fm4_early(self):
        """When pool cannot meet weekly RDI for a tracked nutrient, search returns FM-4 with zero attempts."""
        from src.planning.phase7_search import run_meal_plan_search
        from src.planning.phase0_models import MealSlot
        from src.data_layer.models import MicronutrientProfile, NutritionProfile
        from src.planning.phase0_models import PlanningRecipe, PlanningUserProfile

        def slot():
            return MealSlot("12:00", 2, "lunch")

        schedule = [[slot(), slot()]]
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule,
            pinned_assignments={},
            excluded_ingredients=[],
            liked_foods=[],
            micronutrient_targets={"iron_mg": 1e6},
        )
        zero_iron = MicronutrientProfile(iron_mg=0.0)
        pool = [
            PlanningRecipe("r1", "r1", [], 10, NutritionProfile(1000.0, 50.0, 32.0, 125.0, micronutrients=zero_iron), None, None),
            PlanningRecipe("r2", "r2", [], 10, NutritionProfile(1000.0, 50.0, 32.0, 125.0, micronutrients=zero_iron), None, None),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert result.failure_mode == "FM-4"
        assert result.stats is not None and result.stats.get("attempts", -1) == 0
        assert "deficient_nutrients" in result.report
