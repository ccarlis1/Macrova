"""Recipe scoring system for meal planning."""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from src.data_layer.models import Recipe, NutritionProfile, UserProfile


@dataclass
class ScoringWeights:
    """Configurable weights for different scoring criteria."""
    nutrition_weight: float = 0.35    # 35% - calories/macros match
    schedule_weight: float = 0.20     # 20% - cooking time constraint
    preference_weight: float = 0.15   # 15% - taste preferences
    satiety_weight: float = 0.10      # 10% - satiety requirements
    micronutrient_weight: float = 0.10 # 10% - basic micronutrient bonus (MVP: simple)
    balance_weight: float = 0.10      # 10% - complements daily nutrition

    def __post_init__(self):
        """Validate weights sum to 1.0 and are non-negative."""
        # Check for negative weights
        weights = [self.nutrition_weight, self.schedule_weight, 
                   self.preference_weight, self.satiety_weight, 
                   self.micronutrient_weight, self.balance_weight]
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
        balance_score = self._score_balance_match(recipe_nutrition, user_profile, current_daily_nutrition)
        
        # Hard exclusion for balance score of 0.0 (Calorie Deficit Mode)
        # When max_daily_calories is exceeded, balance_score returns 0.0 as hard exclusion
        if balance_score == 0.0 and user_profile.max_daily_calories is not None:
            return 0.0
        
        # Weighted combination
        total_score = (
            nutrition_score * self.weights.nutrition_weight +
            schedule_score * self.weights.schedule_weight +
            preference_score * self.weights.preference_weight +
            satiety_score * self.weights.satiety_weight +
            micronutrient_score * self.weights.micronutrient_weight +
            balance_score * self.weights.balance_weight
        )
        
        return total_score
    
    def _score_nutrition_match(self, 
                              recipe_nutrition: NutritionProfile,
                              context: MealContext) -> float:
        """Score how well recipe nutrition matches meal targets (0-100).
        
        Based on KNOWLEDGE.md nutrition principles and REASONING_LOGIC.md scoring rules.
        
        Args:
            recipe_nutrition: Calculated nutrition for recipe
            context: Meal context with target macros and timing
            
        Returns:
            Score from 0-100 based on macro target adherence
        """
        # Score each macro component (0-100 each)
        calories_score = self._score_calories(recipe_nutrition.calories, context.target_calories)
        protein_score = self._score_protein(
            recipe_nutrition.protein_g, 
            context.target_protein,
            context.time_slot
        )
        fat_score = self._score_fat(
            recipe_nutrition.fat_g,
            context.target_fat_min,
            context.target_fat_max
        )
        carbs_score = self._score_carbs(
            recipe_nutrition.carbs_g,
            context.target_carbs,
            context.time_slot,
            context.carb_timing_preference
        )
        
        # Weighted average: calories (30%), protein (30%), fat (20%), carbs (20%)
        # This prioritizes calories and protein as most important (KNOWLEDGE.md)
        total_score = (
            calories_score * 0.30 +
            protein_score * 0.30 +
            fat_score * 0.20 +
            carbs_score * 0.20
        )
        
        return total_score
    
    def _score_calories(self, actual: float, target: float) -> float:
        """Score calories match (0-100). Closer to target = higher score.
        
        Args:
            actual: Actual calories in recipe
            target: Target calories for meal
            
        Returns:
            Score from 0-100
        """
        if target == 0:
            return 50.0  # Neutral score if no target
        
        # Calculate percentage deviation
        deviation = abs(actual - target) / target
        
        # Score based on deviation (10% tolerance = 100, 50% deviation = 0)
        if deviation <= 0.10:
            # Within 10% = perfect score
            return 100.0
        elif deviation <= 0.25:
            # 10-25% deviation = linear decrease from 100 to 70
            return 100.0 - (deviation - 0.10) * (30.0 / 0.15)
        elif deviation <= 0.50:
            # 25-50% deviation = linear decrease from 70 to 30
            return 70.0 - (deviation - 0.25) * (40.0 / 0.25)
        else:
            # >50% deviation = linear decrease from 30 to 0
            score = 30.0 - (deviation - 0.50) * (30.0 / 0.50)
            return max(0.0, score)
    
    def _score_protein(self, actual: float, target: float, time_slot: str) -> float:
        """Score protein match (0-100) with workout timing adjustments.
        
        Based on REASONING_LOGIC.md:
        - Pre-workout: Slightly lower protein target (reduce score for high protein)
        - Post-workout: Slightly higher protein target (increase score for high protein)
        - Otherwise: Standard protein distribution
        
        Args:
            actual: Actual protein in recipe (g)
            target: Target protein for meal (g)
            time_slot: "pre_workout", "post_workout", or other
            
        Returns:
            Score from 0-100
        """
        if target == 0:
            return 50.0  # Neutral score if no target
        
        # Adjust target based on workout timing
        adjusted_target = target
        if time_slot == "pre_workout":
            # Pre-workout: slightly lower protein is acceptable (reduce target by 20%)
            adjusted_target = target * 0.8
        elif time_slot == "post_workout":
            # Post-workout: slightly higher protein is preferred (increase target by 20%)
            adjusted_target = target * 1.2
        
        # Calculate percentage deviation from adjusted target
        deviation = abs(actual - adjusted_target) / adjusted_target if adjusted_target > 0 else 1.0
        
        # Score based on deviation (15% tolerance for protein = 100)
        if deviation <= 0.15:
            return 100.0
        elif deviation <= 0.30:
            # 15-30% deviation = linear decrease from 100 to 70
            return 100.0 - (deviation - 0.15) * (30.0 / 0.15)
        elif deviation <= 0.50:
            # 30-50% deviation = linear decrease from 70 to 40
            return 70.0 - (deviation - 0.30) * (30.0 / 0.20)
        else:
            # >50% deviation = linear decrease from 40 to 0
            score = 40.0 - (deviation - 0.50) * (40.0 / 0.50)
            return max(0.0, score)
    
    def _score_fat(self, actual: float, target_min: float, target_max: float) -> float:
        """Score fat match (0-100) within range.
        
        Based on KNOWLEDGE.md line 9: "daily fat intake range of 50-100g"
        Fat should be within the min-max range for optimal score.
        
        Args:
            actual: Actual fat in recipe (g)
            target_min: Minimum fat target (g)
            target_max: Maximum fat target (g)
            
        Returns:
            Score from 0-100
        """
        if target_min == 0 and target_max == 0:
            return 50.0  # Neutral score if no target
        
        # Validate and fix invalid range (target_min > target_max)
        if target_min > target_max:
            target_min, target_max = target_max, target_min  # Swap to create valid range
        
        # Perfect score if within range
        if target_min <= actual <= target_max:
            return 100.0
        
        # Calculate how far outside the range
        if actual < target_min:
            # Below minimum: penalize based on how far below
            gap = target_min - actual
            range_size = target_max - target_min
            if range_size > 0:
                deviation = gap / range_size
            else:
                deviation = gap / target_min if target_min > 0 else 1.0
        else:
            # Above maximum: penalize based on how far above
            gap = actual - target_max
            range_size = target_max - target_min
            if range_size > 0:
                deviation = gap / range_size
            else:
                deviation = gap / target_max if target_max > 0 else 1.0
        
        # Score decreases as deviation increases
        if deviation <= 0.20:
            # Within 20% of range = 80-100
            return 100.0 - (deviation / 0.20) * 20.0
        elif deviation <= 0.50:
            # 20-50% outside = 60-80
            return 80.0 - ((deviation - 0.20) / 0.30) * 20.0
        else:
            # >50% outside = 0-60
            score = 60.0 - ((deviation - 0.50) / 0.50) * 60.0
            return max(0.0, score)
    
    def _score_carbs(self, actual: float, target: float, time_slot: str, 
                     carb_timing: str) -> float:
        """Score carbs match (0-100) with timing considerations.
        
        Based on KNOWLEDGE.md line 10 and REASONING_LOGIC.md:
        - Pre-workout: Fast digesting carbs preferred
        - Post-workout: Recovery carbs (good amount)
        - Sedentary: Score lower for high carbs, but don't eliminate all high-carb options
        
        Args:
            actual: Actual carbs in recipe (g)
            target: Target carbs for meal (g)
            time_slot: "pre_workout", "post_workout", "sedentary", etc.
            carb_timing: "fast_digesting", "slow_digesting", "recovery", "maintenance"
            
        Returns:
            Score from 0-100
        """
        if target == 0:
            return 50.0  # Neutral score if no target
        
        # Calculate base score from deviation
        deviation = abs(actual - target) / target if target > 0 else 1.0
        
        base_score = 100.0
        if deviation <= 0.15:
            base_score = 100.0
        elif deviation <= 0.30:
            base_score = 100.0 - (deviation - 0.15) * (30.0 / 0.15)
        elif deviation <= 0.50:
            base_score = 70.0 - (deviation - 0.30) * (30.0 / 0.20)
        else:
            base_score = max(0.0, 40.0 - (deviation - 0.50) * (40.0 / 0.50))
        
        # Apply timing adjustments
        if time_slot == "pre_workout":
            # Pre-workout: prefer fast digesting carbs (KNOWLEDGE.md example: "2 Bananas")
            if carb_timing == "fast_digesting":
                # Bonus for fast digesting
                return min(100.0, base_score * 1.1)
            elif carb_timing == "slow_digesting":
                # Penalty for slow digesting
                return base_score * 0.8
            else:
                return base_score
        elif time_slot == "post_workout":
            # Post-workout: good amount of carbs for recovery (KNOWLEDGE.md example: "Hot Honey Salmon")
            # Slight bonus if actual is at or above target
            if actual >= target:
                return min(100.0, base_score * 1.05)
            else:
                return base_score
        elif time_slot == "sedentary":
            # Sedentary: score lower for high carbs, but don't eliminate (REASONING_LOGIC.md)
            if actual > target * 1.3:
                # More than 30% over target = reduce score
                return base_score * 0.9
            else:
                return base_score
        else:
            # Other time slots: standard scoring
            return base_score
        
    def _score_schedule_match(self, 
                             recipe: Recipe,
                             context: MealContext) -> float:
        """Score cooking time vs available time (0-100).
        
        Based on KNOWLEDGE.md line 15: Busyness scale 1-4
        - 1: Snack
        - 2: ≤15 minutes
        - 3: ≤30 minutes (weeknight meal)
        - 4: 30+ minutes (weekend/meal prep)
        
        Args:
            recipe: Recipe with cooking_time_minutes
            context: Meal context with cooking_time_max
            
        Returns:
            Score from 0-100 based on time constraint adherence
            - 100 if cooking_time <= cooking_time_max (perfect match)
            - Decreasing score if slightly above (small penalty)
            - 0 if far above (hard fail)
        """
        recipe_time = recipe.cooking_time_minutes
        max_time = context.cooking_time_max
        
        # Perfect score if within time limit
        if recipe_time <= max_time:
            return 100.0
        
        # Calculate how much over the limit
        overage = recipe_time - max_time
        overage_percentage = overage / max_time if max_time > 0 else 1.0
        
        # Small penalty for slight overage (up to 20% over)
        if overage_percentage <= 0.20:
            # Linear decrease from 100 to 80 for 0-20% overage
            penalty = (overage_percentage / 0.20) * 20.0
            return 100.0 - penalty
        
        # Moderate penalty for moderate overage (20-50% over)
        elif overage_percentage <= 0.50:
            # Linear decrease from 80 to 30 for 20-50% overage
            penalty = 20.0 + ((overage_percentage - 0.20) / 0.30) * 50.0
            return 100.0 - penalty
        
        # Large penalty for significant overage (50-100% over)
        elif overage_percentage <= 1.0:
            # Linear decrease from 30 to 0 for 50-100% overage
            penalty = 50.0 + ((overage_percentage - 0.50) / 0.50) * 30.0
            return max(0.0, 100.0 - penalty)
        
        # Hard fail for >100% overage (more than double the time)
        else:
            return 0.0
        
    def _score_preference_match(self, 
                               recipe: Recipe,
                               user_profile: UserProfile) -> float:
        """Score recipe against user preferences (0-100).
        
        Based on KNOWLEDGE.md line 17:
        - Blacklist certain foods if allergic or really don't like (allergies handled in score_recipe)
        - Hard penalty for disliked foods
        - Small boost for liked/preferred foods
        
        Args:
            recipe: Recipe to evaluate
            user_profile: User preferences (likes, dislikes, allergies)
            
        Returns:
            Score from 0-100 based on preference alignment
            - Base score: 50 (neutral)
            - Hard penalty for disliked ingredients (reduce significantly)
            - Small boost for liked ingredients (increase slightly)
        """
        # Start with neutral score
        base_score = 50.0
        
        # Check for disliked ingredients (hard penalty)
        disliked_count = 0
        for ingredient in recipe.ingredients:
            ingredient_name = ingredient.name.lower()
            for disliked in user_profile.disliked_foods:
                if disliked.lower() in ingredient_name or ingredient_name in disliked.lower():
                    disliked_count += 1
                    break  # Count each ingredient only once
        
        # Apply hard penalty for disliked ingredients
        # Each disliked ingredient reduces score by 30 points
        if disliked_count > 0:
            penalty = min(disliked_count * 30.0, 50.0)  # Max penalty of 50 (to 0)
            base_score -= penalty
        
        # Check for liked ingredients (small boost)
        liked_count = 0
        for ingredient in recipe.ingredients:
            ingredient_name = ingredient.name.lower()
            for liked in user_profile.liked_foods:
                if liked.lower() in ingredient_name or ingredient_name in liked.lower():
                    liked_count += 1
                    break  # Count each ingredient only once
        
        # Apply small boost for liked ingredients
        # Each liked ingredient adds 5 points (up to +15 total)
        if liked_count > 0:
            boost = min(liked_count * 5.0, 15.0)  # Max boost of 15
            base_score += boost
        
        # Ensure score stays within 0-100 range
        return max(0.0, min(100.0, base_score))
        
    def _score_satiety_match(self, 
                            recipe_nutrition: NutritionProfile,
                            context: MealContext) -> float:
        """Score satiety appropriateness (0-100).
        
        Based on KNOWLEDGE.md line 16 and REASONING_LOGIC.md:
        - High satiety (long fast ahead: 12 hours OR gap > 4 hours):
          - High protein = higher score
          - High fat = higher score (slower digestion)
          - Higher calories = higher score (bigger meal)
          - Low calorie density preferred (volume)
        - Low satiety (frequent meals): Lighter meals preferred
        - Medium satiety: Balanced approach
        
        Args:
            recipe_nutrition: Calculated nutrition for recipe
            context: Meal context with satiety requirements
            
        Returns:
            Score from 0-100 based on satiety appropriateness
        """
        satiety_req = context.satiety_requirement.lower()
        calories = recipe_nutrition.calories
        protein = recipe_nutrition.protein_g
        fat = recipe_nutrition.fat_g
        
        if satiety_req == "high":
            # High satiety: favor high protein, high fat, higher calories
            # REASONING_LOGIC.md: "Higher calories = higher score (bigger meal)"
            
            # Score based on protein content (more protein = more satiating)
            # Target: 30-50g protein for high satiety meal
            protein_score = 50.0  # Base
            if protein >= 50.0:
                protein_score = 100.0  # Excellent
            elif protein >= 40.0:
                protein_score = 90.0
            elif protein >= 30.0:
                protein_score = 80.0
            elif protein >= 20.0:
                protein_score = 60.0
            else:
                protein_score = 40.0  # Low protein = less satiating
            
            # Score based on fat content (fat slows digestion, increases satiety)
            # Target: 15-30g fat for high satiety meal
            fat_score = 50.0  # Base
            if fat >= 25.0:
                fat_score = 100.0  # Excellent
            elif fat >= 20.0:
                fat_score = 90.0
            elif fat >= 15.0:
                fat_score = 80.0
            elif fat >= 10.0:
                fat_score = 60.0
            else:
                fat_score = 40.0  # Low fat = less satiating
            
            # Score based on calories (bigger meals = more satiating)
            # Target: 600-800 calories for high satiety meal
            calorie_score = 50.0  # Base
            if calories >= 750.0:
                calorie_score = 100.0  # Excellent
            elif calories >= 650.0:
                calorie_score = 90.0
            elif calories >= 550.0:
                calorie_score = 80.0
            elif calories >= 450.0:
                calorie_score = 60.0
            else:
                calorie_score = 40.0  # Small meal = less satiating
            
            # Weighted average: protein (40%), fat (30%), calories (30%)
            total_score = (
                protein_score * 0.40 +
                fat_score * 0.30 +
                calorie_score * 0.30
            )
            
            return total_score
        
        elif satiety_req == "low":
            # Low satiety: favor lighter meals (frequent meals scenario)
            # Target: Lower protein, lower fat, lower calories
            
            # Score based on being light (lower is better)
            # Target: 200-400 calories for low satiety meal
            calorie_score = 50.0  # Base
            if calories <= 300.0:
                calorie_score = 100.0  # Excellent (light)
            elif calories <= 400.0:
                calorie_score = 80.0
            elif calories <= 500.0:
                calorie_score = 60.0
            elif calories <= 600.0:
                calorie_score = 40.0
            else:
                calorie_score = 20.0  # Too heavy for low satiety
            
            # Lower protein is acceptable for low satiety
            # Target: 10-25g protein
            protein_score = 50.0  # Base
            if 15.0 <= protein <= 25.0:
                protein_score = 100.0  # Ideal range
            elif 10.0 <= protein <= 30.0:
                protein_score = 80.0
            elif protein < 10.0:
                protein_score = 60.0  # Very low, but acceptable
            else:
                protein_score = 40.0  # Too high for low satiety
            
            # Lower fat is preferred for low satiety
            # Target: 5-15g fat
            fat_score = 50.0  # Base
            if 5.0 <= fat <= 15.0:
                fat_score = 100.0  # Ideal range
            elif fat < 5.0:
                fat_score = 80.0
            elif fat <= 20.0:
                fat_score = 60.0
            else:
                fat_score = 40.0  # Too high for low satiety
            
            # Weighted average: calories (50%), protein (30%), fat (20%)
            # Calories most important for low satiety (lighter = better)
            total_score = (
                calorie_score * 0.50 +
                protein_score * 0.30 +
                fat_score * 0.20
            )
            
            return total_score
        
        else:  # "medium" or unknown
            # Medium satiety: balanced approach
            # Target: Moderate protein, moderate fat, moderate calories
            
            # Score based on balanced macros
            # Target: 20-40g protein, 10-25g fat, 400-600 calories
            protein_score = 50.0
            if 25.0 <= protein <= 40.0:
                protein_score = 100.0
            elif 20.0 <= protein <= 45.0:
                protein_score = 80.0
            elif 15.0 <= protein <= 50.0:
                protein_score = 60.0
            else:
                protein_score = 40.0
            
            fat_score = 50.0
            if 15.0 <= fat <= 25.0:
                fat_score = 100.0
            elif 10.0 <= fat <= 30.0:
                fat_score = 80.0
            elif 5.0 <= fat <= 35.0:
                fat_score = 60.0
            else:
                fat_score = 40.0
            
            calorie_score = 50.0
            if 450.0 <= calories <= 600.0:
                calorie_score = 100.0
            elif 400.0 <= calories <= 650.0:
                calorie_score = 80.0
            elif 350.0 <= calories <= 700.0:
                calorie_score = 60.0
            else:
                calorie_score = 40.0
            
            # Weighted average: balanced across all factors
            total_score = (
                protein_score * 0.35 +
                fat_score * 0.35 +
                calorie_score * 0.30
            )
            
            return total_score
    
    def _score_micronutrient_bonus(self, 
                                  recipe_nutrition: NutritionProfile,
                                  context: MealContext) -> float:
        """Score basic micronutrient density bonus (0-100).
        
        MVP: Simplified heuristic based on macro diversity and calorie density.
        Future: Actual micronutrient calculation (KNOWLEDGE.md line 12).
        
        Args:
            recipe_nutrition: Calculated nutrition for recipe
            context: Meal context with priority micronutrients
            
        Returns:
            Simple bonus score for micronutrient density (0-100)
            - Higher score for diverse macros (indicates diverse ingredients)
            - Higher score for reasonable calorie density
            - MVP: Simple heuristic, not actual micronutrient tracking
        """
        calories = recipe_nutrition.calories
        protein = recipe_nutrition.protein_g
        fat = recipe_nutrition.fat_g
        carbs = recipe_nutrition.carbs_g
        
        # MVP: Simple heuristic - score based on macro diversity
        # More diverse macros = more likely to have diverse micronutrients
        
        # Calculate macro balance (all macros present = good diversity)
        macro_diversity_score = 50.0  # Base
        
        # Bonus if all macros are present in reasonable amounts
        if calories > 0:
            if protein > 0 and fat > 0 and carbs > 0:
                # All macros present = good diversity
                macro_diversity_score = 80.0
                
                # Check for balanced distribution (indicates diverse ingredients)
                total_macros = protein * 4 + fat * 9 + carbs * 4  # Approximate calories from macros
                if total_macros > 0:
                    protein_pct = (protein * 4) / total_macros
                    fat_pct = (fat * 9) / total_macros
                    carbs_pct = (carbs * 4) / total_macros
                    
                    # Balanced macros (not too skewed) = better diversity
                    if 0.15 <= protein_pct <= 0.40 and 0.20 <= fat_pct <= 0.50 and 0.20 <= carbs_pct <= 0.60:
                        macro_diversity_score = 100.0  # Excellent diversity
                    elif 0.10 <= protein_pct <= 0.50 and 0.15 <= fat_pct <= 0.60 and 0.15 <= carbs_pct <= 0.70:
                        macro_diversity_score = 90.0  # Good diversity
            elif (protein > 0 and fat > 0) or (protein > 0 and carbs > 0) or (fat > 0 and carbs > 0):
                # Two macros present = moderate diversity
                macro_diversity_score = 60.0
            else:
                # Single macro = low diversity
                macro_diversity_score = 40.0
        
        # Future: Consider context.priority_micronutrients for weekly tracking
        # For MVP, we use simple macro diversity as proxy
        
        return macro_diversity_score

    def _score_balance_match(self,
                           recipe_nutrition: NutritionProfile,
                           user_profile: UserProfile,
                           current_daily_nutrition: NutritionProfile) -> float:
        """Score how well recipe fits into remaining daily budget (0-100).
           Prioritize not exceeding daily limits.
           
        HARD CONSTRAINT: If max_daily_calories is set and would be exceeded,
        returns 0.0 immediately (hard exclusion like allergens).
        """
        # HARD CONSTRAINT: Calorie Deficit Mode
        # If max_daily_calories is set, exceeding it returns 0.0 (hard exclusion)
        proj_cals = current_daily_nutrition.calories + recipe_nutrition.calories
        if user_profile.max_daily_calories is not None:
            if proj_cals > user_profile.max_daily_calories:
                return 0.0  # Hard exclusion
        
        score = 100.0
        
        # Soft penalty: Check Calories against daily target (not hard cap)
        daily_cals = user_profile.daily_calories
        if daily_cals > 0 and proj_cals > daily_cals * 1.1:  # 10% tolerance
             # Penalize
             overage = (proj_cals - daily_cals) / daily_cals
             # Linear penalty
             score -= overage * 100.0
             
        # Check Fat
        proj_fat = current_daily_nutrition.fat_g + recipe_nutrition.fat_g
        daily_fat_max = user_profile.daily_fat_g[1]
        if daily_fat_max > 0 and proj_fat > daily_fat_max:
             overage = (proj_fat - daily_fat_max) / daily_fat_max
             score -= overage * 100.0
             
        # Check Carbs
        proj_carbs = current_daily_nutrition.carbs_g + recipe_nutrition.carbs_g
        daily_carbs = user_profile.daily_carbs_g
        if daily_carbs > 0 and proj_carbs > daily_carbs * 1.1:
             overage = (proj_carbs - daily_carbs) / daily_carbs
             score -= overage * 100.0
             
        return max(0.0, score)
    
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
