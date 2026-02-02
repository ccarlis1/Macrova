# Reasoning Logic - Pseudocode Outline

## Overview
This document outlines the step-by-step reasoning process a Nutrition Agent would follow to generate a full day of meals, based on the example in KNOWLEDGE.md. This is conceptual pseudocode, not implementation code.

---

## INITIALIZATION PHASE

```
LOAD user_profile:
    - Daily calorie target (e.g., 2400 kcal)
    - Daily macro targets (protein, fat range, carbs calculated)
    - Daily micronutrient RDIs (based on maintenance calories, not deficit)
    - Schedule constraints (time slots with busyness levels 1-4)
    - Satiety requirements (long overnight fast, frequent meals, etc.)
    - Taste preferences (liked foods, disliked foods, allergies)
    - Activity schedule (work times, workout times, etc.)
    - OPTIONAL: max_daily_calories (hard cap for Calorie Deficit Mode)

LOAD weekly_tracker:
    - Running totals of all nutrients consumed so far this week
    - Days remaining in week
    - Nutrients that need to be carried forward from previous days

INITIALIZE daily_tracker:
    - calories_consumed = 0
    - protein_consumed = 0
    - fat_consumed = 0
    - carbs_consumed = 0
    - micronutrients_consumed = {} (all micronutrients set to 0)
    - meals_planned = []

CALCULATE daily_macro_targets:
    - protein_target = user_profile.daily_protein_g
    - fat_min = user_profile.daily_fat_g.min
    - fat_max = user_profile.daily_fat_g.max
    - carbs_target = (calories_target - protein*4 - fat*9) / 4
        where fat = median of fat range (e.g., 75g)

CALCULATE daily_micronutrient_targets:
    - For each micronutrient:
        - daily_target = weekly_RDI / 7
        - adjusted_target = daily_target + (weekly_deficit / days_remaining)
            where weekly_deficit = nutrients that need to be carried forward
```

---

## MEAL PLANNING PHASE (Iterative for each meal slot)

```
FOR each meal_slot in day (breakfast, lunch, snack, dinner, etc.):

    // STEP 1: ANALYZE CURRENT CONTEXT
    GET meal_context:
        - current_time = meal_slot.time
        - busyness_level = user_profile.schedule[current_time]
        - activity_context = determine_activity_context(current_time):
            * "pre_workout" if workout is within 2 hours
            * "post_workout" if workout was within 3 hours (extended window for recovery meal planning)
            * "sedentary" if no activity nearby
            * "overnight_fast_ahead" if long period until next meal
        - time_until_next_meal = calculate_time_until_next_meal()
        - satiety_requirement = determine_satiety_need(time_until_next_meal)

    // STEP 2: IDENTIFY NUTRIENT GAPS
    ANALYZE nutrient_status:
        - nutrients_already_covered = identify_high_nutrients(daily_tracker):
            * List all micronutrients that are already at or above daily_target
            * These don't need to be prioritized in this meal
        - nutrients_still_needed = identify_low_nutrients(daily_tracker):
            * List all micronutrients that are below daily_target
            * Prioritize those furthest below target
            * Consider weekly carryover needs
        - macro_remaining = calculate_macro_remaining():
            * calories_remaining = daily_target - calories_consumed
            * protein_remaining = protein_target - protein_consumed
            * fat_remaining = fat_max - fat_consumed (but ensure >= fat_min)
            * carbs_remaining = carbs_target - carbs_consumed

    // STEP 3: DETERMINE MEAL REQUIREMENTS
    DEFINE meal_requirements:
        - cooking_time_max = busyness_level_to_time(busyness_level):
            * 1 = snack (< 5 min)
            * 2 = ≤ 15 min
            * 3 = ≤ 30 min
            * 4 = 30+ min
        - carb_timing_requirement:
            * If pre_workout:
                - Need adequate AMOUNT of carbs (amount > complexity)
                - Fast OR medium digesting carbs acceptable
                - Recipe should have: low fiber, low fat, medium-low protein
                - Purpose: Maximize carb absorption into muscle glycogen
                - NOTE: Complexity of carb is less important than having sufficient carbs with this macro profile
            * If post_workout: need good_amount_of_carbs
            * If overnight_fast_ahead: need complex_carbs (for satiety)
            * If sedentary: 
                - Minimize carbs to avoid blood sugar spike
                - BUT: Don't prioritize low carb for ALL meals on non-training days
                - Balance: Still need to hit daily carb target
                - NOTE: This condition must not overpower the daily target condition
        - satiety_requirements:
            * If long_fast_ahead (e.g., 12 hours overnight OR meal gap > 4 hours):
                - high_satiety (fiber, protein, volume, low_calorie_density)
                - higher_calories (bigger meal with more calories)
                - NOTE: If not eating for a long time, meal should be BIGGER with more calories
            * If frequent_meals: moderate_satiety (even spread)
        - micronutrient_priorities = nutrients_still_needed (sorted by deficit)
        - macro_targets_for_meal = distribute_macros_across_remaining_meals()

    // STEP 4: FILTER AND SCORE RECIPES
    FILTER candidate_recipes:
        - cooking_time <= meal_requirements.cooking_time_max
        - No blacklisted ingredients (allergies, dislikes)
        - Respects taste preferences (if possible, prioritize micronutrients first)
        - If meal_prep_mode: exclude ingredients already in prepped meals

    FOR each candidate_recipe:
        CALCULATE recipe_score:
            // Nutrition Match (40 points)
            - calories_score = score_calories(recipe, macro_targets_for_meal.calories)
            - protein_score = score_protein(recipe, macro_targets_for_meal.protein):
                * If pre_workout: Slightly lower protein target (reduce score for high protein)
                * If post_workout: Slightly higher protein target (increase score for high protein)
                * Otherwise: Standard protein distribution
            - fat_score = score_fat(recipe, macro_targets_for_meal.fat_range)
            - carbs_score = score_carbs(recipe, meal_requirements.carb_timing):
                * If pre_workout: Score based on carb amount AND macro profile (low fiber, low fat, medium-low protein)
                * If sedentary: Score lower for high carbs, but don't eliminate all high-carb options
            
            // Micronutrient Match (30 points)
            - micronutrient_score = score_micronutrients(recipe, nutrients_still_needed):
                * Higher score for nutrients that are most needed
                * Lower score for nutrients already covered
                * Bonus for nutrients that need weekly carryover
            
            // Schedule Match (20 points)
            - cooking_time_score = score_cooking_time(recipe, busyness_level)
            
            // Satiety Match (10 points)
            - satiety_score = score_satiety(recipe, satiety_requirement):
                * If long_fast_ahead (12 hours OR gap > 4 hours):
                    - High fiber = higher score
                    - High protein = higher score
                    - Low calorie density = higher score
                    - Higher calories = higher score (bigger meal)
                * If frequent_meals: Moderate satiety = higher score
            
            // Balance (10 points)
            - balance_score = score_balance(recipe, daily_tracker):
                * HARD CONSTRAINT: If max_daily_calories is set and would be exceeded → score = 0.0
                * Complements other meals (doesn't duplicate nutrients excessively)
                * Avoids nutrient overlap where not needed
                * Fat diversity (doesn't rely on same fat sources)

    // HARD EXCLUSION CHECK
    IF balance_score == 0.0 AND max_daily_calories is set:
        EXCLUDE recipe (hard constraint violated)

    SELECT best_recipe = candidate with highest total_score (excluding hard failures)

    // STEP 5: CALCULATE NUTRITION FOR SELECTED RECIPE
    CALCULATE recipe_nutrition:
        FOR each ingredient in recipe.ingredients:
            IF ingredient.is_to_taste == True:
                SKIP ingredient (exclude from nutrition calculation)
            ELSE:
                LOOKUP ingredient_nutrition in nutrition_database
                CONVERT quantity to match database unit
                CALCULATE nutrition_contribution = (per_unit_nutrition * quantity) / unit_size
                ADD to recipe totals
        
        recipe.total_calories = sum(all ingredient calories)
        recipe.total_protein = sum(all ingredient protein)
        recipe.total_fat = sum(all ingredient fat)
        recipe.total_carbs = sum(all ingredient carbs)
        recipe.micronutrients = sum(all ingredient micronutrients)

    // STEP 6: UPDATE TRACKERS
    UPDATE daily_tracker:
        - calories_consumed += recipe.total_calories
        - protein_consumed += recipe.total_protein
        - fat_consumed += recipe.total_fat
        - carbs_consumed += recipe.total_carbs
        - FOR each micronutrient: micronutrients_consumed[micronutrient] += recipe.micronutrients[micronutrient]
        - meals_planned.append(recipe)

    // STEP 7: GENERATE REASONING EXPLANATION
    GENERATE meal_reasoning:
        - Explain why this meal was chosen:
            * What nutrients it provides that were needed
            * How it fits the schedule (cooking time, activity context)
            * How it addresses satiety needs
            * What nutrients from previous meals made this choice logical
            * Example: "Vitamin C, A, and K are high from previous meal, not needed. 
                       Missing minerals like manganese, calcium, zinc. Beef hits those targets. 
                       Need slower digesting carbs for upcoming workout. Quick to prepare."

END FOR (each meal slot)
```

---

## VALIDATION PHASE

```
VALIDATE daily_plan:

    // Macro Validation
    CHECK macros:
        - calories_consumed within target_range (e.g., 2400 ± 10%)
        - protein_consumed within target_range (0.6-0.9g/lb bodyweight)
        - fat_consumed within range (50-100g, ideally ~75g)
        - carbs_consumed approximately matches calculated target
        
        IF macros_not_met:
            ADJUST meal_plan (if possible) OR
            FLAG as acceptable_deviation (if within tolerance)

    // Upper Tolerable Intake (UL) Validation — DAILY enforcement
    // ULs are DAILY limits, NOT averaged over the week
    FOR each micronutrient with non-null UL:
        IF daily_tracker.micronutrients[micronutrient] > resolved_ul[micronutrient]:
            MARK plan as INVALID
            ADD violation: "UL EXCEEDED: {nutrient} {actual} > {limit} (excess: {excess})"
            // Weekly tracking does NOT weaken this — each day must pass independently

    // Micronutrient RDI Validation (separate from UL)
    FOR each micronutrient:
        CALCULATE percentage_of_RDI = (daily_tracker.micronutrients[micronutrient] / daily_RDI) * 100
        
        IF percentage_of_RDI < 100:
            DETERMINE if_carryover_needed:
                - Calculate weekly_deficit = (100 - percentage_of_RDI) * daily_RDI
                - Add to weekly_tracker.carryover_needs[micronutrient]
                - Mark for next day: "CARRY INTO NEXT DAY FOR WEEKLY CALCULATION"
        
        IF percentage_of_RDI >= 100:
            MARK as met (can go over, prefer over than under)
        
        SPECIAL_CASES:
            - Vitamin D: Mark as "DOES NOT MATTER" (obtained from sun/supplements)
            - Omega-3:Omega-6 Ratio: Check ratio (e.g., 1:4) is more important than individual RDIs
            - Sodium: Flag if high (e.g., >200% RDI) as "worth monitoring"

    // Fat Diversity Check
    CHECK fat_diversity:
        - Ensure fat sources are diverse (not all from one type)
        - Avoid excessive reliance on single sources (beef, eggs, cooking oils)
        - Prefer healthy fat variety

    // Weekly Tracking Update
    UPDATE weekly_tracker:
        - Add today's nutrition to weekly_totals
        - Update carryover_needs for next day
        - Calculate days_remaining
```

---

## OUTPUT GENERATION PHASE

```
GENERATE output:

    // Format Each Meal
    FOR each meal in daily_tracker.meals_planned:
        OUTPUT meal_section:
            - Meal name
            - Reasoning explanation (from meal_reasoning)
            - Ingredients list (including "to taste" items for display)
            - Instructions
            - Nutrition breakdown (calories, macros)
                * Note: "to taste" ingredients excluded from nutrition totals

    // Generate Total Breakdown
    OUTPUT total_breakdown:
        // Macronutrients Section
        - Total calories (with target comparison and status ✔️ or ⚠️)
        - Total protein (with status)
        - Total fat (with status)
        - Total carbs (with status)

        // Micronutrients Section
        - General nutrients (Fiber, Omega-3, Omega-6, Ratio)
        - Vitamins (all B vitamins, A, C, D, E, K)
            * Show percentage of RDI
            * Mark special cases (D = doesn't matter, E = carryover, etc.)
        - Minerals (Calcium, Copper, Iron, Magnesium, etc.)
            * Show percentage of RDI
            * Mark carryover needs
            * Flag high values (e.g., Sodium)

    // Generate Weekly Notes
    OUTPUT weekly_notes:
        - List nutrients that need carryover to next day
        - Weekly progress summary (if tracking weekly)
```

---

## KEY DECISION RULES

### Rule 1: Micronutrient Prioritization
```
WHEN selecting recipes:
    PRIORITIZE nutrients that are:
        - Most below daily target
        - Needed for weekly carryover
        - Not already covered by previous meals
    
    DEPRIORITIZE nutrients that are:
        - Already at or above daily target
        - Can be easily obtained later
```

### Rule 2: Macro Distribution
```
WHEN distributing macros across meals:
    - Protein: 
        * Distribute relatively evenly across all meals
        * EXCEPTION: Preworkout meals should have SLIGHTLY less protein
        * EXCEPTION: Postworkout meals should have SLIGHTLY more protein
        * Rationale: Preworkout needs to maximize carb absorption, postworkout needs protein for synthesis
    
    - Fat: Ensure diversity, meet minimum for hormone health
    
    - Carbs: Time based on activity:
        * Preworkout: Adequate amount with specific macro profile (low fiber, low fat, medium-low protein)
          - Amount matters more than complexity (fast/medium digesting OK)
          - Purpose: Maximize carb absorption into muscle glycogen
        * Postworkout: Good amount of carbs for recovery
        * Sedentary: Minimize to avoid blood sugar spike
          - BUT: Don't prioritize low carb for ALL meals on non-training days
          - Still need to hit daily carb target
          - This condition must not overpower daily target condition
        * Long fast ahead: Complex carbs for satiety
```

### Rule 3: Schedule Constraints
```
WHEN matching recipes to schedule:
    - Busyness level 1: Snack only (< 5 min)
    - Busyness level 2: Quick meal (≤ 15 min)
    - Busyness level 3: Weeknight meal (≤ 30 min)
    - Busyness level 4: Weekend/meal prep (30+ min)
    
    NEVER select recipe with cooking_time > busyness_level_max
```

### Rule 4: Satiety Management
```
WHEN determining satiety needs:
    IF long_fast_ahead (e.g., 12 hours overnight OR meal timing gap > 4 hours):
        - Prioritize high fiber
        - Prioritize high protein
        - Prioritize volume (low calorie density)
        - Prioritize higher calories (bigger meal)
        - Use satiety index for food selection
        - NOTE: If not eating for a long time, meal should be BIGGER with more calories
    
    IF frequent_meals:
        - Balance satiety evenly
        - Avoid excessive satiety in single meal
```

### Rule 5: "To Taste" and Seasoning Handling
```
WHEN calculating nutrition (MVP):
    FOR each ingredient:
        IF ingredient.unit == "to taste" OR ingredient contains "to taste":
            - Include in recipe display (show exact text: "salt to taste")
            - Include in instructions
            - EXCLUDE from nutrition calculation
            - Rationale: Negligible nutritional value, varies by preference

WHEN calculating nutrition (Future - Recipe API Integration):
    FOR each ingredient:
        // Handle "to taste" explicitly marked ingredients
        IF ingredient.unit == "to taste" OR ingredient contains "to taste":
            - Include in recipe display
            - EXCLUDE from nutrition calculation
        
        // Handle seasonings and small ingredients (complex logic required)
        ELSE IF ingredient is seasoning OR small_amount:
            - STILL output exact measurements for cooking (e.g., "1 tbsp ground turmeric")
            - DO NOT output as "to taste" - user needs exact measurements for cooking
            - DECIDE whether to calculate nutrition based on ingredient-specific rules:
                * Most seasonings: EXCLUDE from micronutrient calculation
                * BUT: Cannot use simple weight threshold
                * Example: 1 tbsp turmeric = negligible (exclude)
                * Example: 1 tbsp sunflower oil = 120 cal + nutrients (include)
                * Solution: Ingredient-specific logic, not blanket threshold rules
            - Rationale: Some small ingredients are nutritionally significant (oils, seeds)
                        while others are negligible (spices, herbs)
    
    NOTE: This requires ingredient classification system (post-MVP feature)
          Simple weight thresholds won't work due to density differences
```

### Rule 6: Weekly Tracking
```
WHEN tracking weekly nutrients:
    - RDIs calculated from maintenance calories (not deficit)
    - Daily flexibility allowed
    - Weekly totals must meet RDIs
    - Prefer going over weekly RDI rather than under
    - Carry forward deficits to next day
    - Example: If Vitamin E is 96% today, need 104%+ tomorrow to meet weekly
```

---

## EXAMPLE FLOW (Based on KNOWLEDGE.md Example)

```
INITIALIZE:
    - Daily target: 2400 kcal, 166g protein, 50-100g fat, ~205g carbs
    - Schedule: Work day, gym after work, long overnight fast

MEAL 1 (Breakfast):
    CONTEXT: Early morning, sedentary work ahead, long period until next meal
    GAPS: All nutrients needed (first meal)
    REQUIREMENTS: High satiety, low carbs (avoid blood sugar spike), quick prep
    SELECT: 6 Egg Scramble (high protein/fat, low carbs, satiating, quick)
    RESULT: 667 kcal, 48g protein, 29g carbs, 37g fat
    COVERED: High in Vitamins C, A, K

MEAL 2 (Lunch):
    CONTEXT: Pre-workout, need slower digesting carbs, quick prep
    GAPS: Vitamins C/A/K already covered, need minerals (manganese, calcium, zinc)
    REQUIREMENTS: Quick prep, slower digesting carbs, mineral-rich
    SELECT: Roast beef sandwich (beef = minerals, sourdough = low GI carbs, quick)
    RESULT: 560 kcal, 51g protein, 45g carbs, 18g fat
    COVERED: Minerals (manganese, calcium, zinc), slower carbs

SNACK (Pre-workout):
    CONTEXT: Right before workout, need easily digestible carbs
    GAPS: Need quick energy, minimal other nutrients needed
    REQUIREMENTS: Quick carbs, easily digestible
    SELECT: 2 Bananas (simple carbs, quick energy)
    RESULT: 208 kcal, 2g protein, 50g carbs, 1g fat

MEAL 3 (Dinner):
    CONTEXT: Post-workout, long overnight fast ahead, need recovery + satiety
    GAPS: Need Omega-3, various vitamins (A, E, K), minerals (calcium, folate, etc.)
    REQUIREMENTS: High satiety (fiber, protein, volume), complex carbs, micronutrient-dense
    SELECT: Hot Honey Salmon with vegetables (salmon = Omega-3, vegetables = micronutrients, potatoes = satiating carbs)
    RESULT: 738 kcal, 62g protein, 74g carbs, 19g fat
    COVERED: Most remaining micronutrients

VALIDATE:
    - Total: 2263 kcal (within target) ✔️
    - Protein: 166.4g (optimal) ✔️
    - Fat: 78.6g (within range) ✔️
    - Carbs: 204.6g (well-timed) ✔️
    - Micronutrients: Most at or above RDI
    - Carryover: Vitamin E (96%), Magnesium (99%), Manganese (99%)

OUTPUT:
    - Format all meals with reasoning
    - Show total breakdown with percentages
    - Mark carryover needs
    - Flag special cases (Vitamin D, Sodium)
```

---

## NOTES

1. **This is conceptual pseudocode** - not actual implementation code
2. **The reasoning process is iterative** - each meal informs the next
3. **Micronutrients are prioritized** but not at the expense of adding random ingredients
4. **Weekly tracking** allows daily flexibility while ensuring weekly RDIs are met
5. **"To taste" ingredients** are displayed but excluded from calculations
6. **The output format** is flexible and can be adjusted (this pseudocode focuses on the reasoning logic)

