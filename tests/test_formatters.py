"""Unit tests for output formatters."""

import pytest
import json
from src.data_layer.models import Ingredient, NutritionProfile
from src.output.formatters import (
    format_ingredient_string,
    format_nutrition_breakdown,
)


class TestFormatIngredientString:
    """Test ingredient string formatting."""
    
    def test_format_ingredient_basic(self):
        """Test basic ingredient formatting."""
        ingredient = Ingredient(
            name="cream of rice",
            quantity=200.0,
            unit="g",
            is_to_taste=False
        )
        result = format_ingredient_string(ingredient)
        assert result == "200 g cream of rice"
    
    def test_format_ingredient_to_taste(self):
        """Test 'to taste' ingredient formatting."""
        ingredient = Ingredient(
            name="salt",
            quantity=0.0,
            unit="to taste",
            is_to_taste=True
        )
        result = format_ingredient_string(ingredient)
        assert result == "salt to taste"
    
    def test_format_ingredient_decimal_quantity(self):
        """Test ingredient with decimal quantity."""
        ingredient = Ingredient(
            name="olive oil",
            quantity=1.5,
            unit="tsp",
            is_to_taste=False
        )
        result = format_ingredient_string(ingredient)
        assert result == "1.5 tsp olive oil"
    
    def test_format_ingredient_whole_number(self):
        """Test ingredient with whole number quantity."""
        ingredient = Ingredient(
            name="eggs",
            quantity=5.0,
            unit="large",
            is_to_taste=False
        )
        result = format_ingredient_string(ingredient)
        assert result == "5 large eggs"
    
    def test_format_ingredient_no_unit(self):
        """Test ingredient without unit."""
        ingredient = Ingredient(
            name="blueberries",
            quantity=50.0,
            unit="",
            is_to_taste=False
        )
        result = format_ingredient_string(ingredient)
        assert result == "50 blueberries"


class TestFormatNutritionBreakdown:
    """Test nutrition breakdown formatting."""
    
    def test_format_nutrition_basic(self):
        """Test basic nutrition breakdown."""
        nutrition = NutritionProfile(
            calories=800.0,
            protein_g=50.0,
            fat_g=25.0,
            carbs_g=100.0
        )
        result = format_nutrition_breakdown(nutrition)
        assert "**Calories:** 800 kcal" in result
        assert "**Protein:** 50.0g" in result
        assert "**Fat:** 25.0g" in result
        assert "**Carbs:** 100.0g" in result
    
    def test_format_nutrition_with_indent(self):
        """Test nutrition breakdown with indentation."""
        nutrition = NutritionProfile(
            calories=800.0,
            protein_g=50.0,
            fat_g=25.0,
            carbs_g=100.0
        )
        result = format_nutrition_breakdown(nutrition, indent="  ")
        assert result.startswith("  **Calories:**")
        assert "  **Protein:**" in result


# --- Formatters (MealPlanResult) ---


class TestFormatResultMarkdownAndJson:
    """Tests for format_result_markdown, format_result_json, format_result_json_string (MealPlanResult)."""

    @pytest.fixture
    def sample_planning_recipe(self):
        from src.planning.phase0_models import PlanningRecipe
        return PlanningRecipe(
            id="r1",
            name="Test Recipe One",
            ingredients=[
                Ingredient("egg", 2.0, "large", is_to_taste=False),
                Ingredient("salt", 0.0, "to taste", is_to_taste=True),
            ],
            cooking_time_minutes=10,
            nutrition=NutritionProfile(350.0, 25.0, 15.0, 20.0),
            primary_carb_contribution=None,
            primary_carb_source=None,
        )

    @pytest.fixture
    def sample_planning_recipe_two(self):
        from src.planning.phase0_models import PlanningRecipe
        return PlanningRecipe(
            id="r2",
            name="Test Recipe Two",
            ingredients=[Ingredient("chicken", 150.0, "g", is_to_taste=False)],
            cooking_time_minutes=25,
            nutrition=NutritionProfile(250.0, 35.0, 8.0, 0.0),
            primary_carb_contribution=None,
            primary_carb_source=None,
        )

    @pytest.fixture
    def recipe_by_id(self, sample_planning_recipe, sample_planning_recipe_two):
        return {
            "r1": sample_planning_recipe,
            "r2": sample_planning_recipe_two,
        }

    @pytest.fixture
    def sample_planning_profile(self):
        from src.planning.phase0_models import PlanningUserProfile, MealSlot
        return PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule=[
                [
                    MealSlot("07:00", 2, "breakfast"),
                    MealSlot("12:00", 3, "lunch"),
                ],
            ],
            excluded_ingredients=[],
            liked_foods=[],
        )

    @pytest.fixture
    def sample_meal_plan_result_success(self):
        from src.planning.phase0_models import Assignment, DailyTracker, WeeklyTracker
        from src.planning.phase10_reporting import MealPlanResult
        from src.data_layer.models import NutritionProfile
        return MealPlanResult(
            success=True,
            termination_code="TC-1",
            failure_mode=None,
            plan=[
                Assignment(0, 0, "r1", 0),
                Assignment(0, 1, "r2", 0),
            ],
            daily_trackers={
                0: DailyTracker(
                    calories_consumed=600.0,
                    protein_consumed=60.0,
                    fat_consumed=23.0,
                    carbs_consumed=20.0,
                    slots_assigned=2,
                    slots_total=2,
                ),
            },
            weekly_tracker=WeeklyTracker(
                weekly_totals=NutritionProfile(600.0, 60.0, 23.0, 20.0),
                days_completed=1,
                days_remaining=0,
                carryover_needs={},
            ),
            warning=None,
            report={},
            stats=None,
        )

    def test_markdown_contains_recipe_names(self, sample_meal_plan_result_success, recipe_by_id, sample_planning_profile):
        from src.output.formatters import format_result_markdown
        md = format_result_markdown(sample_meal_plan_result_success, recipe_by_id, sample_planning_profile, D=1)
        assert "Test Recipe One" in md
        assert "Test Recipe Two" in md

    def test_markdown_contains_nutrition_values(self, sample_meal_plan_result_success, recipe_by_id, sample_planning_profile):
        from src.output.formatters import format_result_markdown
        md = format_result_markdown(sample_meal_plan_result_success, recipe_by_id, sample_planning_profile, D=1)
        assert "350" in md
        assert "25.0" in md
        assert "600.0" in md or "600" in md

    def test_markdown_contains_day_grouping(self, sample_meal_plan_result_success, recipe_by_id, sample_planning_profile):
        from src.output.formatters import format_result_markdown
        md = format_result_markdown(sample_meal_plan_result_success, recipe_by_id, sample_planning_profile, D=1)
        assert "Day 1" in md

    def test_markdown_weekly_totals_when_d_gt_1(self, sample_meal_plan_result_success, recipe_by_id):
        from src.planning.phase0_models import PlanningUserProfile, MealSlot
        from src.output.formatters import format_result_markdown
        profile_2day = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule=[
                [MealSlot("07:00", 2, "breakfast"), MealSlot("12:00", 3, "lunch")],
                [MealSlot("07:00", 2, "breakfast"), MealSlot("12:00", 3, "lunch")],
            ],
            excluded_ingredients=[],
            liked_foods=[],
        )
        md = format_result_markdown(sample_meal_plan_result_success, recipe_by_id, profile_2day, D=2)
        assert "Weekly totals" in md

    def test_json_has_required_top_level_keys(self, sample_meal_plan_result_success, recipe_by_id, sample_planning_profile):
        from src.output.formatters import format_result_json
        data = format_result_json(sample_meal_plan_result_success, recipe_by_id, sample_planning_profile, D=1)
        assert "success" in data
        assert "termination_code" in data
        assert "days" in data
        assert "daily_plans" in data
        assert "warnings" in data
        assert "goals" in data

    def test_json_structure_and_values(self, sample_meal_plan_result_success, recipe_by_id, sample_planning_profile):
        from src.output.formatters import format_result_json
        data = format_result_json(sample_meal_plan_result_success, recipe_by_id, sample_planning_profile, D=1)
        assert data["success"] is True
        assert data["termination_code"] == "TC-1"
        assert data["days"] == 1
        assert len(data["daily_plans"]) == 1
        assert data["daily_plans"][0]["day"] == 1
        assert len(data["daily_plans"][0]["meals"]) == 2
        assert data["daily_plans"][0]["totals"]["calories"] == 600.0
        assert data["goals"]["daily_calories"] == 2400

    def test_json_string_roundtrip(self, sample_meal_plan_result_success, recipe_by_id, sample_planning_profile):
        from src.output.formatters import format_result_json_string
        s = format_result_json_string(sample_meal_plan_result_success, recipe_by_id, sample_planning_profile, D=1)
        parsed = json.loads(s)
        assert parsed["success"] is True
        assert parsed["termination_code"] == "TC-1"

    def test_failure_case_markdown_renders_warning(self, recipe_by_id, sample_planning_profile):
        from src.planning.phase10_reporting import MealPlanResult
        from src.output.formatters import format_result_markdown
        result = MealPlanResult(
            success=False,
            termination_code="TC-2",
            failure_mode="FM-4",
            plan=None,
            daily_trackers=None,
            weekly_tracker=None,
            warning={"sodium_advisory": "Weekly sodium exceeds 200% of prorated RDI."},
            report={},
            stats=None,
        )
        md = format_result_markdown(result, recipe_by_id, sample_planning_profile, D=1)
        assert "False" in md or "failure" in md.lower() or "Failure" in md
        assert "sodium" in md or "Sodium" in md or "warning" in md.lower()

    def test_failure_case_json_includes_warning(self, recipe_by_id, sample_planning_profile):
        from src.planning.phase10_reporting import MealPlanResult
        from src.output.formatters import format_result_json
        result = MealPlanResult(
            success=False,
            termination_code="TC-2",
            failure_mode="FM-4",
            plan=None,
            daily_trackers=None,
            weekly_tracker=None,
            warning={"sodium_advisory": "Weekly sodium exceeds 200% of prorated RDI."},
            report={},
            stats=None,
        )
        data = format_result_json(result, recipe_by_id, sample_planning_profile, D=1)
        assert data["success"] is False
        assert "sodium_advisory" in data["warnings"] or "sodium" in str(data["warnings"]).lower()

