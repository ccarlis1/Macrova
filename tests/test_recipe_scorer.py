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
                weights.micronutrient_weight + weights.balance_weight)
        assert abs(total - 1.0) < 0.001
    
    def test_custom_weights_validation(self):
        """Test custom weights are validated."""
        # Valid weights (must sum to 1.0 including balance_weight)
        weights = ScoringWeights(
            nutrition_weight=0.4,
            schedule_weight=0.2,
            preference_weight=0.2,
            satiety_weight=0.05,
            micronutrient_weight=0.05,
            balance_weight=0.1
        )
        assert weights.nutrition_weight == 0.4
        
        # Invalid weights (don't sum to 1.0)
        with pytest.raises(ValueError, match="must sum to 1.0"):
            ScoringWeights(
                nutrition_weight=0.5,
                schedule_weight=0.5,
                preference_weight=0.5,
                satiety_weight=0.5,
                micronutrient_weight=0.5,
                balance_weight=0.5
            )
    
    def test_negative_weights_validation(self):
        """Test negative weights are rejected."""
        with pytest.raises(ValueError, match="must be non-negative"):
            ScoringWeights(
                nutrition_weight=-0.1,
                schedule_weight=0.5,
                preference_weight=0.3,
                satiety_weight=0.2,
                micronutrient_weight=0.1,
                balance_weight=0.0
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
            nutrition_weight=0.4,
            schedule_weight=0.2,
            preference_weight=0.2,
            satiety_weight=0.05,
            micronutrient_weight=0.05,
            balance_weight=0.1
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
        assert hasattr(scorer, '_score_balance_match')
        
        # Methods should be callable (even if not implemented yet)
        assert callable(scorer._score_nutrition_match)
        assert callable(scorer._score_schedule_match)
        assert callable(scorer._score_preference_match)
        assert callable(scorer._score_satiety_match)
        assert callable(scorer._score_micronutrient_bonus)
        assert callable(scorer._score_balance_match)
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


class TestNutritionScoring:
    """Test nutrition scoring functions."""
    
    @pytest.fixture
    def scorer(self):
        """Create a RecipeScorer instance."""
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        nutrition_calculator = NutritionCalculator(nutrition_db)
        return RecipeScorer(nutrition_calculator)
    
    def test_score_calories_perfect_match(self, scorer):
        """Test calories scoring with perfect match."""
        score = scorer._score_calories(actual=400.0, target=400.0)
        assert score == 100.0
    
    def test_score_calories_within_tolerance(self, scorer):
        """Test calories scoring within 10% tolerance."""
        # 5% deviation
        score = scorer._score_calories(actual=420.0, target=400.0)
        assert score == 100.0
        
        # 10% deviation (boundary)
        score = scorer._score_calories(actual=440.0, target=400.0)
        assert score == 100.0
    
    def test_score_calories_moderate_deviation(self, scorer):
        """Test calories scoring with moderate deviation."""
        # 20% deviation
        score = scorer._score_calories(actual=480.0, target=400.0)
        assert 70.0 <= score < 100.0
        
        # 40% deviation
        score = scorer._score_calories(actual=560.0, target=400.0)
        assert 30.0 <= score < 70.0
    
    def test_score_calories_large_deviation(self, scorer):
        """Test calories scoring with large deviation."""
        # 60% deviation
        score = scorer._score_calories(actual=640.0, target=400.0)
        assert 0.0 <= score < 30.0
        
        # 100% deviation
        score = scorer._score_calories(actual=800.0, target=400.0)
        assert score >= 0.0
    
    def test_score_calories_zero_target(self, scorer):
        """Test calories scoring with zero target."""
        score = scorer._score_calories(actual=400.0, target=0.0)
        assert score == 50.0  # Neutral score
    
    def test_score_protein_standard(self, scorer):
        """Test protein scoring for standard time slot."""
        # Perfect match
        score = scorer._score_protein(actual=30.0, target=30.0, time_slot="morning")
        assert score == 100.0
        
        # Within 15% tolerance
        score = scorer._score_protein(actual=32.0, target=30.0, time_slot="morning")
        assert score == 100.0
    
    def test_score_protein_pre_workout(self, scorer):
        """Test protein scoring for pre-workout (lower protein acceptable)."""
        # Pre-workout: target is reduced by 20% (30g -> 24g)
        # Actual 24g should score well
        score = scorer._score_protein(actual=24.0, target=30.0, time_slot="pre_workout")
        assert score >= 80.0  # Should score well at adjusted target
        
        # High protein (35g) should score lower for pre-workout
        score_high = scorer._score_protein(actual=35.0, target=30.0, time_slot="pre_workout")
        score_standard = scorer._score_protein(actual=35.0, target=30.0, time_slot="morning")
        # Pre-workout should score lower for high protein
        assert score_high <= score_standard
    
    def test_score_protein_post_workout(self, scorer):
        """Test protein scoring for post-workout (higher protein preferred)."""
        # Post-workout: target is increased by 20% (30g -> 36g)
        # Actual 36g should score well
        score = scorer._score_protein(actual=36.0, target=30.0, time_slot="post_workout")
        assert score >= 80.0  # Should score well at adjusted target
        
        # High protein (40g) should score better for post-workout
        score_post = scorer._score_protein(actual=40.0, target=30.0, time_slot="post_workout")
        score_standard = scorer._score_protein(actual=40.0, target=30.0, time_slot="morning")
        # Post-workout should score better for high protein
        assert score_post >= score_standard
    
    def test_score_fat_within_range(self, scorer):
        """Test fat scoring within min-max range (KNOWLEDGE.md: 50-100g range)."""
        # Perfect: within range
        score = scorer._score_fat(actual=20.0, target_min=15.0, target_max=25.0)
        assert score == 100.0
        
        # At minimum boundary
        score = scorer._score_fat(actual=15.0, target_min=15.0, target_max=25.0)
        assert score == 100.0
        
        # At maximum boundary
        score = scorer._score_fat(actual=25.0, target_min=15.0, target_max=25.0)
        assert score == 100.0
    
    def test_score_fat_below_range(self, scorer):
        """Test fat scoring below minimum."""
        # 5g below minimum (15g target, 10g actual)
        score = scorer._score_fat(actual=10.0, target_min=15.0, target_max=25.0)
        assert 0.0 <= score < 100.0
        
        # Way below minimum
        score = scorer._score_fat(actual=5.0, target_min=15.0, target_max=25.0)
        assert score < 50.0
    
    def test_score_fat_above_range(self, scorer):
        """Test fat scoring above maximum."""
        # 5g above maximum (25g target, 30g actual)
        score = scorer._score_fat(actual=30.0, target_min=15.0, target_max=25.0)
        assert 0.0 <= score < 100.0
        
        # Way above maximum
        score = scorer._score_fat(actual=40.0, target_min=15.0, target_max=25.0)
        assert score < 50.0
    
    def test_score_fat_invalid_range_swapped(self, scorer):
        """Test fat scoring with invalid range (target_min > target_max) - should auto-correct."""
        # Invalid range: min > max (should be auto-corrected by swapping)
        # If actual=20.0 is within the corrected range (15-25), it should score 100
        score_invalid = scorer._score_fat(actual=20.0, target_min=25.0, target_max=15.0)
        
        # Should handle gracefully by swapping values internally
        assert 0.0 <= score_invalid <= 100.0
        
        # Verify it gives same result as correct range
        score_correct = scorer._score_fat(actual=20.0, target_min=15.0, target_max=25.0)
        assert abs(score_invalid - score_correct) < 0.01  # Should be identical
    
    def test_score_fat_invalid_range_at_boundary(self, scorer):
        """Test fat scoring with invalid range at boundaries."""
        # Invalid range with actual at what should be minimum
        score = scorer._score_fat(actual=15.0, target_min=25.0, target_max=15.0)
        # After swap: min=15, max=25, actual=15 (at minimum) should score 100
        assert score == 100.0
        
        # Invalid range with actual at what should be maximum
        score = scorer._score_fat(actual=25.0, target_min=25.0, target_max=15.0)
        # After swap: min=15, max=25, actual=25 (at maximum) should score 100
        assert score == 100.0
    
    def test_score_fat_invalid_range_below_corrected_min(self, scorer):
        """Test fat scoring with invalid range when actual is below corrected minimum."""
        # Invalid range: min=25, max=15, actual=10
        # After swap: min=15, max=25, actual=10 (below min) should penalize
        score = scorer._score_fat(actual=10.0, target_min=25.0, target_max=15.0)
        
        # Should score lower than if within range
        score_within = scorer._score_fat(actual=20.0, target_min=25.0, target_max=15.0)
        assert score < score_within
        assert score < 100.0
    
    def test_score_fat_invalid_range_above_corrected_max(self, scorer):
        """Test fat scoring with invalid range when actual is above corrected maximum."""
        # Invalid range: min=25, max=15, actual=30
        # After swap: min=15, max=25, actual=30 (above max) should penalize
        score = scorer._score_fat(actual=30.0, target_min=25.0, target_max=15.0)
        
        # Should score lower than if within range
        score_within = scorer._score_fat(actual=20.0, target_min=25.0, target_max=15.0)
        assert score < score_within
        assert score < 100.0
    
    def test_score_carbs_pre_workout_fast_digesting(self, scorer):
        """Test carbs scoring for pre-workout with fast digesting (KNOWLEDGE.md: '2 Bananas')."""
        # Pre-workout: fast digesting should get bonus
        score_fast = scorer._score_carbs(
            actual=50.0, target=50.0, 
            time_slot="pre_workout", carb_timing="fast_digesting"
        )
        score_slow = scorer._score_carbs(
            actual=50.0, target=50.0,
            time_slot="pre_workout", carb_timing="slow_digesting"
        )
        assert score_fast > score_slow
    
    def test_score_carbs_post_workout_recovery(self, scorer):
        """Test carbs scoring for post-workout recovery (KNOWLEDGE.md: 'Hot Honey Salmon')."""
        # Post-workout: at or above target should get slight bonus
        score_at_target = scorer._score_carbs(
            actual=74.0, target=74.0,
            time_slot="post_workout", carb_timing="recovery"
        )
        score_above_target = scorer._score_carbs(
            actual=80.0, target=74.0,
            time_slot="post_workout", carb_timing="recovery"
        )
        score_below_target = scorer._score_carbs(
            actual=60.0, target=74.0,
            time_slot="post_workout", carb_timing="recovery"
        )
        
        # Above target should score at least as well as at target
        assert score_above_target >= score_at_target
        # Below target should score lower
        assert score_below_target <= score_at_target
    
    def test_score_carbs_sedentary_high_carbs(self, scorer):
        """Test carbs scoring for sedentary (score lower for high carbs, but don't eliminate)."""
        # Sedentary: high carbs (>30% over target) should be penalized
        score_high = scorer._score_carbs(
            actual=65.0, target=50.0,  # 30% over
            time_slot="sedentary", carb_timing="maintenance"
        )
        score_normal = scorer._score_carbs(
            actual=50.0, target=50.0,
            time_slot="sedentary", carb_timing="maintenance"
        )
        
        # High carbs should score lower but not zero
        assert score_high < score_normal
        assert score_high > 0.0  # Don't eliminate
    
    def test_score_nutrition_match_complete(self, scorer):
        """Test complete nutrition match scoring."""
        recipe_nutrition = NutritionProfile(
            calories=400.0,
            protein_g=30.0,
            fat_g=20.0,
            carbs_g=30.0
        )
        
        context = MealContext(
            meal_type="breakfast",
            time_slot="morning",
            cooking_time_max=15,
            target_calories=400.0,
            target_protein=30.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=30.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_nutrition_match(recipe_nutrition, context)
        
        # Should be a valid score between 0-100
        assert 0.0 <= score <= 100.0
        # Perfect match should score high
        assert score >= 80.0
    
    def test_score_nutrition_match_workout_timing(self, scorer):
        """Test nutrition match with workout timing adjustments."""
        recipe_nutrition = NutritionProfile(
            calories=200.0,
            protein_g=2.0,
            fat_g=1.0,
            carbs_g=50.0
        )
        
        # Pre-workout context (like "2 Bananas" example)
        pre_context = MealContext(
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
        
        score = scorer._score_nutrition_match(recipe_nutrition, pre_context)
        assert 0.0 <= score <= 100.0


class TestScheduleScoring:
    """Test schedule scoring functions."""
    
    @pytest.fixture
    def scorer(self):
        """Create a RecipeScorer instance."""
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        nutrition_calculator = NutritionCalculator(nutrition_db)
        return RecipeScorer(nutrition_calculator)
    
    def test_score_schedule_perfect_match(self, scorer):
        """Test schedule scoring with perfect match (within time limit)."""
        recipe = Recipe(
            id="quick_recipe",
            name="Quick Meal",
            ingredients=[],
            cooking_time_minutes=10,
            instructions=[]
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=15,  # Busyness level 2 (≤15 min)
            target_calories=400.0,
            target_protein=25.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_schedule_match(recipe, context)
        assert score == 100.0  # Perfect match
    
    def test_score_schedule_at_limit(self, scorer):
        """Test schedule scoring at exact time limit."""
        recipe = Recipe(
            id="at_limit",
            name="At Limit",
            ingredients=[],
            cooking_time_minutes=15,
            instructions=[]
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=15,
            target_calories=400.0,
            target_protein=25.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_schedule_match(recipe, context)
        assert score == 100.0  # At limit is still perfect
    
    def test_score_schedule_slight_overage(self, scorer):
        """Test schedule scoring with slight overage (small penalty)."""
        recipe = Recipe(
            id="slight_over",
            name="Slightly Over",
            ingredients=[],
            cooking_time_minutes=18,  # 20% over 15 min limit
            instructions=[]
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=15,
            target_calories=400.0,
            target_protein=25.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_schedule_match(recipe, context)
        # Should be between 80-100 (small penalty)
        assert 80.0 <= score < 100.0
    
    def test_score_schedule_moderate_overage(self, scorer):
        """Test schedule scoring with moderate overage (moderate penalty)."""
        recipe = Recipe(
            id="moderate_over",
            name="Moderately Over",
            ingredients=[],
            cooking_time_minutes=22,  # ~47% over 15 min limit
            instructions=[]
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=15,
            target_calories=400.0,
            target_protein=25.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_schedule_match(recipe, context)
        # Should be between 30-80 (moderate penalty)
        assert 30.0 <= score < 80.0
    
    def test_score_schedule_large_overage(self, scorer):
        """Test schedule scoring with large overage (large penalty)."""
        recipe = Recipe(
            id="large_over",
            name="Large Over",
            ingredients=[],
            cooking_time_minutes=25,  # ~67% over 15 min limit
            instructions=[]
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=15,
            target_calories=400.0,
            target_protein=25.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_schedule_match(recipe, context)
        # Should be between 0-50 (large penalty for 67% overage)
        assert 0.0 <= score < 50.0
        # Should be significantly penalized
        assert score < 50.0
    
    def test_score_schedule_hard_fail(self, scorer):
        """Test schedule scoring with hard fail (>100% overage)."""
        recipe = Recipe(
            id="way_over",
            name="Way Over",
            ingredients=[],
            cooking_time_minutes=35,  # >100% over 15 min limit (133% over)
            instructions=[]
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=15,
            target_calories=400.0,
            target_protein=25.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_schedule_match(recipe, context)
        assert score == 0.0  # Hard fail
    
    def test_score_schedule_busyness_level_2(self, scorer):
        """Test schedule scoring for busyness level 2 (≤15 minutes)."""
        # Recipe within limit
        recipe_ok = Recipe(
            id="quick",
            name="Quick",
            ingredients=[],
            cooking_time_minutes=12,
            instructions=[]
        )
        
        # Recipe over limit
        recipe_over = Recipe(
            id="slow",
            name="Slow",
            ingredients=[],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=15,  # Busyness level 2
            target_calories=400.0,
            target_protein=25.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score_ok = scorer._score_schedule_match(recipe_ok, context)
        score_over = scorer._score_schedule_match(recipe_over, context)
        
        assert score_ok == 100.0
        assert score_over < 100.0
    
    def test_score_schedule_busyness_level_3(self, scorer):
        """Test schedule scoring for busyness level 3 (≤30 minutes)."""
        recipe = Recipe(
            id="weeknight",
            name="Weeknight Meal",
            ingredients=[],
            cooking_time_minutes=25,
            instructions=[]
        )
        
        context = MealContext(
            meal_type="dinner",
            time_slot="evening",
            cooking_time_max=30,  # Busyness level 3
            target_calories=600.0,
            target_protein=40.0,
            target_fat_min=20.0,
            target_fat_max=30.0,
            target_carbs=50.0,
            satiety_requirement="high",
            carb_timing_preference="slow_digesting"
        )
        
        score = scorer._score_schedule_match(recipe, context)
        assert score == 100.0  # Within 30 min limit
    
    def test_score_schedule_busyness_level_4(self, scorer):
        """Test schedule scoring for busyness level 4 (30+ minutes)."""
        recipe = Recipe(
            id="weekend",
            name="Weekend Meal",
            ingredients=[],
            cooking_time_minutes=45,
            instructions=[]
        )
        
        context = MealContext(
            meal_type="dinner",
            time_slot="evening",
            cooking_time_max=60,  # Busyness level 4 (flexible)
            target_calories=700.0,
            target_protein=50.0,
            target_fat_min=25.0,
            target_fat_max=35.0,
            target_carbs=60.0,
            satiety_requirement="high",
            carb_timing_preference="slow_digesting"
        )
        
        score = scorer._score_schedule_match(recipe, context)
        assert score == 100.0  # Within 60 min limit
    
    def test_score_schedule_zero_time_recipe(self, scorer):
        """Test schedule scoring with zero cooking time recipe."""
        recipe = Recipe(
            id="instant",
            name="Instant",
            ingredients=[],
            cooking_time_minutes=0,
            instructions=[]
        )
        
        context = MealContext(
            meal_type="snack",
            time_slot="morning",
            cooking_time_max=5,
            target_calories=200.0,
            target_protein=10.0,
            target_fat_min=5.0,
            target_fat_max=10.0,
            target_carbs=20.0,
            satiety_requirement="low",
            carb_timing_preference="fast_digesting"
        )
        
        score = scorer._score_schedule_match(recipe, context)
        assert score == 100.0  # Zero time is always within limit
    
    def test_score_schedule_exact_double_time(self, scorer):
        """Test schedule scoring at exactly double the time (100% overage)."""
        recipe = Recipe(
            id="double",
            name="Double Time",
            ingredients=[],
            cooking_time_minutes=30,  # Exactly double 15 min (100% overage)
            instructions=[]
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=15,
            target_calories=400.0,
            target_protein=25.0,
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_schedule_match(recipe, context)
        # At exactly 100% overage, should be at end of 50-100% range (score = 20.0)
        assert 15.0 <= score <= 25.0  # Around 20.0 at boundary


class TestPreferenceScoring:
    """Test preference scoring functions."""
    
    @pytest.fixture
    def scorer(self):
        """Create a RecipeScorer instance."""
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        nutrition_calculator = NutritionCalculator(nutrition_db)
        return RecipeScorer(nutrition_calculator)
    
    def test_score_preference_neutral(self, scorer):
        """Test preference scoring with no matches (neutral score)."""
        recipe = Recipe(
            id="neutral",
            name="Neutral Recipe",
            ingredients=[
                Ingredient(name="chicken", quantity=200.0, unit="g", is_to_taste=False),
                Ingredient(name="rice", quantity=100.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["salmon", "avocado"],
            disliked_foods=["mushroom", "broccoli"],
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        assert score == 50.0  # Neutral score (no matches)
    
    def test_score_preference_liked_food(self, scorer):
        """Test preference scoring with liked food (boost)."""
        recipe = Recipe(
            id="liked",
            name="Liked Recipe",
            ingredients=[
                Ingredient(name="salmon", quantity=200.0, unit="g", is_to_taste=False),
                Ingredient(name="rice", quantity=100.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["salmon", "avocado"],
            disliked_foods=["mushroom"],
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        assert score == 55.0  # Base 50 + 5 for liked salmon
    
    def test_score_preference_multiple_liked_foods(self, scorer):
        """Test preference scoring with multiple liked foods (boost capped)."""
        recipe = Recipe(
            id="multiple_liked",
            name="Multiple Liked",
            ingredients=[
                Ingredient(name="salmon", quantity=200.0, unit="g", is_to_taste=False),
                Ingredient(name="avocado", quantity=50.0, unit="g", is_to_taste=False),
                Ingredient(name="rice", quantity=100.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["salmon", "avocado"],
            disliked_foods=[],
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        assert score == 60.0  # Base 50 + 10 for 2 liked foods (5 each)
    
    def test_score_preference_disliked_food(self, scorer):
        """Test preference scoring with disliked food (hard penalty)."""
        recipe = Recipe(
            id="disliked",
            name="Disliked Recipe",
            ingredients=[
                Ingredient(name="mushroom", quantity=100.0, unit="g", is_to_taste=False),
                Ingredient(name="rice", quantity=100.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["salmon"],
            disliked_foods=["mushroom", "broccoli"],
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        assert score == 20.0  # Base 50 - 30 for disliked mushroom
    
    def test_score_preference_multiple_disliked_foods(self, scorer):
        """Test preference scoring with multiple disliked foods (penalty capped)."""
        recipe = Recipe(
            id="multiple_disliked",
            name="Multiple Disliked",
            ingredients=[
                Ingredient(name="mushroom", quantity=100.0, unit="g", is_to_taste=False),
                Ingredient(name="broccoli", quantity=100.0, unit="g", is_to_taste=False),
                Ingredient(name="rice", quantity=100.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=[],
            disliked_foods=["mushroom", "broccoli"],
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        assert score == 0.0  # Base 50 - 60 (capped at 50, so 0)
    
    def test_score_preference_mixed_liked_disliked(self, scorer):
        """Test preference scoring with both liked and disliked foods."""
        recipe = Recipe(
            id="mixed",
            name="Mixed Recipe",
            ingredients=[
                Ingredient(name="salmon", quantity=200.0, unit="g", is_to_taste=False),
                Ingredient(name="mushroom", quantity=50.0, unit="g", is_to_taste=False),
                Ingredient(name="rice", quantity=100.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["salmon"],
            disliked_foods=["mushroom"],
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        # Base 50 + 5 (liked) - 30 (disliked) = 25
        assert score == 25.0
    
    def test_score_preference_case_insensitive(self, scorer):
        """Test preference scoring is case insensitive."""
        recipe = Recipe(
            id="case",
            name="Case Test",
            ingredients=[
                Ingredient(name="SALMON", quantity=200.0, unit="g", is_to_taste=False),
                Ingredient(name="Mushroom", quantity=50.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["salmon"],  # lowercase
            disliked_foods=["MUSHROOM"],  # uppercase
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        # Should match despite case differences
        assert score == 25.0  # Base 50 + 5 (liked) - 30 (disliked)
    
    def test_score_preference_substring_matching(self, scorer):
        """Test preference scoring with substring matching."""
        recipe = Recipe(
            id="substring",
            name="Substring Test",
            ingredients=[
                Ingredient(name="salmon fillet", quantity=200.0, unit="g", is_to_taste=False),
                Ingredient(name="mushroom soup", quantity=100.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["salmon"],  # Should match "salmon fillet"
            disliked_foods=["mushroom"],  # Should match "mushroom soup"
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        # Should match substrings
        assert score == 25.0  # Base 50 + 5 (liked) - 30 (disliked)
    
    def test_score_preference_empty_lists(self, scorer):
        """Test preference scoring with empty preference lists."""
        recipe = Recipe(
            id="empty",
            name="Empty Preferences",
            ingredients=[
                Ingredient(name="chicken", quantity=200.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=[],  # Empty
            disliked_foods=[],  # Empty
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        assert score == 50.0  # Neutral score
    
    def test_score_preference_to_taste_ingredients(self, scorer):
        """Test preference scoring ignores 'to taste' ingredients."""
        recipe = Recipe(
            id="to_taste",
            name="To Taste Test",
            ingredients=[
                Ingredient(name="chicken", quantity=200.0, unit="g", is_to_taste=False),
                Ingredient(name="salt", quantity=0.0, unit="to taste", is_to_taste=True),
                Ingredient(name="pepper", quantity=0.0, unit="to taste", is_to_taste=True)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        # User dislikes salt and pepper, but they're "to taste"
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=[],
            disliked_foods=["salt", "pepper"],  # Disliked but "to taste"
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        # "To taste" ingredients should still be checked for preferences
        # (they're displayed in recipe, so preferences matter)
        # But they shouldn't break the recipe
        assert 0.0 <= score <= 100.0  # Should handle gracefully
    
    def test_score_preference_boost_cap(self, scorer):
        """Test preference scoring boost is capped at +15."""
        recipe = Recipe(
            id="boost_cap",
            name="Boost Cap Test",
            ingredients=[
                Ingredient(name="salmon", quantity=200.0, unit="g", is_to_taste=False),
                Ingredient(name="avocado", quantity=50.0, unit="g", is_to_taste=False),
                Ingredient(name="egg", quantity=2.0, unit="large", is_to_taste=False),
                Ingredient(name="chicken", quantity=100.0, unit="g", is_to_taste=False),
                Ingredient(name="beef", quantity=100.0, unit="g", is_to_taste=False)
            ],
            cooking_time_minutes=20,
            instructions=[]
        )
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["salmon", "avocado", "egg", "chicken", "beef"],  # 5 liked foods
            disliked_foods=[],
            allergies=[]
        )
        
        score = scorer._score_preference_match(recipe, user_profile)
        # Should be capped at +15 (max boost)
        assert score == 65.0  # Base 50 + 15 (capped, not 25)


class TestSatietyScoring:
    """Test satiety scoring functions."""
    
    @pytest.fixture
    def scorer(self):
        """Create a RecipeScorer instance."""
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        nutrition_calculator = NutritionCalculator(nutrition_db)
        return RecipeScorer(nutrition_calculator)
    
    def test_score_satiety_high_ideal(self, scorer):
        """Test high satiety scoring with ideal meal (KNOWLEDGE.md: 12 hour fast)."""
        # High satiety meal: high protein, high fat, high calories
        nutrition = NutritionProfile(
            calories=750.0,  # High calories (bigger meal)
            protein_g=50.0,   # High protein
            fat_g=25.0,       # High fat
            carbs_g=60.0
        )
        
        context = MealContext(
            meal_type="dinner",
            time_slot="evening",
            cooking_time_max=30,
            target_calories=700.0,
            target_protein=45.0,
            target_fat_min=20.0,
            target_fat_max=30.0,
            target_carbs=50.0,
            satiety_requirement="high",  # Long fast ahead
            carb_timing_preference="slow_digesting"
        )
        
        score = scorer._score_satiety_match(nutrition, context)
        # Should score high (80-100) for ideal high satiety meal
        assert score >= 80.0
    
    def test_score_satiety_high_low_protein(self, scorer):
        """Test high satiety scoring with low protein (should score lower)."""
        # Low protein meal (less satiating)
        nutrition = NutritionProfile(
            calories=600.0,
            protein_g=15.0,  # Low protein
            fat_g=20.0,
            carbs_g=70.0
        )
        
        context = MealContext(
            meal_type="dinner",
            time_slot="evening",
            cooking_time_max=30,
            target_calories=600.0,
            target_protein=40.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=50.0,
            satiety_requirement="high",
            carb_timing_preference="slow_digesting"
        )
        
        score = scorer._score_satiety_match(nutrition, context)
        # Should score lower than ideal high satiety meal
        assert score < 70.0
    
    def test_score_satiety_high_small_meal(self, scorer):
        """Test high satiety scoring with small meal (should score lower)."""
        # Small meal (less satiating for long fast)
        nutrition = NutritionProfile(
            calories=300.0,  # Small meal
            protein_g=25.0,
            fat_g=15.0,
            carbs_g=20.0
        )
        
        context = MealContext(
            meal_type="dinner",
            time_slot="evening",
            cooking_time_max=30,
            target_calories=600.0,
            target_protein=40.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=50.0,
            satiety_requirement="high",
            carb_timing_preference="slow_digesting"
        )
        
        score = scorer._score_satiety_match(nutrition, context)
        # Should score lower (small meal not ideal for long fast)
        assert score <= 60.0  # Small meals score lower for high satiety
    
    def test_score_satiety_low_ideal(self, scorer):
        """Test low satiety scoring with ideal light meal (frequent meals)."""
        # Light meal for frequent eating
        nutrition = NutritionProfile(
            calories=300.0,  # Light calories
            protein_g=20.0,   # Moderate protein
            fat_g=10.0,      # Low fat
            carbs_g=30.0
        )
        
        context = MealContext(
            meal_type="snack",
            time_slot="morning",
            cooking_time_max=5,
            target_calories=250.0,
            target_protein=15.0,
            target_fat_min=5.0,
            target_fat_max=10.0,
            target_carbs=25.0,
            satiety_requirement="low",  # Frequent meals
            carb_timing_preference="fast_digesting"
        )
        
        score = scorer._score_satiety_match(nutrition, context)
        # Should score high (80-100) for ideal light meal
        assert score >= 70.0
    
    def test_score_satiety_low_heavy_meal(self, scorer):
        """Test low satiety scoring with heavy meal (should score lower)."""
        # Heavy meal (not ideal for frequent meals)
        nutrition = NutritionProfile(
            calories=700.0,  # Heavy meal
            protein_g=50.0,
            fat_g=30.0,
            carbs_g=50.0
        )
        
        context = MealContext(
            meal_type="snack",
            time_slot="morning",
            cooking_time_max=5,
            target_calories=300.0,
            target_protein=20.0,
            target_fat_min=5.0,
            target_fat_max=15.0,
            target_carbs=30.0,
            satiety_requirement="low",
            carb_timing_preference="fast_digesting"
        )
        
        score = scorer._score_satiety_match(nutrition, context)
        # Should score lower (too heavy for frequent meals)
        assert score < 50.0
    
    def test_score_satiety_medium_balanced(self, scorer):
        """Test medium satiety scoring with balanced meal."""
        # Balanced meal
        nutrition = NutritionProfile(
            calories=500.0,  # Moderate calories
            protein_g=30.0,  # Moderate protein
            fat_g=20.0,     # Moderate fat
            carbs_g=40.0
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=20,
            target_calories=500.0,
            target_protein=30.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_satiety_match(nutrition, context)
        # Should score well for balanced meal
        assert score >= 70.0
    
    def test_score_satiety_medium_unbalanced(self, scorer):
        """Test medium satiety scoring with unbalanced meal."""
        # Unbalanced meal (too extreme)
        nutrition = NutritionProfile(
            calories=800.0,  # Too high
            protein_g=60.0,  # Too high
            fat_g=40.0,      # Too high
            carbs_g=20.0
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=20,
            target_calories=500.0,
            target_protein=30.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=40.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_satiety_match(nutrition, context)
        # Should score lower (too extreme for medium satiety)
        assert score < 60.0
    
    def test_score_satiety_high_vs_low_comparison(self, scorer):
        """Test that high satiety favors different meals than low satiety."""
        # Same nutrition profile
        nutrition = NutritionProfile(
            calories=500.0,
            protein_g=30.0,
            fat_g=20.0,
            carbs_g=40.0
        )
        
        context_high = MealContext(
            meal_type="dinner",
            time_slot="evening",
            cooking_time_max=30,
            target_calories=600.0,
            target_protein=40.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=50.0,
            satiety_requirement="high",
            carb_timing_preference="slow_digesting"
        )
        
        context_low = MealContext(
            meal_type="snack",
            time_slot="morning",
            cooking_time_max=5,
            target_calories=300.0,
            target_protein=15.0,
            target_fat_min=5.0,
            target_fat_max=10.0,
            target_carbs=30.0,
            satiety_requirement="low",
            carb_timing_preference="fast_digesting"
        )
        
        score_high = scorer._score_satiety_match(nutrition, context_high)
        score_low = scorer._score_satiety_match(nutrition, context_low)
        
        # Same meal should score differently based on satiety requirement
        # This meal is moderate, so scores might be similar, but logic should differ
        assert 0.0 <= score_high <= 100.0
        assert 0.0 <= score_low <= 100.0
    
    def test_score_satiety_high_excellent_meal(self, scorer):
        """Test high satiety with excellent meal (REASONING_LOGIC.md example)."""
        # Excellent high satiety meal (like "Hot Honey Salmon" example)
        nutrition = NutritionProfile(
            calories=738.0,  # High calories (bigger meal)
            protein_g=62.0,  # High protein
            fat_g=19.0,      # Moderate-high fat
            carbs_g=74.0
        )
        
        context = MealContext(
            meal_type="dinner",
            time_slot="post_workout",
            cooking_time_max=30,
            target_calories=700.0,
            target_protein=60.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=70.0,
            satiety_requirement="high",  # Long fast ahead
            carb_timing_preference="recovery"
        )
        
        score = scorer._score_satiety_match(nutrition, context)
        # Should score very high (excellent for high satiety)
        assert score >= 85.0
    
    def test_score_satiety_low_snack_meal(self, scorer):
        """Test low satiety with ideal snack (KNOWLEDGE.md: frequent meals)."""
        # Ideal snack for frequent meals
        nutrition = NutritionProfile(
            calories=208.0,  # Light calories (like "2 Bananas" example)
            protein_g=2.0,   # Low protein
            fat_g=1.0,       # Low fat
            carbs_g=50.0
        )
        
        context = MealContext(
            meal_type="snack",
            time_slot="pre_workout",
            cooking_time_max=5,
            target_calories=200.0,
            target_protein=2.0,
            target_fat_min=0.5,
            target_fat_max=2.0,
            target_carbs=50.0,
            satiety_requirement="low",  # Frequent meals
            carb_timing_preference="fast_digesting"
        )
        
        score = scorer._score_satiety_match(nutrition, context)
        # Should score well for light snack
        assert score >= 60.0  # Light meals score well for low satiety
    
    def test_score_satiety_unknown_requirement(self, scorer):
        """Test satiety scoring with unknown requirement (defaults to medium)."""
        nutrition = NutritionProfile(
            calories=500.0,
            protein_g=30.0,
            fat_g=20.0,
            carbs_g=40.0
        )
        
        context = MealContext(
            meal_type="lunch",
            time_slot="afternoon",
            cooking_time_max=20,
            target_calories=500.0,
            target_protein=30.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=40.0,
            satiety_requirement="unknown",  # Unknown value
            carb_timing_preference="maintenance"
        )
        
        score = scorer._score_satiety_match(nutrition, context)
        # Should default to medium satiety logic
        assert 0.0 <= score <= 100.0


class TestCompleteRecipeScoring:
    """Test complete recipe scoring integration."""
    
    @pytest.fixture
    def scorer(self):
        """Create a RecipeScorer instance."""
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        nutrition_calculator = NutritionCalculator(nutrition_db)
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
            schedule={},
            liked_foods=["egg", "salmon"],
            disliked_foods=["mushroom"],
            allergies=["peanut"]
        )
    
    def test_score_recipe_complete_integration(self, scorer, sample_recipe, sample_context, sample_user_profile):
        """Test complete recipe scoring with all components."""
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        score = scorer.score_recipe(
            sample_recipe,
            sample_context,
            sample_user_profile,
            current_nutrition
        )
        
        # Should return a valid score between 0-100
        assert 0.0 <= score <= 100.0
        # Should not be 0 (unless there's a major issue)
        assert score > 0.0
    
    def test_score_recipe_allergen_exclusion(self, scorer, sample_context, sample_user_profile):
        """Test that recipes with allergens return 0.0."""
        # Recipe with peanut (allergen)
        peanut_recipe = Recipe(
            id="peanut_recipe",
            name="Peanut Recipe",
            ingredients=[
                Ingredient(name="peanut butter", quantity=2.0, unit="tbsp", is_to_taste=False)
            ],
            cooking_time_minutes=5,
            instructions=["Spread peanut butter"]
        )
        
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        score = scorer.score_recipe(
            peanut_recipe,
            sample_context,
            sample_user_profile,
            current_nutrition
        )
        
        assert score == 0.0  # Should be excluded
    
    def test_score_recipe_weighted_combination(self, scorer, sample_recipe, sample_context, sample_user_profile):
        """Test that weighted combination works correctly."""
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        # Get individual scores
        recipe_nutrition = scorer.nutrition_calculator.calculate_recipe_nutrition(sample_recipe)
        nutrition_score = scorer._score_nutrition_match(recipe_nutrition, sample_context)
        schedule_score = scorer._score_schedule_match(sample_recipe, sample_context)
        preference_score = scorer._score_preference_match(sample_recipe, sample_user_profile)
        satiety_score = scorer._score_satiety_match(recipe_nutrition, sample_context)
        micronutrient_score = scorer._score_micronutrient_bonus(recipe_nutrition, sample_context)
        balance_score = scorer._score_balance_match(recipe_nutrition, sample_user_profile, current_nutrition)
        
        # Calculate expected weighted score (including balance_weight)
        expected_score = (
            nutrition_score * scorer.weights.nutrition_weight +
            schedule_score * scorer.weights.schedule_weight +
            preference_score * scorer.weights.preference_weight +
            satiety_score * scorer.weights.satiety_weight +
            micronutrient_score * scorer.weights.micronutrient_weight +
            balance_score * scorer.weights.balance_weight
        )
        
        # Get actual score
        actual_score = scorer.score_recipe(
            sample_recipe,
            sample_context,
            sample_user_profile,
            current_nutrition
        )
        
        # Should match (within floating point precision)
        assert abs(actual_score - expected_score) < 0.01
    
    def test_score_recipe_custom_weights(self, scorer, sample_recipe, sample_context, sample_user_profile):
        """Test recipe scoring with custom weights."""
        # Custom weights emphasizing nutrition (must sum to 1.0 including balance_weight)
        custom_weights = ScoringWeights(
            nutrition_weight=0.5,      # 50% nutrition
            schedule_weight=0.1,        # 10% schedule
            preference_weight=0.1,      # 10% preference
            satiety_weight=0.1,         # 10% satiety
            micronutrient_weight=0.1,   # 10% micronutrient
            balance_weight=0.1          # 10% balance
        )
        
        custom_scorer = RecipeScorer(scorer.nutrition_calculator, custom_weights)
        
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        score = custom_scorer.score_recipe(
            sample_recipe,
            sample_context,
            sample_user_profile,
            current_nutrition
        )
        
        assert 0.0 <= score <= 100.0
    
    def test_score_recipe_to_taste_exclusion(self, scorer, sample_context, sample_user_profile):
        """Test that 'to taste' ingredients are excluded from nutrition calculation."""
        # Recipe with "to taste" ingredients
        recipe_with_to_taste = Recipe(
            id="to_taste_recipe",
            name="To Taste Recipe",
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
        
        score = scorer.score_recipe(
            recipe_with_to_taste,
            sample_context,
            sample_user_profile,
            current_nutrition
        )
        
        # Should score normally (not crash)
        assert 0.0 <= score <= 100.0
        
        # Verify nutrition calculation excludes "to taste"
        recipe_nutrition = scorer.nutrition_calculator.calculate_recipe_nutrition(recipe_with_to_taste)
        # Nutrition should only include eggs, not salt/pepper
        assert recipe_nutrition.calories > 0.0  # Should have calories from eggs
    
    def test_score_recipe_perfect_match(self, scorer, sample_user_profile):
        """Test recipe scoring with perfect match on all criteria."""
        # Recipe that matches all criteria perfectly
        perfect_recipe = Recipe(
            id="perfect",
            name="Perfect Recipe",
            ingredients=[
                Ingredient(name="egg", quantity=3.0, unit="large", is_to_taste=False)  # Liked food
            ],
            cooking_time_minutes=10,
            instructions=["Cook eggs"]
        )
        
        perfect_context = MealContext(
            meal_type="breakfast",
            time_slot="morning",
            cooking_time_max=15,  # Recipe fits
            target_calories=216.0,  # ~3 eggs
            target_protein=18.9,   # ~3 eggs
            target_fat_min=10.0,
            target_fat_max=20.0,
            target_carbs=5.0,
            satiety_requirement="medium",
            carb_timing_preference="maintenance",
            priority_micronutrients=[]
        )
        
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        score = scorer.score_recipe(
            perfect_recipe,
            perfect_context,
            sample_user_profile,
            current_nutrition
        )
        
        # Should score high (all criteria met)
        print(f"Perfect recipe score: {score}")
        assert score >= 70.0
    
    def test_score_recipe_poor_match(self, scorer, sample_user_profile):
        """Test recipe scoring with poor match on multiple criteria."""
        # Recipe that matches poorly
        poor_recipe = Recipe(
            id="poor",
            name="Poor Recipe",
            ingredients=[
                Ingredient(name="mushroom", quantity=200.0, unit="g", is_to_taste=False)  # Disliked food
            ],
            cooking_time_minutes=30,  # Over time limit
            instructions=["Cook mushrooms"]
        )
        
        poor_context = MealContext(
            meal_type="breakfast",
            time_slot="morning",
            cooking_time_max=10,  # Recipe takes 30 min (way over)
            target_calories=400.0,
            target_protein=30.0,
            target_fat_min=15.0,
            target_fat_max=25.0,
            target_carbs=40.0,
            satiety_requirement="high",  # But recipe is light
            carb_timing_preference="maintenance",
            priority_micronutrients=[]
        )
        
        current_nutrition = NutritionProfile(
            calories=0.0, protein_g=0.0, fat_g=0.0, carbs_g=0.0
        )
        
        score = scorer.score_recipe(
            poor_recipe,
            poor_context,
            sample_user_profile,
            current_nutrition
        )
        
        # Should score low (multiple criteria not met)
        assert score < 50.0


class TestCalorieDeficitMode:
    """Tests for Calorie Deficit Mode (hard calorie cap constraint)."""
    
    @pytest.fixture
    def scorer(self):
        """Create a RecipeScorer instance."""
        nutrition_db = NutritionDB("tests/fixtures/test_ingredients.json")
        nutrition_calculator = NutritionCalculator(nutrition_db)
        return RecipeScorer(nutrition_calculator)
    
    @pytest.fixture
    def sample_recipe(self):
        """Create a sample recipe with known calories (~216 kcal from 3 eggs)."""
        return Recipe(
            id="test_recipe",
            name="Test Recipe",
            ingredients=[
                Ingredient(name="egg", quantity=3.0, unit="large", is_to_taste=False)
            ],
            cooking_time_minutes=10,
            instructions=["Cook eggs"]
        )
    
    @pytest.fixture
    def high_calorie_recipe(self):
        """Create a high-calorie recipe (~720 kcal from 10 eggs)."""
        return Recipe(
            id="high_cal_recipe",
            name="High Calorie Recipe",
            ingredients=[
                Ingredient(name="egg", quantity=10.0, unit="large", is_to_taste=False)
            ],
            cooking_time_minutes=15,
            instructions=["Cook eggs"]
        )
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample meal context."""
        return MealContext(
            meal_type="dinner",
            time_slot="evening",
            cooking_time_max=30,
            target_calories=500.0,
            target_protein=30.0,
            target_fat_min=10.0,
            target_fat_max=25.0,
            target_carbs=50.0,
            satiety_requirement="high",
            carb_timing_preference="slow_digesting",
            priority_micronutrients=[]
        )
    
    def test_balance_score_zero_when_exceeds_max_daily_calories(self, scorer, high_calorie_recipe, sample_context):
        """Test that balance score is 0.0 when recipe would exceed max_daily_calories."""
        # User with hard calorie cap
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["egg"],
            disliked_foods=[],
            allergies=[],
            max_daily_calories=2000  # Hard cap
        )
        
        # Already consumed 1800 kcal, recipe adds ~720 kcal → projected 2520 > 2000
        current_nutrition = NutritionProfile(
            calories=1800.0, protein_g=100.0, fat_g=60.0, carbs_g=200.0
        )
        
        score = scorer.score_recipe(
            high_calorie_recipe,
            sample_context,
            user_profile,
            current_nutrition
        )
        
        # Should be 0.0 due to hard constraint violation
        assert score == 0.0
    
    def test_balance_score_nonzero_when_within_max_daily_calories(self, scorer, sample_recipe, sample_context):
        """Test that balance score is > 0.0 when recipe stays within max_daily_calories."""
        # User with hard calorie cap
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["egg"],
            disliked_foods=[],
            allergies=[],
            max_daily_calories=2000  # Hard cap
        )
        
        # Already consumed 1500 kcal, recipe adds ~216 kcal → projected 1716 < 2000
        current_nutrition = NutritionProfile(
            calories=1500.0, protein_g=80.0, fat_g=50.0, carbs_g=150.0
        )
        
        score = scorer.score_recipe(
            sample_recipe,
            sample_context,
            user_profile,
            current_nutrition
        )
        
        # Should be > 0.0 since within hard cap
        assert score > 0.0
    
    def test_balance_score_ignores_max_when_not_set(self, scorer, high_calorie_recipe, sample_context):
        """Test that when max_daily_calories is None, behavior is unchanged (soft penalty only)."""
        # User WITHOUT hard calorie cap
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["egg"],
            disliked_foods=[],
            allergies=[],
            max_daily_calories=None  # Feature disabled
        )
        
        # Already consumed 1800 kcal, recipe adds ~720 kcal → projected 2520 > 2400 target
        current_nutrition = NutritionProfile(
            calories=1800.0, protein_g=100.0, fat_g=60.0, carbs_g=200.0
        )
        
        score = scorer.score_recipe(
            high_calorie_recipe,
            sample_context,
            user_profile,
            current_nutrition
        )
        
        # Should be > 0.0 (soft penalty, not hard exclusion)
        assert score > 0.0
    
    def test_max_daily_calories_exact_boundary(self, scorer, sample_recipe, sample_context):
        """Test that recipe is allowed when projected calories exactly equal max."""
        # Recipe has ~216 kcal from 3 eggs
        recipe_nutrition = scorer.nutrition_calculator.calculate_recipe_nutrition(sample_recipe)
        recipe_calories = recipe_nutrition.calories
        
        # Set max so that current + recipe = exactly max
        max_cal = 2000
        current_cal = max_cal - recipe_calories
        
        user_profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=300.0,
            schedule={},
            liked_foods=["egg"],
            disliked_foods=[],
            allergies=[],
            max_daily_calories=max_cal
        )
        
        current_nutrition = NutritionProfile(
            calories=current_cal, protein_g=80.0, fat_g=50.0, carbs_g=150.0
        )
        
        score = scorer.score_recipe(
            sample_recipe,
            sample_context,
            user_profile,
            current_nutrition
        )
        
        # Exactly at boundary should be allowed (score > 0.0)
        assert score > 0.0
