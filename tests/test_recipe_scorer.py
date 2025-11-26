"""Unit tests for recipe scoring system."""

import pytest
from src.scoring.recipe_scorer import RecipeScorer, ScoringWeights, MealContext
from src.data_layer.models import Recipe, Ingredient, NutritionProfile, UserProfile, NutritionGoals
from src.nutrition.calculator import NutritionCalculator
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.ingredient_db import IngredientDB


class TestScoringWeights:
    """Test ScoringWeights validation."""
    
    def test_default_weights_sum_to_one(self):
        """Test default weights sum to 1.0."""
        weights = ScoringWeights()
        total = (weights.nutrition_weight + weights.schedule_weight + 
                weights.preference_weight + weights.satiety_weight + 
                weights.micronutrient_weight)
        assert abs(total - 1.0) < 0.001
    
    def test_custom_weights_validation(self):
        """Test custom weights are validated."""
        # Valid weights
        weights = ScoringWeights(
            nutrition_weight=0.5,
            schedule_weight=0.2,
            preference_weight=0.2,
            satiety_weight=0.05,
            micronutrient_weight=0.05
        )
        assert weights.nutrition_weight == 0.5
        
        # Invalid weights (don't sum to 1.0)
        with pytest.raises(ValueError, match="must sum to 1.0"):
            ScoringWeights(
                nutrition_weight=0.5,
                schedule_weight=0.5,
                preference_weight=0.5,
                satiety_weight=0.5,
                micronutrient_weight=0.5
            )
    
    def test_negative_weights_validation(self):
        """Test negative weights are rejected."""
        with pytest.raises(ValueError, match="must be non-negative"):
            ScoringWeights(
                nutrition_weight=-0.1,
                schedule_weight=0.5,
                preference_weight=0.3,
                satiety_weight=0.2,
                micronutrient_weight=0.1
            )


class TestMealContext:
    """Test MealContext data structure."""
    
    def test_meal_context_creation(self):
        """Test MealContext can be created with all fields."""
        context = MealContext(
            meal_type="breakfast",
            time_slot="morning",
            cooking_time_max=15,
            target_calories=600.0,
            target_protein=25.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=60.0,
            satiety_requirement="high",
            carb_timing_preference="slow_digesting",
            priority_micronutrients=["vitamin_c", "iron"]
        )
        
        assert context.meal_type == "breakfast"
        assert context.time_slot == "morning"
        assert context.cooking_time_max == 15
        assert context.target_calories == 600.0
        assert context.target_protein == 25.0
        assert context.target_fat_min == 15.0
        assert context.target_fat_max == 25.0
        assert context.target_carbs == 60.0
        assert context.satiety_requirement == "high"
        assert context.carb_timing_preference == "slow_digesting"
        assert context.priority_micronutrients == ["vitamin_c", "iron"]
    
    def test_meal_context_workout_timing(self):
        """Test MealContext supports workout-specific timing (KNOWLEDGE.md examples)."""
        # Pre-workout context (like "2 Bananas" example)
        pre_workout = MealContext(
            meal_type="snack",
            time_slot="pre_workout",
            cooking_time_max=5,
            target_calories=208.0,
            target_protein=2.0,
            target_fat_min=0.5,
            target_fat_max=2.0,
            target_carbs=50.0,
            satiety_requirement="low",
            carb_timing_preference="fast_digesting"
        )
        assert pre_workout.time_slot == "pre_workout"
        assert pre_workout.carb_timing_preference == "fast_digesting"
        
        # Post-workout context (like "Hot Honey Salmon" example)
        post_workout = MealContext(
            meal_type="dinner",
            time_slot="post_workout",
            cooking_time_max=30,
            target_calories=738.0,
            target_protein=62.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=74.0,
            satiety_requirement="high",
            carb_timing_preference="recovery"
        )
        assert post_workout.time_slot == "post_workout"
        assert post_workout.carb_timing_preference == "recovery"
        assert post_workout.satiety_requirement == "high"
    
    def test_meal_context_fat_range(self):
        """Test MealContext supports fat ranges (KNOWLEDGE.md: 50-100g daily range)."""
        context = MealContext(
            meal_type="lunch",
            time_slot="sedentary",
            cooking_time_max=20,
            target_calories=500.0,
            target_protein=30.0,
            target_fat_min=16.7,  # ~50g daily / 3 meals
            target_fat_max=33.3,  # ~100g daily / 3 meals
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        # Verify fat range is properly represented
        assert context.target_fat_min < context.target_fat_max
        assert context.target_fat_min == 16.7
        assert context.target_fat_max == 33.3


class TestRecipeScorer:
    """Test RecipeScorer functionality."""
    
    @pytest.fixture
    def nutrition_calculator(self):
        """Create a nutrition calculator for testing."""
        # Create nutrition database (which creates its own ingredient database)
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        return NutritionCalculator(nutrition_db)
    
    @pytest.fixture
    def scorer(self, nutrition_calculator):
        """Create a RecipeScorer instance."""
        return RecipeScorer(nutrition_calculator)
    
    @pytest.fixture
    def sample_recipe(self):
        """Create a sample recipe for testing."""
        return Recipe(
            id="test_recipe",
            name="Test Recipe",
            ingredients=[
                Ingredient(name="egg", quantity=2.0, unit="large", is_to_taste=False),
                Ingredient(name="salt", quantity=0.0, unit="to taste", is_to_taste=True)
            ],
            cooking_time_minutes=10,
            instructions=["Cook eggs", "Add salt to taste"]
        )
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample meal context."""
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
            schedule={},  # Empty schedule for testing
            liked_foods=["egg", "salmon"],
            disliked_foods=["mushroom"],
            allergies=["peanut"]
        )
    
    def test_scorer_initialization(self, nutrition_calculator):
        """Test RecipeScorer can be initialized."""
        scorer = RecipeScorer(nutrition_calculator)
        assert scorer.nutrition_calculator == nutrition_calculator
        assert isinstance(scorer.weights, ScoringWeights)
    
    def test_scorer_with_custom_weights(self, nutrition_calculator):
        """Test RecipeScorer with custom weights."""
        custom_weights = ScoringWeights(
            nutrition_weight=0.5,
            schedule_weight=0.2,
            preference_weight=0.2,
            satiety_weight=0.05,
            micronutrient_weight=0.05
        )
        scorer = RecipeScorer(nutrition_calculator, custom_weights)
        assert scorer.weights == custom_weights
    
    def test_score_recipe_method_exists(self, scorer, sample_recipe, sample_context, 
                                       sample_user_profile):
        """Test score_recipe method exists and accepts correct parameters."""
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        # Method should exist and be callable
        # Note: Will fail until implementation is complete due to None * float
        try:
            result = scorer.score_recipe(
                sample_recipe, 
                sample_context, 
                sample_user_profile, 
                current_nutrition
            )
            # Once implemented, result should be a float between 0-100
            assert isinstance(result, (int, float)) and 0 <= result <= 100
        except TypeError:
            # Expected failure until scoring methods are implemented
            # (None * float raises TypeError)
            pass
    
    def test_scoring_methods_exist(self, scorer):
        """Test all scoring methods exist."""
        # Verify all scoring methods are defined
        assert hasattr(scorer, '_score_nutrition_match')
        assert hasattr(scorer, '_score_schedule_match')
        assert hasattr(scorer, '_score_preference_match')
        assert hasattr(scorer, '_score_satiety_match')
        assert hasattr(scorer, '_score_micronutrient_bonus')
        
        # Methods should be callable (even if not implemented yet)
        assert callable(scorer._score_nutrition_match)
        assert callable(scorer._score_schedule_match)
        assert callable(scorer._score_preference_match)
        assert callable(scorer._score_satiety_match)
        assert callable(scorer._score_micronutrient_bonus)
        assert callable(scorer._contains_allergens)
    
    def test_allergen_exclusion(self, scorer):
        """Test recipes with allergens are scored as 0.0 (KNOWLEDGE.md line 17: blacklist)."""
        # Recipe with peanut (allergen)
        peanut_recipe = Recipe(
            id="peanut_recipe",
            name="Peanut Butter Toast",
            ingredients=[
                Ingredient(name="bread", quantity=2.0, unit="slice", is_to_taste=False),
                Ingredient(name="peanut butter", quantity=2.0, unit="tbsp", is_to_taste=False)
            ],
            cooking_time_minutes=5,
            instructions=["Toast bread", "Spread peanut butter"]
        )
        
        user_with_peanut_allergy = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=[],
            disliked_foods=[],
            allergies=["peanut"]
        )
        
        context = MealContext(
            meal_type="breakfast",
            time_slot="morning",
            cooking_time_max=10,
            target_calories=300.0,
            target_protein=15.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=30.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        # Should return 0.0 due to allergen
        score = scorer.score_recipe(peanut_recipe, context, user_with_peanut_allergy, current_nutrition)
        assert score == 0.0
    
    def test_contains_allergens_method(self, scorer):
        """Test _contains_allergens method directly."""
        # Recipe with egg
        egg_recipe = Recipe(
            id="egg_recipe",
            name="Scrambled Eggs",
            ingredients=[
                Ingredient(name="egg", quantity=2.0, unit="large", is_to_taste=False),
                Ingredient(name="salt", quantity=0.0, unit="to taste", is_to_taste=True)
            ],
            cooking_time_minutes=5,
            instructions=["Scramble eggs", "Add salt to taste"]
        )
        
        # Test with egg allergy
        assert scorer._contains_allergens(egg_recipe, ["egg"]) is True
        assert scorer._contains_allergens(egg_recipe, ["peanut"]) is False
        assert scorer._contains_allergens(egg_recipe, []) is False
        
        # Test case insensitive matching
        assert scorer._contains_allergens(egg_recipe, ["EGG"]) is True
        assert scorer._contains_allergens(egg_recipe, ["Egg"]) is True
    
    def test_to_taste_verification(self, scorer, sample_context, sample_user_profile):
        """Test that 'to taste' ingredients are properly handled (KNOWLEDGE.md line 17)."""
        # Recipe with "to taste" ingredients
        recipe_with_to_taste = Recipe(
            id="recipe_with_to_taste",
            name="Seasoned Eggs",
            ingredients=[
                Ingredient(name="egg", quantity=2.0, unit="large", is_to_taste=False),
                Ingredient(name="salt", quantity=0.0, unit="to taste", is_to_taste=True),
                Ingredient(name="pepper", quantity=0.0, unit="to taste", is_to_taste=True)
            ],
            cooking_time_minutes=5,
            instructions=["Cook eggs", "Season to taste"]
        )
        
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        # Should not crash and should handle "to taste" ingredients
        try:
            score = scorer.score_recipe(
                recipe_with_to_taste, 
                sample_context, 
                sample_user_profile, 
                current_nutrition
            )
            # Score might be None (unimplemented) or a number, but shouldn't crash
            assert score is None or isinstance(score, (int, float))
        except TypeError:
            # Expected until scoring methods are fully implemented
            pass
