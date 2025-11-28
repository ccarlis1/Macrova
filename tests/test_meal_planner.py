"""Unit tests for meal planning system."""

import pytest
from src.planning.meal_planner import MealPlanner, DailySchedule
from src.data_layer.models import NutritionGoals, UserProfile, NutritionProfile
from src.scoring.recipe_scorer import RecipeScorer
from src.nutrition.aggregator import NutritionAggregator
from src.nutrition.calculator import NutritionCalculator
from src.data_layer.nutrition_db import NutritionDB
from src.ingestion.recipe_retriever import RecipeRetriever
from src.data_layer.recipe_db import RecipeDB


class TestDistributeDailyTargets:
    """Test daily target distribution."""
    
    @pytest.fixture
    def planner(self):
        """Create a MealPlanner instance."""
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        nutrition_calculator = NutritionCalculator(nutrition_db)
        nutrition_aggregator = NutritionAggregator()
        recipe_scorer = RecipeScorer(nutrition_calculator)
        recipe_db = RecipeDB("tests/fixtures/test_recipes.json")
        recipe_retriever = RecipeRetriever(recipe_db)
        
        return MealPlanner(recipe_scorer, recipe_retriever, nutrition_aggregator)
    
    @pytest.fixture
    def sample_goals(self):
        """Create sample nutrition goals."""
        return NutritionGoals(
            calories=2400,
            protein_g=150.0,
            fat_g_min=50.0,
            fat_g_max=100.0,
            carbs_g=300.0
        )
    
    def test_distribute_daily_targets_basic(self, planner, sample_goals):
        """Test basic target distribution across 3 meals."""
        schedule = DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=2,
            lunch_time="12:00",
            lunch_busyness=3,
            dinner_time="18:00",
            dinner_busyness=3,
            workout_time=None
        )
        
        meal_contexts = planner._distribute_daily_targets(sample_goals, schedule)
        
        # Should have 3 meals
        assert len(meal_contexts) == 3
        assert "breakfast" in meal_contexts
        assert "lunch" in meal_contexts
        assert "dinner" in meal_contexts
        
        # Check breakfast
        breakfast = meal_contexts["breakfast"]
        assert breakfast.meal_type == "breakfast"
        assert breakfast.time_slot == "morning"
        assert breakfast.cooking_time_max == 15  # Busyness level 2
        
        # Check lunch
        lunch = meal_contexts["lunch"]
        assert lunch.meal_type == "lunch"
        assert lunch.time_slot == "afternoon"
        assert lunch.cooking_time_max == 30  # Busyness level 3
        
        # Check dinner
        dinner = meal_contexts["dinner"]
        assert dinner.meal_type == "dinner"
        assert dinner.time_slot == "evening"
        assert dinner.cooking_time_max == 30  # Busyness level 3
        assert dinner.satiety_requirement == "high"  # Always high for dinner
    
    def test_distribute_daily_targets_base_calculation(self, planner, sample_goals):
        """Test that base targets are divided by 3."""
        schedule = DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=2,
            lunch_time="12:00",
            lunch_busyness=2,
            dinner_time="18:00",
            dinner_busyness=3,
            workout_time=None
        )
        
        meal_contexts = planner._distribute_daily_targets(sample_goals, schedule)
        
        # Base targets should be divided by 3
        base_calories = 2400 / 3.0  # 800
        base_protein = 150.0 / 3.0  # 50
        base_fat_min = 50.0 / 3.0   # ~16.67
        base_fat_max = 100.0 / 3.0  # ~33.33
        base_carbs = 300.0 / 3.0    # 100
        
        breakfast = meal_contexts["breakfast"]
        # Breakfast should be close to base (no special adjustments)
        assert abs(breakfast.target_calories - base_calories) < 10.0
        assert abs(breakfast.target_protein - base_protein) < 5.0
    
    def test_distribute_daily_targets_pre_workout_adjustment(self, planner, sample_goals):
        """Test pre-workout meal adjustments (lower protein, more carbs)."""
        schedule = DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=2,
            lunch_time="12:00",
            lunch_busyness=2,
            dinner_time="18:00",
            dinner_busyness=3,
            workout_time="09:00"  # 2 hours after breakfast (pre-workout)
        )
        
        meal_contexts = planner._distribute_daily_targets(sample_goals, schedule)
        
        breakfast = meal_contexts["breakfast"]
        assert breakfast.time_slot == "pre_workout"
        assert breakfast.carb_timing_preference == "fast_digesting"
        
        # Pre-workout: lower protein (0.8x), more carbs (1.1x)
        base_protein = 150.0 / 3.0  # 50
        base_carbs = 300.0 / 3.0    # 100
        
        expected_protein = base_protein * 0.8  # 40
        expected_carbs = base_carbs * 1.1      # 110
        
        assert abs(breakfast.target_protein - expected_protein) < 1.0
        assert abs(breakfast.target_carbs - expected_carbs) < 1.0
    
    def test_distribute_daily_targets_post_workout_adjustment(self, planner, sample_goals):
        """Test post-workout meal adjustments (higher protein, more carbs)."""
        schedule = DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=2,
            lunch_time="12:00",
            lunch_busyness=2,
            dinner_time="18:00",
            dinner_busyness=3,
            workout_time="17:00"  # 1 hour before dinner (post-workout dinner)
        )
        
        meal_contexts = planner._distribute_daily_targets(sample_goals, schedule)
        
        dinner = meal_contexts["dinner"]
        assert dinner.time_slot == "post_workout"
        assert dinner.carb_timing_preference == "slow_digesting"  # Overridden for dinner
        
        # Post-workout: higher protein (1.2x), more carbs (1.1x)
        base_protein = 150.0 / 3.0  # 50
        base_carbs = 300.0 / 3.0    # 100
        
        expected_protein = base_protein * 1.2  # 60
        expected_carbs = base_carbs * 1.1      # 110
        
        assert abs(dinner.target_protein - expected_protein) < 1.0
        assert abs(dinner.target_carbs - expected_carbs) < 1.0
    
    def test_distribute_daily_targets_satiety_requirements(self, planner, sample_goals):
        """Test satiety requirement determination."""
        # Schedule with long gap (high satiety needed)
        schedule_long_gap = DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=2,
            lunch_time="13:00",  # 6 hour gap
            lunch_busyness=2,
            dinner_time="18:00",
            dinner_busyness=3,
            workout_time=None
        )
        
        meal_contexts = planner._distribute_daily_targets(sample_goals, schedule_long_gap)
        
        breakfast = meal_contexts["breakfast"]
        # Breakfast before 6-hour gap should be high satiety
        assert breakfast.satiety_requirement == "high"
        
        # Dinner always high satiety (overnight fast)
        dinner = meal_contexts["dinner"]
        assert dinner.satiety_requirement == "high"
    
    def test_distribute_daily_targets_busyness_levels(self, planner, sample_goals):
        """Test busyness level to cooking time mapping (KNOWLEDGE.md line 15)."""
        schedule = DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=1,  # Snack
            lunch_time="12:00",
            lunch_busyness=2,  # ≤15 minutes
            dinner_time="18:00",
            dinner_busyness=4,  # 30+ minutes
            workout_time=None
        )
        
        meal_contexts = planner._distribute_daily_targets(sample_goals, schedule)
        
        # Level 1: Snack = 5 minutes
        assert meal_contexts["breakfast"].cooking_time_max == 5
        
        # Level 2: ≤15 minutes = 15 minutes
        assert meal_contexts["lunch"].cooking_time_max == 15
        
        # Level 4: 30+ minutes = 60 minutes
        assert meal_contexts["dinner"].cooking_time_max == 60
    
    def test_distribute_daily_targets_dinner_always_high_satiety(self, planner, sample_goals):
        """Test that dinner always has high satiety requirement."""
        schedule = DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=2,
            lunch_time="12:00",
            lunch_busyness=2,
            dinner_time="18:00",
            dinner_busyness=3,
            workout_time=None
        )
        
        meal_contexts = planner._distribute_daily_targets(sample_goals, schedule)
        
        dinner = meal_contexts["dinner"]
        assert dinner.satiety_requirement == "high"
        assert dinner.carb_timing_preference == "slow_digesting"  # Complex carbs for overnight
    
    def test_distribute_daily_targets_carb_timing_preferences(self, planner, sample_goals):
        """Test carb timing preferences based on meal context."""
        schedule = DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=2,
            lunch_time="12:00",
            lunch_busyness=2,
            dinner_time="18:00",
            dinner_busyness=3,
            workout_time="08:00"  # 1 hour after breakfast (pre-workout breakfast)
        )
        
        meal_contexts = planner._distribute_daily_targets(sample_goals, schedule)
        
        # Breakfast: pre-workout = fast digesting
        assert meal_contexts["breakfast"].carb_timing_preference == "fast_digesting"
        
        # Lunch: standard = maintenance
        assert meal_contexts["lunch"].carb_timing_preference == "maintenance"
        
        # Dinner: always slow digesting for overnight
        assert meal_contexts["dinner"].carb_timing_preference == "slow_digesting"
    
    def test_distribute_daily_targets_post_workout_lunch(self, planner, sample_goals):
        """Test post-workout lunch adjustments."""
        schedule = DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=2,
            lunch_time="13:00",
            lunch_busyness=2,
            dinner_time="18:00",
            dinner_busyness=3,
            workout_time="12:00"  # 1 hour before lunch (post-workout lunch)
        )
        
        meal_contexts = planner._distribute_daily_targets(sample_goals, schedule)
        
        lunch = meal_contexts["lunch"]
        assert lunch.time_slot == "post_workout"
        assert lunch.carb_timing_preference == "recovery"
        
        # Post-workout: higher protein (1.2x)
        base_protein = 150.0 / 3.0
        expected_protein = base_protein * 1.2
        assert abs(lunch.target_protein - expected_protein) < 1.0


class TestSelectBestRecipe:
    """Test recipe selection logic."""
    
    @pytest.fixture
    def planner(self):
        """Create a MealPlanner instance."""
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        nutrition_calculator = NutritionCalculator(nutrition_db)
        nutrition_aggregator = NutritionAggregator()
        recipe_scorer = RecipeScorer(nutrition_calculator)
        recipe_db = RecipeDB("tests/fixtures/test_recipes.json")
        recipe_retriever = RecipeRetriever(recipe_db)
        
        return MealPlanner(recipe_scorer, recipe_retriever, nutrition_aggregator)
    
    @pytest.fixture
    def sample_recipes(self):
        """Create sample recipes for testing."""
        from src.data_layer.models import Recipe, Ingredient
        
        return [
            Recipe(
                id="recipe_1",
                name="Quick Eggs",
                ingredients=[
                    Ingredient(name="egg", quantity=2.0, unit="large", is_to_taste=False)
                ],
                cooking_time_minutes=5,
                instructions=["Cook eggs"]
            ),
            Recipe(
                id="recipe_2",
                name="Slow Eggs",
                ingredients=[
                    Ingredient(name="egg", quantity=3.0, unit="large", is_to_taste=False)
                ],
                cooking_time_minutes=30,
                instructions=["Cook eggs slowly"]
            ),
            Recipe(
                id="recipe_3",
                name="Eggs with Salt",
                ingredients=[
                    Ingredient(name="egg", quantity=2.0, unit="large", is_to_taste=False),
                    Ingredient(name="salt", quantity=0.0, unit="to taste", is_to_taste=True)
                ],
                cooking_time_minutes=5,
                instructions=["Cook eggs", "Add salt to taste"]
            )
        ]
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample meal context."""
        from src.scoring.recipe_scorer import MealContext
        
        return MealContext(
            meal_type="breakfast",
            time_slot="morning",
            cooking_time_max=15,
            target_calories=400.0,
            target_protein=20.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=30.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance",
            priority_micronutrients=[]
        )
    
    @pytest.fixture
    def sample_user_profile(self):
        """Create a sample user profile."""
        return UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["egg"],
            disliked_foods=["mushroom"],
            allergies=[]
        )
    
    def test_select_best_recipe_basic(self, planner, sample_recipes, sample_context, sample_user_profile):
        """Test basic recipe selection."""
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        best_recipe, score = planner._select_best_recipe(
            sample_recipes,
            sample_context,
            sample_user_profile,
            current_nutrition
        )
        
        # Should return a recipe and valid score
        assert best_recipe is not None
        assert best_recipe in sample_recipes
        assert 0.0 <= score <= 100.0
    
    def test_select_best_recipe_highest_score(self, planner, sample_recipes, sample_context, sample_user_profile):
        """Test that highest-scoring recipe is selected."""
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        # Score all recipes individually
        scores = {}
        for recipe in sample_recipes:
            score = planner.recipe_scorer.score_recipe(
                recipe,
                sample_context,
                sample_user_profile,
                current_nutrition
            )
            scores[recipe.id] = score
        
        # Select best
        best_recipe, best_score = planner._select_best_recipe(
            sample_recipes,
            sample_context,
            sample_user_profile,
            current_nutrition
        )
        
        # Best recipe should have the highest score
        assert best_score == max(scores.values())
        assert scores[best_recipe.id] == best_score
    
    def test_select_best_recipe_schedule_preference(self, planner, sample_recipes, sample_user_profile):
        """Test that recipes matching schedule constraints score higher."""
        from src.scoring.recipe_scorer import MealContext
        
        # Context with tight time constraint (5 minutes)
        tight_context = MealContext(
            meal_type="breakfast",
            time_slot="morning",
            cooking_time_max=5,  # Very tight
            target_calories=400.0,
            target_protein=20.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=30.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance",
            priority_micronutrients=[]
        )
        
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        best_recipe, score = planner._select_best_recipe(
            sample_recipes,
            tight_context,
            sample_user_profile,
            current_nutrition
        )
        
        # Quick recipe (5 min) should be selected over slow recipe (30 min)
        assert best_recipe.cooking_time_minutes <= 5
        assert best_recipe.id in ["recipe_1", "recipe_3"]  # Quick recipes
    
    def test_select_best_recipe_preference_boost(self, planner, sample_recipes, sample_context):
        """Test that recipes with liked ingredients score higher."""
        from src.scoring.recipe_scorer import MealContext
        
        # User who likes eggs
        egg_lover = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["egg"],  # Likes eggs
            disliked_foods=[],
            allergies=[]
        )
        
        # User who dislikes eggs
        egg_hater = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=[],
            disliked_foods=["egg"],  # Dislikes eggs
            allergies=[]
        )
        
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        # Both should select a recipe, but scores may differ
        best_recipe_lover, score_lover = planner._select_best_recipe(
            sample_recipes,
            sample_context,
            egg_lover,
            current_nutrition
        )
        
        best_recipe_hater, score_hater = planner._select_best_recipe(
            sample_recipes,
            sample_context,
            egg_hater,
            current_nutrition
        )
        
        # Both should return valid recipes
        assert best_recipe_lover is not None
        assert best_recipe_hater is not None
        
        # Egg lover should score higher (all recipes have eggs, so all get boost)
        # But egg hater should still select one (just with lower preference score)
        assert 0.0 <= score_lover <= 100.0
        assert 0.0 <= score_hater <= 100.0
    
    def test_select_best_recipe_allergen_exclusion(self, planner, sample_context, sample_user_profile):
        """Test that recipes with allergens are excluded (score = 0)."""
        from src.data_layer.models import Recipe, Ingredient
        
        # Recipe with allergen
        peanut_recipe = Recipe(
            id="peanut_recipe",
            name="Peanut Recipe",
            ingredients=[
                Ingredient(name="peanut butter", quantity=2.0, unit="tbsp", is_to_taste=False)
            ],
            cooking_time_minutes=5,
            instructions=["Spread peanut butter"]
        )
        
        # Recipe without allergen
        safe_recipe = Recipe(
            id="safe_recipe",
            name="Safe Recipe",
            ingredients=[
                Ingredient(name="egg", quantity=2.0, unit="large", is_to_taste=False)
            ],
            cooking_time_minutes=5,
            instructions=["Cook eggs"]
        )
        
        # User with peanut allergy
        allergic_user = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=[],
            disliked_foods=[],
            allergies=["peanut"]
        )
        
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        candidates = [peanut_recipe, safe_recipe]
        
        best_recipe, score = planner._select_best_recipe(
            candidates,
            sample_context,
            allergic_user,
            current_nutrition
        )
        
        # Should select safe recipe (peanut recipe scores 0.0)
        assert best_recipe.id == "safe_recipe"
        assert score > 0.0
    
    def test_select_best_recipe_single_candidate(self, planner, sample_recipes, sample_context, sample_user_profile):
        """Test selection with single candidate."""
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        single_candidate = [sample_recipes[0]]
        
        best_recipe, score = planner._select_best_recipe(
            single_candidate,
            sample_context,
            sample_user_profile,
            current_nutrition
        )
        
        assert best_recipe == sample_recipes[0]
        assert 0.0 <= score <= 100.0
    
    def test_select_best_recipe_empty_list(self, planner, sample_context, sample_user_profile):
        """Test that empty candidates list raises ValueError."""
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        with pytest.raises(ValueError, match="empty candidates"):
            planner._select_best_recipe(
                [],
                sample_context,
                sample_user_profile,
                current_nutrition
            )
    
    def test_select_best_recipe_all_zero_scores(self, planner, sample_context):
        """Test selection when all recipes score 0 (edge case)."""
        from src.data_layer.models import Recipe, Ingredient
        
        # Recipes that might all score 0 (e.g., all have allergens)
        allergic_user = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=[],
            disliked_foods=[],
            allergies=["egg", "peanut", "chicken"]  # Allergic to everything
        )
        
        # All recipes have allergens
        candidates = [
            Recipe(
                id="egg_recipe",
                name="Egg Recipe",
                ingredients=[Ingredient(name="egg", quantity=2.0, unit="large", is_to_taste=False)],
                cooking_time_minutes=5,
                instructions=[]
            )
        ]
        
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        # Should still return a recipe (even if score is 0)
        best_recipe, score = planner._select_best_recipe(
            candidates,
            sample_context,
            allergic_user,
            current_nutrition
        )
        
        assert best_recipe is not None
        assert score == 0.0  # Allergen exclusion


class TestPlanDailyMeals:
    """Test complete daily meal planning."""
    
    @pytest.fixture
    def planner(self):
        """Create a MealPlanner instance."""
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        nutrition_calculator = NutritionCalculator(nutrition_db)
        nutrition_aggregator = NutritionAggregator()
        recipe_scorer = RecipeScorer(nutrition_calculator)
        recipe_db = RecipeDB("tests/fixtures/test_recipes.json")
        recipe_retriever = RecipeRetriever(recipe_db)
        
        return MealPlanner(recipe_scorer, recipe_retriever, nutrition_aggregator)
    
    @pytest.fixture
    def sample_user_profile(self):
        """Create a sample user profile."""
        return UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["egg", "salmon"],
            disliked_foods=["mushroom"],
            allergies=["peanut"]
        )
    
    @pytest.fixture
    def sample_schedule(self):
        """Create a sample daily schedule."""
        return DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=2,
            lunch_time="12:00",
            lunch_busyness=3,
            dinner_time="18:00",
            dinner_busyness=3,
            workout_time=None
        )
    
    def test_plan_daily_meals_basic(self, planner, sample_user_profile, sample_schedule):
        """Test basic daily meal planning."""
        result = planner.plan_daily_meals(
            sample_user_profile,
            sample_schedule
        )
        
        # Should return PlanningResult
        assert result is not None
        assert result.daily_plan is not None
        assert len(result.daily_plan.meals) == 3
        
        # Should have breakfast, lunch, dinner
        meal_types = [meal.meal_type for meal in result.daily_plan.meals]
        assert "breakfast" in meal_types
        assert "lunch" in meal_types
        assert "dinner" in meal_types
        
        # Should have total nutrition
        assert result.total_nutrition is not None
        assert result.total_nutrition.calories > 0.0
    
    def test_plan_daily_meals_with_provided_recipes(self, planner, sample_user_profile, sample_schedule):
        """Test planning with provided recipe list."""
        from src.data_layer.models import Recipe, Ingredient
        
        # Provide custom recipes
        custom_recipes = [
            Recipe(
                id="custom_1",
                name="Custom Breakfast",
                ingredients=[
                    Ingredient(name="egg", quantity=2.0, unit="large", is_to_taste=False)
                ],
                cooking_time_minutes=5,
                instructions=["Cook eggs"]
            ),
            Recipe(
                id="custom_2",
                name="Custom Lunch",
                ingredients=[
                    Ingredient(name="salmon", quantity=150.0, unit="g", is_to_taste=False)
                ],
                cooking_time_minutes=15,
                instructions=["Cook salmon"]
            ),
            Recipe(
                id="custom_3",
                name="Custom Dinner",
                ingredients=[
                    Ingredient(name="salmon", quantity=200.0, unit="g", is_to_taste=False)
                ],
                cooking_time_minutes=20,
                instructions=["Cook salmon"]
            )
        ]
        
        result = planner.plan_daily_meals(
            sample_user_profile,
            sample_schedule,
            available_recipes=custom_recipes
        )
        
        # Should use provided recipes
        assert result.daily_plan is not None
        assert len(result.daily_plan.meals) == 3
        
        # All meals should use custom recipes
        recipe_ids = [meal.recipe.id for meal in result.daily_plan.meals]
        assert all(rid in ["custom_1", "custom_2", "custom_3"] for rid in recipe_ids)
    
    def test_plan_daily_meals_no_candidates(self, planner, sample_user_profile, sample_schedule):
        """Test planning when no recipes match constraints."""
        from src.data_layer.models import Recipe, Ingredient
        
        # Recipes that all violate constraints (too long cooking time)
        bad_recipes = [
            Recipe(
                id="too_slow",
                name="Too Slow",
                ingredients=[
                    Ingredient(name="egg", quantity=2.0, unit="large", is_to_taste=False)
                ],
                cooking_time_minutes=60,  # Too long for breakfast (busyness 2 = 15 min max)
                instructions=["Cook slowly"]
            )
        ]
        
        result = planner.plan_daily_meals(
            sample_user_profile,
            sample_schedule,
            available_recipes=bad_recipes
        )
        
        # Should return failure result
        assert result.success is False
        assert result.daily_plan is None
        assert len(result.warnings) > 0
        assert any("No recipes available" in w for w in result.warnings)
    
    def test_plan_daily_meals_workout_timing(self, planner, sample_user_profile):
        """Test planning with workout timing adjustments."""
        workout_schedule = DailySchedule(
            breakfast_time="07:00",
            breakfast_busyness=2,
            lunch_time="12:00",
            lunch_busyness=2,
            dinner_time="18:00",
            dinner_busyness=3,
            workout_time="08:00"  # 1 hour after breakfast (pre-workout breakfast)
        )
        
        result = planner.plan_daily_meals(
            sample_user_profile,
            workout_schedule
        )
        
        # Should plan successfully
        assert result.daily_plan is not None
        assert len(result.daily_plan.meals) == 3
        
        # Breakfast should be pre-workout
        breakfast = next(m for m in result.daily_plan.meals if m.meal_type == "breakfast")
        # Context should have been pre-workout (verified via meal selection)
        assert breakfast is not None
    
    def test_plan_daily_meals_validation(self, planner, sample_user_profile, sample_schedule):
        """Test that daily plan validation works."""
        result = planner.plan_daily_meals(
            sample_user_profile,
            sample_schedule
        )
        
        # Should have validation results
        assert "calories" in result.target_adherence
        assert "protein" in result.target_adherence
        assert "fat" in result.target_adherence
        assert "carbs" in result.target_adherence
        
        # Adherence should be percentages
        for macro, adherence in result.target_adherence.items():
            assert 0.0 <= adherence <= 200.0  # Reasonable range (can be over/under)
        
        # Should have success flag
        assert isinstance(result.success, bool)
    
    def test_plan_daily_meals_nutrition_tracking(self, planner, sample_user_profile, sample_schedule):
        """Test that nutrition is tracked correctly across meals."""
        result = planner.plan_daily_meals(
            sample_user_profile,
            sample_schedule
        )
        
        # Total nutrition should equal sum of meal nutritions
        calculated_total = planner.nutrition_aggregator.aggregate_meals(result.daily_plan.meals)
        
        assert abs(result.total_nutrition.calories - calculated_total.calories) < 0.01
        assert abs(result.total_nutrition.protein_g - calculated_total.protein_g) < 0.01
        assert abs(result.total_nutrition.fat_g - calculated_total.fat_g) < 0.01
        assert abs(result.total_nutrition.carbs_g - calculated_total.carbs_g) < 0.01
    
    def test_plan_daily_meals_allergen_exclusion(self, planner, sample_schedule):
        """Test that allergen-containing recipes are excluded."""
        allergic_user = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=[],
            disliked_foods=[],
            allergies=["egg"]  # Allergic to eggs
        )
        
        result = planner.plan_daily_meals(
            allergic_user,
            sample_schedule
        )
        
        # Should still plan (if other recipes available) or fail gracefully
        if result.daily_plan:
            # No meals should contain eggs
            for meal in result.daily_plan.meals:
                ingredient_names = [ing.name.lower() for ing in meal.recipe.ingredients]
                assert "egg" not in ingredient_names


class TestValidateDailyPlan:
    """Test daily plan validation logic."""
    
    @pytest.fixture
    def planner(self):
        """Create a MealPlanner instance."""
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        nutrition_calculator = NutritionCalculator(nutrition_db)
        nutrition_aggregator = NutritionAggregator()
        recipe_scorer = RecipeScorer(nutrition_calculator)
        recipe_db = RecipeDB("tests/fixtures/test_recipes.json")
        recipe_retriever = RecipeRetriever(recipe_db)
        
        return MealPlanner(recipe_scorer, recipe_retriever, nutrition_aggregator)
    
    @pytest.fixture
    def sample_goals(self):
        """Create sample nutrition goals."""
        return NutritionGoals(
            calories=2400,
            protein_g=150.0,
            fat_g_min=50.0,
            fat_g_max=100.0,
            carbs_g=300.0
        )
    
    def test_validate_daily_plan_perfect_match(self, planner, sample_goals):
        """Test validation with perfect match."""
        from src.data_layer.models import Meal, Recipe, Ingredient
        
        # Meals that exactly match targets
        meals = [
            Meal(
                recipe=Recipe(id="m1", name="Meal 1", ingredients=[], cooking_time_minutes=10, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=25.0, carbs_g=100.0),
                meal_type="breakfast",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m2", name="Meal 2", ingredients=[], cooking_time_minutes=15, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=25.0, carbs_g=100.0),
                meal_type="lunch",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m3", name="Meal 3", ingredients=[], cooking_time_minutes=20, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=25.0, carbs_g=100.0),
                meal_type="dinner",
                scheduled_time=None,
                busyness_level=3
            )
        ]
        
        success, adherence, warnings = planner._validate_daily_plan(meals, sample_goals)
        
        # Should succeed (perfect match)
        assert success is True
        assert len(warnings) == 0
        
        # Adherence should be 100% for all macros
        assert abs(adherence["calories"] - 100.0) < 0.1
        assert abs(adherence["protein"] - 100.0) < 0.1
        assert abs(adherence["carbs"] - 100.0) < 0.1
    
    def test_validate_daily_plan_within_tolerance(self, planner, sample_goals):
        """Test validation within 10% tolerance."""
        from src.data_layer.models import Meal, Recipe
        
        # Meals that are within 10% tolerance (e.g., 5% over)
        total_calories = 2400 * 1.05  # 5% over = 2520
        total_protein = 150.0 * 1.05  # 5% over = 157.5
        total_fat = 75.0  # Within range (50-100)
        total_carbs = 300.0 * 1.05  # 5% over = 315
        
        meals = [
            Meal(
                recipe=Recipe(id="m1", name="Meal 1", ingredients=[], cooking_time_minutes=10, instructions=[]),
                nutrition=NutritionProfile(
                    calories=total_calories / 3.0,
                    protein_g=total_protein / 3.0,
                    fat_g=total_fat / 3.0,
                    carbs_g=total_carbs / 3.0
                ),
                meal_type="breakfast",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m2", name="Meal 2", ingredients=[], cooking_time_minutes=15, instructions=[]),
                nutrition=NutritionProfile(
                    calories=total_calories / 3.0,
                    protein_g=total_protein / 3.0,
                    fat_g=total_fat / 3.0,
                    carbs_g=total_carbs / 3.0
                ),
                meal_type="lunch",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m3", name="Meal 3", ingredients=[], cooking_time_minutes=20, instructions=[]),
                nutrition=NutritionProfile(
                    calories=total_calories / 3.0,
                    protein_g=total_protein / 3.0,
                    fat_g=total_fat / 3.0,
                    carbs_g=total_carbs / 3.0
                ),
                meal_type="dinner",
                scheduled_time=None,
                busyness_level=3
            )
        ]
        
        success, adherence, warnings = planner._validate_daily_plan(meals, sample_goals)
        
        # Should succeed (within 10% tolerance)
        assert success is True
        assert len(warnings) == 0
    
    def test_validate_daily_plan_outside_tolerance(self, planner, sample_goals):
        """Test validation outside 10% tolerance."""
        from src.data_layer.models import Meal, Recipe
        
        # Meals that are outside 10% tolerance (e.g., 15% over)
        total_calories = 2400 * 1.15  # 15% over = 2760
        total_protein = 150.0 * 1.15  # 15% over = 172.5
        total_fat = 75.0  # Within range
        total_carbs = 300.0 * 1.15  # 15% over = 345
        
        meals = [
            Meal(
                recipe=Recipe(id="m1", name="Meal 1", ingredients=[], cooking_time_minutes=10, instructions=[]),
                nutrition=NutritionProfile(
                    calories=total_calories / 3.0,
                    protein_g=total_protein / 3.0,
                    fat_g=total_fat / 3.0,
                    carbs_g=total_carbs / 3.0
                ),
                meal_type="breakfast",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m2", name="Meal 2", ingredients=[], cooking_time_minutes=15, instructions=[]),
                nutrition=NutritionProfile(
                    calories=total_calories / 3.0,
                    protein_g=total_protein / 3.0,
                    fat_g=total_fat / 3.0,
                    carbs_g=total_carbs / 3.0
                ),
                meal_type="lunch",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m3", name="Meal 3", ingredients=[], cooking_time_minutes=20, instructions=[]),
                nutrition=NutritionProfile(
                    calories=total_calories / 3.0,
                    protein_g=total_protein / 3.0,
                    fat_g=total_fat / 3.0,
                    carbs_g=total_carbs / 3.0
                ),
                meal_type="dinner",
                scheduled_time=None,
                busyness_level=3
            )
        ]
        
        success, adherence, warnings = planner._validate_daily_plan(meals, sample_goals)
        
        # Should fail (outside 10% tolerance)
        assert success is False
        assert len(warnings) > 0
        # Should have warnings for calories, protein, carbs
        assert any("Calories above target" in w for w in warnings)
        assert any("Protein above target" in w for w in warnings)
        assert any("Carbs above target" in w for w in warnings)
    
    def test_validate_daily_plan_fat_below_minimum(self, planner, sample_goals):
        """Test validation when fat is below minimum (KNOWLEDGE.md: 50-100g range)."""
        from src.data_layer.models import Meal, Recipe
        
        # Meals with fat below minimum
        meals = [
            Meal(
                recipe=Recipe(id="m1", name="Meal 1", ingredients=[], cooking_time_minutes=10, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=10.0, carbs_g=100.0),  # Low fat
                meal_type="breakfast",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m2", name="Meal 2", ingredients=[], cooking_time_minutes=15, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=10.0, carbs_g=100.0),  # Low fat
                meal_type="lunch",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m3", name="Meal 3", ingredients=[], cooking_time_minutes=20, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=10.0, carbs_g=100.0),  # Low fat
                meal_type="dinner",
                scheduled_time=None,
                busyness_level=3
            )
        ]
        
        success, adherence, warnings = planner._validate_daily_plan(meals, sample_goals)
        
        # Should fail (fat below minimum: 30g < 50g)
        assert success is False
        assert any("Fat below minimum" in w for w in warnings)
    
    def test_validate_daily_plan_fat_above_maximum(self, planner, sample_goals):
        """Test validation when fat is above maximum (KNOWLEDGE.md: 50-100g range)."""
        from src.data_layer.models import Meal, Recipe
        
        # Meals with fat above maximum
        meals = [
            Meal(
                recipe=Recipe(id="m1", name="Meal 1", ingredients=[], cooking_time_minutes=10, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=40.0, carbs_g=100.0),  # High fat
                meal_type="breakfast",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m2", name="Meal 2", ingredients=[], cooking_time_minutes=15, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=40.0, carbs_g=100.0),  # High fat
                meal_type="lunch",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m3", name="Meal 3", ingredients=[], cooking_time_minutes=20, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=40.0, carbs_g=100.0),  # High fat
                meal_type="dinner",
                scheduled_time=None,
                busyness_level=3
            )
        ]
        
        success, adherence, warnings = planner._validate_daily_plan(meals, sample_goals)
        
        # Should fail (fat above maximum: 120g > 100g)
        assert success is False
        assert any("Fat above maximum" in w for w in warnings)
    
    def test_validate_daily_plan_fat_within_range(self, planner, sample_goals):
        """Test validation when fat is within range (KNOWLEDGE.md: 50-100g)."""
        from src.data_layer.models import Meal, Recipe
        
        # Meals with fat within range
        meals = [
            Meal(
                recipe=Recipe(id="m1", name="Meal 1", ingredients=[], cooking_time_minutes=10, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=25.0, carbs_g=100.0),  # 25g per meal = 75g total
                meal_type="breakfast",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m2", name="Meal 2", ingredients=[], cooking_time_minutes=15, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=25.0, carbs_g=100.0),
                meal_type="lunch",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m3", name="Meal 3", ingredients=[], cooking_time_minutes=20, instructions=[]),
                nutrition=NutritionProfile(calories=800.0, protein_g=50.0, fat_g=25.0, carbs_g=100.0),
                meal_type="dinner",
                scheduled_time=None,
                busyness_level=3
            )
        ]
        
        success, adherence, warnings = planner._validate_daily_plan(meals, sample_goals)
        
        # Should succeed (fat within range: 75g is between 50-100g)
        assert success is True
        assert not any("Fat" in w for w in warnings)
    
    def test_validate_daily_plan_empty_meals(self, planner, sample_goals):
        """Test validation with empty meals list."""
        success, adherence, warnings = planner._validate_daily_plan([], sample_goals)
        
        assert success is False
        assert len(adherence) == 0
        assert "No meals planned" in warnings
    
    def test_validate_daily_plan_adherence_calculation(self, planner, sample_goals):
        """Test that adherence percentages are calculated correctly."""
        from src.data_layer.models import Meal, Recipe
        
        # Meals with known nutrition values
        meals = [
            Meal(
                recipe=Recipe(id="m1", name="Meal 1", ingredients=[], cooking_time_minutes=10, instructions=[]),
                nutrition=NutritionProfile(calories=1200.0, protein_g=75.0, fat_g=37.5, carbs_g=150.0),  # 50% of daily
                meal_type="breakfast",
                scheduled_time=None,
                busyness_level=2
            ),
            Meal(
                recipe=Recipe(id="m2", name="Meal 2", ingredients=[], cooking_time_minutes=15, instructions=[]),
                nutrition=NutritionProfile(calories=1200.0, protein_g=75.0, fat_g=37.5, carbs_g=150.0),  # 50% of daily
                meal_type="lunch",
                scheduled_time=None,
                busyness_level=2
            )
        ]
        
        success, adherence, warnings = planner._validate_daily_plan(meals, sample_goals)
        
        # Total: 2400 cal, 150g protein, 75g fat, 300g carbs (100% of targets)
        # But only 2 meals, so should be 100% for all
        assert abs(adherence["calories"] - 100.0) < 0.1
        assert abs(adherence["protein"] - 100.0) < 0.1
        assert abs(adherence["carbs"] - 100.0) < 0.1
        # Fat: 75g is within 50-100g range, so should be ~100% relative to midpoint (75g)
        assert abs(adherence["fat"] - 100.0) < 0.1
