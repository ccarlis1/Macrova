# Changes Summary - Reasoning Logic Updates

## What I Know

Based on KNOWLEDGE.md and the reasoning logic pseudocode, the Nutrition Agent must:

1. **Generate meals iteratively** - Each meal informs the next based on nutrient gaps
2. **Prioritize micronutrients** - Weekly RDIs must be met, daily flexibility allowed
3. **Consider activity context** - Pre/post-workout timing affects macro distribution
4. **Respect schedule constraints** - Busyness levels (1-4) determine cooking time limits
5. **Manage satiety** - Long fasts require high-satiety meals, frequent meals need balanced satiety
6. **Exclude "to taste" ingredients** - Display them but don't calculate nutrition
7. **Track weekly totals** - Running totals ensure weekly RDIs are met

## Changes Made to REASONING_LOGIC.md

### 1. Post-Workout Window Extension
- **Changed**: Post-workout context window from "within 2 hours" to "within 3 hours"
- **Rationale**: Longer window for post-workout meal planning

### 2. Preworkout Meal Clarification
- **Changed**: Clarified preworkout carb requirements
- **Key Points**:
  - Amount of carbs matters more than complexity (fast/medium digesting OK)
  - Should be **low fiber, low fat, medium-low protein**
  - Purpose: Maximize carb absorption into muscle glycogen
  - Not just "easily digestible" - specific macro profile needed

### 3. Sedentary Carb Minimization
- **Changed**: Added constraint to prevent over-minimization on non-training days
- **Key Points**:
  - Don't prioritize low carb for ALL meals on non-training days
  - Still need to hit daily carb target
  - This condition shouldn't overpower the daily target condition
  - Balance: Avoid blood sugar spikes while meeting daily needs

### 4. Protein Distribution Exception
- **Changed**: Added exception for pre/post-workout meals
- **Key Points**:
  - Preworkout meals: **SLIGHTLY less protein**
  - Postworkout meals: **SLIGHTLY more protein**
  - All other meals: Distribute relatively evenly

### 5. Satiety/Long Fast Clarification
- **Changed**: Expanded definition and added calorie requirement
- **Key Points**:
  - Long fast = 12 hours overnight OR meal timing gap > 4 hours
  - Meal should have **more calories** (bigger meal)
  - High fiber, protein, volume, low calorie density
  - Bigger meal = more calories if not eating for a long time

### 6. "To Taste" and Seasoning Handling (Future)
- **Changed**: Added extensive note about future recipe API integration
- **Key Points**:
  - Most seasonings shouldn't be counted for micronutrients
  - But still output exact measurements for cooking (e.g., "1 tbsp ground turmeric")
  - Complex rule: Can't use simple weight threshold
  - Example: 1 tbsp turmeric = negligible, but 1 tbsp sunflower oil = 120 cal + nutrients
  - This requires ingredient-specific logic, not blanket rules

## Impact on Pseudocode

These changes affect:
1. **Activity Context Detection** - Post-workout window extended
2. **Carb Timing Requirements** - Preworkout needs specific macro profile
3. **Sedentary Meal Planning** - Balance between minimizing spikes and meeting daily targets
4. **Macro Distribution** - Pre/post-workout protein adjustments
5. **Satiety Calculation** - Expanded definition and calorie requirement
6. **Nutrition Calculation** - Future complexity for seasonings (post-MVP)

## Next Steps

Update REASONING_LOGIC.md to integrate these notes properly into the pseudocode structure.

