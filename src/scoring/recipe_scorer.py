"""Recipe scoring system for meal planning."""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from src.data_layer.models import Recipe, NutritionProfile, UserProfile


@dataclass
class ScoringWeights:
    """Configurable weights for different scoring criteria."""
    nutrition_weight: float = 0.4    # 40% - calories/macros match
    schedule_weight: float = 0.2     # 20% - cooking time constraint
    preference_weight: float = 0.2   # 20% - taste preferences
    satiety_weight: float = 0.1      # 10% - satiety requirements
    micronutrient_weight: float = 0.1 # 10% - basic micronutrient bonus (MVP: simple)

    def __post_init__(self):
        """Validate weights sum to 1.0 and are non-negative."""
        # Check for negative weights
        weights = [self.nutrition_weight, self.schedule_weight, 
                   self.preference_weight, self.satiety_weight, 
                   self.micronutrient_weight]
        if any(w < 0 for w in weights):
            raise ValueError("All scoring weights must be non-negative")
        
        # Check sum
        total = sum(weights)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")


@dataclass
class MealContext:
    """Context for scoring a specific meal slot."""
    meal_type: str  # "breakfast", "lunch", "dinner", "snack"
    time_slot: str  # "morning", "pre_workout", "post_workout", "sedentary", "evening"
    cooking_time_max: int  # Maximum cooking time allowed (minutes)
    target_calories: float  # Target calories for this meal
    target_protein: float   # Target protein for this meal
    target_fat_min: float  # Minimum fat for this meal (KNOWLEDGE.md: 50-100g range)
    target_fat_max: float  # Maximum fat for this meal (KNOWLEDGE.md: 50-100g range)
    target_carbs: float    # Target carbs for this meal
    satiety_requirement: str  # "high", "medium", "low"
    carb_timing_preference: str  # "fast_digesting", "slow_digesting", "recovery", "maintenance"
    priority_micronutrients: List[str] = field(default_factory=list)  # Nutrients most needed today (weekly tracking)


class RecipeScorer:
    """Scores recipes based on nutrition goals, schedule, and preferences."""
    
    def __init__(self, 
                 nutrition_calculator,
                 weights: Optional[ScoringWeights] = None):
        """Initialize recipe scorer.
        
        Args:
            nutrition_calculator: NutritionCalculator instance
            weights: Optional custom scoring weights
        """
        self.nutrition_calculator = nutrition_calculator
        self.weights = weights or ScoringWeights()
    
    def score_recipe(self, 
                    recipe: Recipe, 
                    context: MealContext,
                    user_profile: UserProfile,
                    current_daily_nutrition: NutritionProfile) -> float:
        """Score a recipe for a specific meal context.
        
        Args:
            recipe: Recipe to score
            context: Meal context with targets and constraints
            user_profile: User preferences and goals
            current_daily_nutrition: Nutrition consumed so far today
            
        Returns:
            Score from 0.0 to 100.0 (higher is better), or 0.0 if contains allergens
        """
        # Hard exclusion for allergens - return 0 immediately (KNOWLEDGE.md line 17)
        if self._contains_allergens(recipe, user_profile.allergies):
            return 0.0
        
        # Calculate recipe nutrition (excluding "to taste" ingredients)
        recipe_nutrition = self.nutrition_calculator.calculate_recipe_nutrition(recipe)
        
        # Verify "to taste" ingredients were excluded (KNOWLEDGE.md line 17)
        to_taste_count = sum(1 for ing in recipe.ingredients if ing.is_to_taste)
        if to_taste_count > 0:
            # "to taste" ingredients should be excluded from nutrition calculation
            # This is handled by nutrition_calculator.calculate_recipe_nutrition()
            pass
        
        # Calculate individual component scores (0-100 each)
        nutrition_score = self._score_nutrition_match(recipe_nutrition, context)
        schedule_score = self._score_schedule_match(recipe, context)
        preference_score = self._score_preference_match(recipe, user_profile)
        satiety_score = self._score_satiety_match(recipe_nutrition, context)
        micronutrient_score = self._score_micronutrient_bonus(recipe_nutrition, context)
        
        # Weighted combination
        total_score = (
            nutrition_score * self.weights.nutrition_weight +
            schedule_score * self.weights.schedule_weight +
            preference_score * self.weights.preference_weight +
            satiety_score * self.weights.satiety_weight +
            micronutrient_score * self.weights.micronutrient_weight
        )
        
        return total_score
    
    def _score_nutrition_match(self, 
                              recipe_nutrition: NutritionProfile,
                              context: MealContext) -> float:
        """Score how well recipe nutrition matches meal targets (0-100).
        
        Args:
            recipe_nutrition: Calculated nutrition for recipe
            context: Meal context with target macros
            
        Returns:
            Score from 0-100 based on macro target adherence
        """
        # TODO: Implement nutrition matching logic
        # - Compare calories, protein, fat, carbs to targets
        # - Score based on closeness (closer = higher score)
        # - Penalize large deviations
        pass
        
    def _score_schedule_match(self, 
                             recipe: Recipe,
                             context: MealContext) -> float:
        """Score cooking time vs available time (0-100).
        
        Args:
            recipe: Recipe with cooking_time_minutes
            context: Meal context with cooking_time_max
            
        Returns:
            Score from 0-100 based on time constraint adherence
        """
        # TODO: Implement schedule matching logic
        # - Perfect score if cooking_time <= cooking_time_max
        # - Small penalty if slightly above
        # - Hard fail (0 score) if far above
        pass
        
    def _score_preference_match(self, 
                               recipe: Recipe,
                               user_profile: UserProfile) -> float:
        """Score recipe against user preferences (0-100).
        
        Args:
            recipe: Recipe to evaluate
            user_profile: User preferences (likes, dislikes, allergies)
            
        Returns:
            Score from 0-100 based on preference alignment
        """
        # TODO: Implement preference matching logic
        # - Hard penalty for disliked ingredients
        # - Small boost for liked ingredients
        # - Exclude entirely if contains allergens (return 0)
        pass
        
    def _score_satiety_match(self, 
                            recipe_nutrition: NutritionProfile,
                            context: MealContext) -> float:
        """Score satiety appropriateness (0-100).
        
        Args:
            recipe_nutrition: Calculated nutrition for recipe
            context: Meal context with satiety requirements
            
        Returns:
            Score from 0-100 based on satiety appropriateness
        """
        # TODO: Implement satiety matching logic
        # - High satiety: favor high protein + fat, higher calories
        # - Low satiety: favor lighter meals, more carbs
        # - Medium satiety: balanced approach
        pass
    
    def _score_micronutrient_bonus(self, 
                                  recipe_nutrition: NutritionProfile,
                                  context: MealContext) -> float:
        """Score basic micronutrient density bonus (0-100).
        
        Args:
            recipe_nutrition: Calculated nutrition for recipe
            context: Meal context with priority micronutrients
            
        Returns:
            Simple bonus score for micronutrient density (MVP: simplified)
        """
        # TODO: Implement basic micronutrient bonus
        # - MVP: Simple heuristic based on ingredient diversity
        # - Consider context.priority_micronutrients for weekly tracking
        # - Future: Actual micronutrient calculation (KNOWLEDGE.md line 12)
        pass
    
    def _contains_allergens(self, recipe: Recipe, allergies: List[str]) -> bool:
        """Check if recipe contains any allergens (KNOWLEDGE.md line 17: "blacklist").
        
        Args:
            recipe: Recipe to check
            allergies: List of allergen names to avoid
            
        Returns:
            True if recipe contains allergens, False otherwise
        """
        if not allergies:
            return False
            
        # Check all ingredients (including "to taste" ones for allergen safety)
        for ingredient in recipe.ingredients:
            ingredient_name = ingredient.name.lower()
            for allergen in allergies:
                if allergen.lower() in ingredient_name:
                    return True
        
        return False
