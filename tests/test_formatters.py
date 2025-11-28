"""Unit tests for output formatters."""

import pytest
import json
from src.data_layer.models import (
    Ingredient,
    Recipe,
    Meal,
    DailyMealPlan,
    NutritionProfile,
    NutritionGoals
)
from src.planning.meal_planner import PlanningResult
from src.output.formatters import (
    format_ingredient_string,
    format_nutrition_breakdown,
    format_plan_markdown,
    format_plan_json,
    format_plan_json_string
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


class TestFormatPlanMarkdown:
    """Test Markdown plan formatting."""
    
    @pytest.fixture
    def sample_plan_result(self):
        """Create a sample PlanningResult for testing."""
        # Create ingredients
        ingredient1 = Ingredient(
            name="cream of rice",
            quantity=200.0,
            unit="g",
            is_to_taste=False
        )
        ingredient2 = Ingredient(
            name="whey protein powder",
            quantity=1.0,
            unit="scoop",
            is_to_taste=False
        )
        ingredient3 = Ingredient(
            name="salt",
            quantity=0.0,
            unit="to taste",
            is_to_taste=True
        )
        
        # Create recipes
        recipe1 = Recipe(
            id="r1",
            name="Preworkout Meal",
            ingredients=[ingredient1, ingredient2, ingredient3],
            cooking_time_minutes=5,
            instructions=["Mix cream of rice with water", "Add protein powder", "Season to taste"]
        )
        
        recipe2 = Recipe(
            id="r2",
            name="Breakfast Scramble",
            ingredients=[
                Ingredient(name="eggs", quantity=5.0, unit="large", is_to_taste=False),
                Ingredient(name="potatoes", quantity=175.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=["Scramble eggs", "Cook potatoes"]
        )
        
        # Create meals
        meal1 = Meal(
            recipe=recipe1,
            nutrition=NutritionProfile(calories=600.0, protein_g=40.0, fat_g=5.0, carbs_g=80.0),
            meal_type="breakfast",
            busyness_level=2
        )
        
        meal2 = Meal(
            recipe=recipe2,
            nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=30.0, carbs_g=100.0),
            meal_type="lunch",
            busyness_level=3
        )
        
        # Create daily plan
        goals = NutritionGoals(
            calories=2400,
            protein_g=150.0,
            fat_g_min=50.0,
            fat_g_max=100.0,
            carbs_g=300.0
        )
        
        total_nutrition = NutritionProfile(
            calories=1400.0,
            protein_g=90.0,
            fat_g=35.0,
            carbs_g=180.0
        )
        
        daily_plan = DailyMealPlan(
            date="2024-01-01",
            meals=[meal1, meal2],
            total_nutrition=total_nutrition,
            goals=goals,
            meets_goals=True
        )
        
        return PlanningResult(
            daily_plan=daily_plan,
            success=True,
            total_nutrition=total_nutrition,
            target_adherence={
                "calories": 95.0,
                "protein": 98.0,
                "fat": 85.0,
                "carbs": 92.0
            },
            warnings=[]
        )
    
    def test_format_markdown_basic(self, sample_plan_result):
        """Test basic Markdown formatting."""
        result = format_plan_markdown(sample_plan_result)
        
        # Check header
        assert "# Daily Meal Plan" in result
        
        # Check success status
        assert "✅ **Plan meets nutrition goals**" in result
        
        # Check meal names
        assert "## Meal 1: Preworkout Meal" in result
        assert "## Meal 2: Breakfast Scramble" in result
        
        # Check ingredients
        assert "200 g cream of rice" in result
        assert "1 scoop whey protein powder" in result
        assert "salt to taste" in result
        
        # Check cooking time
        assert "**Cooking Time:** 5 minutes" in result
        assert "**Cooking Time:** 20 minutes" in result
        
        # Check nutrition breakdown
        assert "**Calories:** 600 kcal" in result
        assert "**Protein:** 40.0g" in result
        
        # Check daily totals
        assert "## Daily Totals" in result
        assert "**Calories:** 1400 kcal" in result
        
        # Check goals
        assert "## Goals & Adherence" in result
        assert "**Target Calories:** 2400" in result
    
    def test_format_markdown_with_warnings(self, sample_plan_result):
        """Test Markdown formatting with warnings."""
        sample_plan_result.warnings = [
            "Calories below target: 1400 / 2400 (58.3%)",
            "Protein below target: 90.0g / 150.0g (60.0%)"
        ]
        sample_plan_result.success = False
        
        result = format_plan_markdown(sample_plan_result)
        
        assert "⚠️ **Plan has warnings**" in result
        assert "## Warnings" in result
        assert "Calories below target" in result
        assert "Protein below target" in result
    
    def test_format_markdown_instructions(self, sample_plan_result):
        """Test that instructions are included in Markdown."""
        result = format_plan_markdown(sample_plan_result)
        
        assert "### Instructions" in result
        assert "Mix cream of rice with water" in result
        assert "Add protein powder" in result


class TestFormatPlanJson:
    """Test JSON plan formatting."""
    
    @pytest.fixture
    def sample_plan_result(self):
        """Create a sample PlanningResult for testing."""
        ingredient = Ingredient(
            name="cream of rice",
            quantity=200.0,
            unit="g",
            is_to_taste=False
        )
        
        recipe = Recipe(
            id="r1",
            name="Preworkout Meal",
            ingredients=[ingredient],
            cooking_time_minutes=5,
            instructions=["Mix and cook"]
        )
        
        meal = Meal(
            recipe=recipe,
            nutrition=NutritionProfile(calories=600.0, protein_g=40.0, fat_g=5.0, carbs_g=80.0),
            meal_type="breakfast",
            busyness_level=2
        )
        
        goals = NutritionGoals(
            calories=2400,
            protein_g=150.0,
            fat_g_min=50.0,
            fat_g_max=100.0,
            carbs_g=300.0
        )
        
        daily_plan = DailyMealPlan(
            date="2024-01-01",
            meals=[meal],
            total_nutrition=NutritionProfile(calories=600.0, protein_g=40.0, fat_g=5.0, carbs_g=80.0),
            goals=goals,
            meets_goals=True
        )
        
        return PlanningResult(
            daily_plan=daily_plan,
            success=True,
            total_nutrition=NutritionProfile(calories=600.0, protein_g=40.0, fat_g=5.0, carbs_g=80.0),
            target_adherence={"calories": 95.0, "protein": 98.0, "fat": 85.0, "carbs": 92.0},
            warnings=[]
        )
    
    def test_format_json_basic(self, sample_plan_result):
        """Test basic JSON formatting."""
        result = format_plan_json(sample_plan_result)
        
        # Check top-level structure
        assert "success" in result
        assert "date" in result
        assert "meals" in result
        assert "total_nutrition" in result
        assert "goals" in result
        assert "target_adherence" in result
        assert "warnings" in result
        assert "meets_goals" in result
        
        # Check values
        assert result["success"] is True
        assert result["date"] == "2024-01-01"
        assert len(result["meals"]) == 1
    
    def test_format_json_meal_structure(self, sample_plan_result):
        """Test meal structure in JSON."""
        result = format_plan_json(sample_plan_result)
        meal = result["meals"][0]
        
        assert meal["meal_type"] == "breakfast"
        assert meal["busyness_level"] == 2
        assert "recipe" in meal
        assert "nutrition" in meal
        
        # Check recipe structure
        recipe = meal["recipe"]
        assert recipe["id"] == "r1"
        assert recipe["name"] == "Preworkout Meal"
        assert recipe["cooking_time_minutes"] == 5
        assert len(recipe["ingredients"]) == 1
        
        # Check ingredient structure
        ingredient = recipe["ingredients"][0]
        assert ingredient["name"] == "cream of rice"
        assert ingredient["quantity"] == 200.0
        assert ingredient["unit"] == "g"
        assert ingredient["is_to_taste"] is False
        assert ingredient["display"] == "200 g cream of rice"
    
    def test_format_json_nutrition(self, sample_plan_result):
        """Test nutrition formatting in JSON."""
        result = format_plan_json(sample_plan_result)
        
        # Check meal nutrition
        meal_nutrition = result["meals"][0]["nutrition"]
        assert meal_nutrition["calories"] == 600.0
        assert meal_nutrition["protein_g"] == 40.0
        assert meal_nutrition["fat_g"] == 5.0
        assert meal_nutrition["carbs_g"] == 80.0
        
        # Check total nutrition
        total_nutrition = result["total_nutrition"]
        assert total_nutrition["calories"] == 600.0
    
    def test_format_json_to_taste_ingredient(self, sample_plan_result):
        """Test JSON formatting with 'to taste' ingredient."""
        # Add a 'to taste' ingredient
        to_taste_ingredient = Ingredient(
            name="salt",
            quantity=0.0,
            unit="to taste",
            is_to_taste=True
        )
        sample_plan_result.daily_plan.meals[0].recipe.ingredients.append(to_taste_ingredient)
        
        result = format_plan_json(sample_plan_result)
        ingredients = result["meals"][0]["recipe"]["ingredients"]
        
        # Find the 'to taste' ingredient
        salt_ingredient = next(ing for ing in ingredients if ing["name"] == "salt")
        assert salt_ingredient["is_to_taste"] is True
        assert salt_ingredient["display"] == "salt to taste"
    
    def test_format_json_string(self, sample_plan_result):
        """Test JSON string formatting."""
        result = format_plan_json_string(sample_plan_result)
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert isinstance(result, str)
    
    def test_format_json_warnings(self, sample_plan_result):
        """Test JSON formatting with warnings."""
        sample_plan_result.warnings = ["Warning 1", "Warning 2"]
        sample_plan_result.success = False
        
        result = format_plan_json(sample_plan_result)
        
        assert result["success"] is False
        assert len(result["warnings"]) == 2
        assert "Warning 1" in result["warnings"]
        assert "Warning 2" in result["warnings"]
    
    def test_format_json_adherence(self, sample_plan_result):
        """Test adherence formatting in JSON."""
        result = format_plan_json(sample_plan_result)
        
        adherence = result["target_adherence"]
        assert adherence["calories"] == 95.0
        assert adherence["protein"] == 98.0
        assert adherence["fat"] == 85.0
        assert adherence["carbs"] == 92.0

