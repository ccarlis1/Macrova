"""Meal planning system for generating daily meal plans."""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from src.data_layer.models import Recipe, Meal, DailyMealPlan, UserProfile, NutritionGoals, NutritionProfile
from src.scoring.recipe_scorer import RecipeScorer, MealContext
from src.nutrition.aggregator import NutritionAggregator


@dataclass
class DailySchedule:
    """User's schedule for a specific day."""
    breakfast_time: str  # e.g., "07:00"
    breakfast_busyness: int  # 1-4 scale
    lunch_time: str
    lunch_busyness: int
    dinner_time: str
    dinner_busyness: int
    workout_time: Optional[str] = None  # e.g., "18:00"


@dataclass
class PlanningResult:
    """Result of meal planning with success metrics."""
    daily_plan: DailyMealPlan
    success: bool
    total_nutrition: NutritionProfile
    target_adherence: Dict[str, float]  # % of target met for each macro
    warnings: List[str]  # Any issues or compromises made


class MealPlanner:
    """Plans daily meals using scored recipes."""
    
    def __init__(self, 
                 recipe_scorer: RecipeScorer,
                 recipe_retriever,
                 nutrition_aggregator: NutritionAggregator):
        """Initialize meal planner.
        
        Args:
            recipe_scorer: RecipeScorer instance for scoring recipes
            recipe_retriever: RecipeRetriever instance for finding recipes
            nutrition_aggregator: NutritionAggregator instance for summing nutrition
        """
        self.recipe_scorer = recipe_scorer
        self.recipe_retriever = recipe_retriever
        self.nutrition_aggregator = nutrition_aggregator
    
    def plan_daily_meals(self, 
                        user_profile: UserProfile,
                        schedule: DailySchedule,
                        available_recipes: List[Recipe] = None) -> PlanningResult:
        """Plan 3 meals for a day meeting nutrition and schedule goals.
        
        Uses greedy approach: selects best recipe for each meal slot independently.
        Final validation ensures daily targets are met within tolerance.
        
        Args:
            user_profile: User preferences and nutrition goals
            schedule: Daily schedule with time/busyness constraints
            available_recipes: Optional recipe list (uses retriever if None)
            
        Returns:
            PlanningResult with selected meals and adherence metrics
        """
        # Convert user profile to nutrition goals
        goals = NutritionGoals(
            calories=user_profile.daily_calories,
            protein_g=user_profile.daily_protein_g,
            fat_g_min=user_profile.daily_fat_g[0],
            fat_g_max=user_profile.daily_fat_g[1],
            carbs_g=user_profile.daily_carbs_g
        )
        
        # Distribute daily targets across 3 meals
        meal_contexts = self._distribute_daily_targets(goals, schedule)
        
        # Get available recipes (use provided list or retrieve from database)
        if available_recipes is None:
            # Use retriever's recipe_db to get all recipes (no keyword filter for MVP)
            available_recipes = self.recipe_retriever.recipe_db.get_all_recipes()
        
        # Track nutrition consumed so far
        current_nutrition = NutritionProfile(
            calories=0.0,
            protein_g=0.0,
            fat_g=0.0,
            carbs_g=0.0
        )
        
        # Plan each meal
        planned_meals = []
        meal_order = ["breakfast", "lunch", "dinner"]
        used_recipe_ids = set()  # Track recipes already selected to prevent reuse
        
        for meal_type in meal_order:
            context = meal_contexts[meal_type]
            
            # Filter candidates by basic constraints (cooking time, allergies, dislikes)
            candidates = self._filter_candidates(
                available_recipes,
                context,
                user_profile
            )
            
            # Exclude recipes already selected for previous meals (Issue #7)
            candidates = [r for r in candidates if r.id not in used_recipe_ids]
            
            if not candidates:
                # No candidates available - create warning
                warnings = [f"No recipes available for {meal_type}"]
                # Return partial plan with warning
                return PlanningResult(
                    daily_plan=None,  # Cannot create complete plan
                    success=False,
                    total_nutrition=current_nutrition,
                    target_adherence={},
                    warnings=warnings
                )
            
            # Select best recipe for this meal
            best_recipe, score = self._select_best_recipe(
                candidates,
                context,
                user_profile,
                current_nutrition
            )
            
            # Mark recipe as used to prevent reuse in subsequent meals (Issue #7)
            used_recipe_ids.add(best_recipe.id)
            
            # Calculate recipe nutrition
            recipe_nutrition = self.recipe_scorer.nutrition_calculator.calculate_recipe_nutrition(best_recipe)
            
            # Create Meal object
            meal = Meal(
                recipe=best_recipe,
                nutrition=recipe_nutrition,
                meal_type=meal_type,
                scheduled_time=None,  # MVP: not tracking exact time
                busyness_level=schedule.breakfast_busyness if meal_type == "breakfast" else
                              (schedule.lunch_busyness if meal_type == "lunch" else schedule.dinner_busyness)
            )
            planned_meals.append(meal)
            
            # Update running nutrition totals
            # Simply add recipe nutrition to current totals
            current_nutrition = NutritionProfile(
                calories=current_nutrition.calories + recipe_nutrition.calories,
                protein_g=current_nutrition.protein_g + recipe_nutrition.protein_g,
                fat_g=current_nutrition.fat_g + recipe_nutrition.fat_g,
                carbs_g=current_nutrition.carbs_g + recipe_nutrition.carbs_g
            )
        
        # Validate daily plan
        success, adherence, warnings = self._validate_daily_plan(planned_meals, goals)
        
        # Create daily meal plan
        daily_plan = DailyMealPlan(
            date="",  # MVP: empty, future: actual date
            meals=planned_meals,
            total_nutrition=current_nutrition,
            goals=goals,
            meets_goals=success
        )
        
        return PlanningResult(
            daily_plan=daily_plan,
            success=success,
            total_nutrition=current_nutrition,
            target_adherence=adherence,
            warnings=warnings
        )
    
    def _filter_candidates(self,
                          recipes: List[Recipe],
                          context: MealContext,
                          user_profile: UserProfile) -> List[Recipe]:
        """Filter recipes by basic constraints (cooking time, allergies, dislikes).
        
        Args:
            recipes: List of all recipes
            context: Meal context with constraints
            user_profile: User preferences
            
        Returns:
            Filtered list of candidate recipes
        """
        candidates = []
        
        for recipe in recipes:
            # Filter by cooking time
            if recipe.cooking_time_minutes > context.cooking_time_max:
                continue  # Skip recipes that take too long
            
            # Filter by allergies (hard exclusion)
            if self.recipe_scorer._contains_allergens(recipe, user_profile.allergies):
                continue  # Skip allergen-containing recipes
            
            # Filter by disliked foods (soft exclusion - can be overridden by scoring)
            # For MVP, we'll let scoring handle dislikes, but could filter here too
            
            candidates.append(recipe)
        
        return candidates
        
    def _distribute_daily_targets(self, 
                                 goals: NutritionGoals,
                                 schedule: DailySchedule) -> Dict[str, MealContext]:
        """Distribute daily nutrition targets across 3 meals based on schedule.
        
        Based on KNOWLEDGE.md and REASONING_LOGIC.md:
        - Pre-workout meals: Lower protein, fast-digesting carbs
        - Post-workout meals: Higher protein, recovery carbs
        - High satiety meals: Higher protein, fat, calories (long fast ahead)
        - Standard meals: Balanced distribution
        
        Args:
            goals: Daily nutrition goals
            schedule: Daily schedule with workout timing and busyness
            
        Returns:
            Dictionary mapping meal_type ("breakfast", "lunch", "dinner") to MealContext
        """
        # Calculate per-meal base targets (divide by 3)
        base_calories = goals.calories / 3.0
        base_protein = goals.protein_g / 3.0
        base_fat_min = goals.fat_g_min / 3.0
        base_fat_max = goals.fat_g_max / 3.0
        base_carbs = goals.carbs_g / 3.0
        
        # Determine workout timing relative to meals
        workout_time = schedule.workout_time
        breakfast_time = schedule.breakfast_time
        lunch_time = schedule.lunch_time
        dinner_time = schedule.dinner_time
        
        # Helper to determine if meal is pre/post workout
        def is_pre_workout(meal_time: str) -> bool:
            if not workout_time:
                return False
            # Simple comparison (assumes times are in "HH:MM" format)
            meal_hour = int(meal_time.split(":")[0])
            workout_hour = int(workout_time.split(":")[0])
            # Pre-workout if meal is 1-3 hours before workout
            return 1 <= (workout_hour - meal_hour) <= 3
        
        def is_post_workout(meal_time: str) -> bool:
            if not workout_time:
                return False
            meal_hour = int(meal_time.split(":")[0])
            workout_hour = int(workout_time.split(":")[0])
            # Post-workout if meal is 0-3 hours after workout
            return 0 <= (meal_hour - workout_hour) <= 3
        
        # Determine satiety requirements
        # High satiety if long fast ahead (12 hours overnight OR >4 hour gap)
        def get_satiety_requirement(meal_type: str, meal_time: str) -> str:
            if meal_type == "dinner":
                # Dinner before overnight fast = high satiety
                return "high"
            # Check for >4 hour gap to next meal
            if meal_type == "breakfast":
                next_meal_hour = int(lunch_time.split(":")[0])
                meal_hour = int(meal_time.split(":")[0])
                if (next_meal_hour - meal_hour) > 4:
                    return "high"
            elif meal_type == "lunch":
                next_meal_hour = int(dinner_time.split(":")[0])
                meal_hour = int(meal_time.split(":")[0])
                if (next_meal_hour - meal_hour) > 4:
                    return "high"
            return "medium"
        
        # Map busyness level to cooking time max (KNOWLEDGE.md line 15)
        def busyness_to_time(busyness: int) -> int:
            if busyness == 1:  # Snack
                return 5
            elif busyness == 2:  # ≤15 minutes
                return 15
            elif busyness == 3:  # ≤30 minutes
                return 30
            else:  # busyness == 4: 30+ minutes
                return 60
        
        # Determine carb timing preference
        def get_carb_timing(meal_type: str, meal_time: str) -> str:
            if is_pre_workout(meal_time):
                return "fast_digesting"
            elif is_post_workout(meal_time):
                return "recovery"
            elif meal_type == "dinner":
                return "slow_digesting"  # Complex carbs for overnight satiety
            else:
                return "maintenance"
        
        # Build meal contexts
        meal_contexts = {}
        
        # Breakfast
        breakfast_pre_workout = is_pre_workout(breakfast_time)
        breakfast_context = MealContext(
            meal_type="breakfast",
            time_slot="pre_workout" if breakfast_pre_workout else "morning",
            cooking_time_max=busyness_to_time(schedule.breakfast_busyness),
            target_calories=base_calories * (0.9 if breakfast_pre_workout else 1.0),  # Slightly less for pre-workout
            target_protein=base_protein * (0.8 if breakfast_pre_workout else 1.0),  # Lower protein pre-workout
            target_fat_min=base_fat_min * (0.8 if breakfast_pre_workout else 1.0),
            target_fat_max=base_fat_max * (0.8 if breakfast_pre_workout else 1.0),
            target_carbs=base_carbs * (1.1 if breakfast_pre_workout else 1.0),  # More carbs pre-workout
            satiety_requirement=get_satiety_requirement("breakfast", breakfast_time),
            carb_timing_preference=get_carb_timing("breakfast", breakfast_time),
            priority_micronutrients=[]  # MVP: empty, future: weekly tracking
        )
        meal_contexts["breakfast"] = breakfast_context
        
        # Lunch
        lunch_pre_workout = is_pre_workout(lunch_time)
        lunch_post_workout = is_post_workout(lunch_time)
        lunch_context = MealContext(
            meal_type="lunch",
            time_slot=("pre_workout" if lunch_pre_workout else 
                      "post_workout" if lunch_post_workout else "afternoon"),
            cooking_time_max=busyness_to_time(schedule.lunch_busyness),
            target_calories=base_calories * (0.9 if lunch_pre_workout else 1.1 if lunch_post_workout else 1.0),
            target_protein=base_protein * (0.8 if lunch_pre_workout else 1.2 if lunch_post_workout else 1.0),
            target_fat_min=base_fat_min * (0.8 if lunch_pre_workout else 1.0),
            target_fat_max=base_fat_max * (0.8 if lunch_pre_workout else 1.0),
            target_carbs=base_carbs * (1.1 if lunch_pre_workout else 1.1 if lunch_post_workout else 1.0),
            satiety_requirement=get_satiety_requirement("lunch", lunch_time),
            carb_timing_preference=get_carb_timing("lunch", lunch_time),
            priority_micronutrients=[]
        )
        meal_contexts["lunch"] = lunch_context
        
        # Dinner
        dinner_post_workout = is_post_workout(dinner_time)
        dinner_context = MealContext(
            meal_type="dinner",
            time_slot="post_workout" if dinner_post_workout else "evening",
            cooking_time_max=busyness_to_time(schedule.dinner_busyness),
            target_calories=base_calories * (1.2 if dinner_post_workout else 1.1),  # Higher for recovery/satiety
            target_protein=base_protein * (1.2 if dinner_post_workout else 1.1),  # Higher for recovery/satiety
            target_fat_min=base_fat_min * 1.0,
            target_fat_max=base_fat_max * 1.0,
            target_carbs=base_carbs * (1.1 if dinner_post_workout else 1.0),
            satiety_requirement="high",  # Always high for dinner (overnight fast)
            carb_timing_preference="slow_digesting",  # Complex carbs for overnight
            priority_micronutrients=[]
        )
        meal_contexts["dinner"] = dinner_context
        
        return meal_contexts
    
    def _select_best_recipe(self, 
                           candidates: List[Recipe],
                           context: MealContext,
                           user_profile: UserProfile,
                           current_nutrition: NutritionProfile) -> Tuple[Recipe, float]:
        """Select highest-scoring recipe for a meal slot.
        
        Uses greedy approach: scores all candidates and selects the highest.
        
        Args:
            candidates: List of candidate recipes
            context: Meal context with targets and constraints
            user_profile: User preferences and goals
            current_nutrition: Nutrition consumed so far today
            
        Returns:
            Tuple of (best_recipe, score)
            
        Raises:
            ValueError: If candidates list is empty
        """
        if not candidates:
            raise ValueError("Cannot select recipe from empty candidates list")
        
        # Score all candidates
        best_recipe = None
        best_score = -1.0
        
        for recipe in candidates:
            score = self.recipe_scorer.score_recipe(
                recipe,
                context,
                user_profile,
                current_nutrition
            )
            
            # Track highest score
            if score > best_score:
                best_score = score
                best_recipe = recipe
        
        # Return best recipe and its score
        return (best_recipe, best_score)
        
    def _validate_daily_plan(self, 
                            meals: List[Meal],
                            goals: NutritionGoals) -> Tuple[bool, Dict[str, float], List[str]]:
        """Validate if daily plan meets nutrition targets within tolerance.
        
        Based on IMPLEMENTATION_PLAN.md: ±10% tolerance for MVP.
        Based on KNOWLEDGE.md:
        - Calories: 2400 target (slight deficit from 2800 maintenance)
        - Protein: 0.6-0.9g per pound bodyweight (weekly average 0.7-0.8g/lb)
        - Fat: 50-100g daily range (weekly median ~75g)
        - Carbs: Remainder after protein/fat
        
        Args:
            meals: List of planned meals
            goals: Daily nutrition goals
            
        Returns:
            Tuple of (success: bool, adherence: Dict[str, float], warnings: List[str])
            - success: True if all targets met within tolerance
            - adherence: Percentage of target met for each macro (calories, protein, fat, carbs)
            - warnings: List of warning messages for deviations
        """
        if not meals:
            return (False, {}, ["No meals planned"])
        
        # Aggregate total nutrition from all meals
        total_nutrition = self.nutrition_aggregator.aggregate_meals(meals)
        
        # Calculate adherence percentages
        adherence = {}
        warnings = []
        
        # Calories adherence (10% tolerance per IMPLEMENTATION_PLAN.md)
        calories_adherence = (total_nutrition.calories / goals.calories * 100.0) if goals.calories > 0 else 0.0
        adherence["calories"] = calories_adherence
        if calories_adherence < 90.0:
            warnings.append(f"Calories below target: {total_nutrition.calories:.0f} / {goals.calories} ({calories_adherence:.1f}%)")
        elif calories_adherence > 110.0:
            warnings.append(f"Calories above target: {total_nutrition.calories:.0f} / {goals.calories} ({calories_adherence:.1f}%)")
        
        # Protein adherence (10% tolerance)
        # KNOWLEDGE.md: 0.6-0.9g per pound bodyweight (daily range)
        protein_adherence = (total_nutrition.protein_g / goals.protein_g * 100.0) if goals.protein_g > 0 else 0.0
        adherence["protein"] = protein_adherence
        if protein_adherence < 90.0:
            warnings.append(f"Protein below target: {total_nutrition.protein_g:.1f}g / {goals.protein_g:.1f}g ({protein_adherence:.1f}%)")
        elif protein_adherence > 110.0:
            warnings.append(f"Protein above target: {total_nutrition.protein_g:.1f}g / {goals.protein_g:.1f}g ({protein_adherence:.1f}%)")
        
        # Fat adherence (must be within min-max range)
        # KNOWLEDGE.md line 9: "daily fat intake range of 50-100g"
        fat_min_adherence = (total_nutrition.fat_g / goals.fat_g_min * 100.0) if goals.fat_g_min > 0 else 0.0
        fat_max_adherence = (total_nutrition.fat_g / goals.fat_g_max * 100.0) if goals.fat_g_max > 0 else 0.0
        
        # Store adherence as percentage relative to range midpoint for display
        fat_range_midpoint = (goals.fat_g_min + goals.fat_g_max) / 2.0
        fat_adherence = (total_nutrition.fat_g / fat_range_midpoint * 100.0) if fat_range_midpoint > 0 else 0.0
        adherence["fat"] = fat_adherence
        
        if total_nutrition.fat_g < goals.fat_g_min:
            warnings.append(f"Fat below minimum: {total_nutrition.fat_g:.1f}g / {goals.fat_g_min:.1f}g ({fat_min_adherence:.1f}%)")
        elif total_nutrition.fat_g > goals.fat_g_max:
            warnings.append(f"Fat above maximum: {total_nutrition.fat_g:.1f}g / {goals.fat_g_max:.1f}g ({fat_max_adherence:.1f}%)")
        
        # Carbs adherence (10% tolerance)
        # KNOWLEDGE.md line 10: Carbs are remainder after protein/fat
        carbs_adherence = (total_nutrition.carbs_g / goals.carbs_g * 100.0) if goals.carbs_g > 0 else 0.0
        adherence["carbs"] = carbs_adherence
        if carbs_adherence < 90.0:
            warnings.append(f"Carbs below target: {total_nutrition.carbs_g:.1f}g / {goals.carbs_g:.1f}g ({carbs_adherence:.1f}%)")
        elif carbs_adherence > 110.0:
            warnings.append(f"Carbs above target: {total_nutrition.carbs_g:.1f}g / {goals.carbs_g:.1f}g ({carbs_adherence:.1f}%)")
        
        # Determine success (within 10% tolerance for calories/protein/carbs, within range for fat)
        # IMPLEMENTATION_PLAN.md: "Meals meet calorie and macro targets (within 10% tolerance)"
        success = (
            90.0 <= calories_adherence <= 110.0 and
            90.0 <= protein_adherence <= 110.0 and
            goals.fat_g_min <= total_nutrition.fat_g <= goals.fat_g_max and
            90.0 <= carbs_adherence <= 110.0
        )
        
        return (success, adherence, warnings)
