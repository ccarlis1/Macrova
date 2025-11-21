# Design Understanding Summary

## Authoritative Reference
**KNOWLEDGE.md** is the authoritative source for nutrition logic, meal generation rules, and implementation requirements.

## Key Design Principles from KNOWLEDGE.md

### 1. Calories (Line 6)
- Maintenance calories: ~2800 (user-specific)
- Target for deficit: 2400 calories/day for 6 out of 7 days
- Weekly cheat meal accommodation: eat less on non-cheat days

### 2. Macronutrients (Lines 8-10)
- **Protein**: 0.6-0.9g per pound bodyweight daily, weekly average 0.7-0.8g/lb
- **Fats**: 50-100g daily range, weekly median ~75g
  - Priority: Fat diversity (don't rely on single sources)
  - Minimum to meet micronutrient RDIs + hormone health
- **Carbs**: Calculated as remainder after protein/fat
  - Timing matters: easily digestible pre-workout, complex carbs for satiety
  - Prioritize micronutrient-rich carb sources

### 3. Micronutrients (Line 12)
- RDIs calculated based on **maintenance calories** (not deficit calories)
- Daily flexibility allowed, but **weekly totals must meet RDIs**
- Prefer going over weekly RDI rather than under
- Don't add random ingredients just to hit micronutrient targets

### 4. Meal Generation Factors (Lines 15-18)

#### Time Constraints (Line 15)
- Busyness scale: 1-4
  - 1 = snack (< 5 min)
  - 2 = quick meal (≤ 15 min)
  - 3 = weeknight meal (≤ 30 min)
  - 4 = weekend/meal prep (30+ min)

#### Satiety (Line 16)
- User-specified requirements
- For long overnight fasts: increase fiber, protein, volume (low calorie density)
- For frequent meals: balance satiety evenly throughout day

#### Taste Preferences (Line 17) ⭐ **UPDATED**
- User can specify liked/disliked foods, allergies
- Can specify dietary patterns (e.g., Mediterranean diet)
- **CRITICAL RULE**: Ingredients marked "to taste" are:
  - ✅ **Included** in recipe display and instructions
  - ❌ **Excluded** from nutrition calculations
  - Examples: salt, garnishes (green onion), salsa "to taste"
  - Rationale: Negligible nutritional value, amounts vary by preference

#### Meal Prep (Line 18)
- Post-MVP feature
- User specifies pre-planned meals (e.g., "5 servings of chili this week")
- System adjusts other meals to account for pre-planned meal nutrition
- Example: If chili is high in fiber, reduce fiber in other meals

## Implementation Decisions Based on KNOWLEDGE.md

### Data Models
- `Ingredient` model includes `is_to_taste: bool` flag
- Ingredients with `is_to_taste=True` are excluded from nutrition calculations

### Ingredient Parser
- Must detect "to taste" pattern in ingredient strings
- Mark ingredients appropriately with `is_to_taste` flag
- Examples:
  - `"salt to taste"` → `is_to_taste=True`
  - `"green onion to taste"` → `is_to_taste=True`
  - `"salsa to taste"` → `is_to_taste=True`

### Nutrition Calculator
- **Filter step**: Skip all ingredients where `is_to_taste=True`
- Only calculate nutrition for measured ingredients
- This ensures accuracy while simplifying calculations

### Recipe Display
- "To taste" ingredients are still shown in recipe output
- They appear in ingredient lists and instructions
- But they don't contribute to nutrition totals

## Example from KNOWLEDGE.md

From README.md example (Mexican-Style Breakfast Scramble):
- Ingredients include: "Salsa and green onion to taste"
- These are displayed in the recipe
- But nutrition breakdown only includes:
  - 5 large eggs
  - 175g potatoes
  - 50g red peppers
  - 40g raw spinach
  - 1oz sharp cheddar cheese
  - 3oz lean turkey sausage
  - 50g pinto beans
  - 2 tsp olive oil
- Salsa and green onion are excluded from nutrition calculation

## Updated Design Documents

The following documents have been updated to reflect the "to taste" handling:

1. **TECHNICAL_DESIGN.md**:
   - Updated `Ingredient` model to include `is_to_taste` flag
   - Updated Ingredient Parser specification
   - Updated Nutrition Calculator to filter "to taste" ingredients

2. **IMPLEMENTATION_PLAN.md**:
   - Added "to taste" detection to Step 2.1 (Ingredient Parsing)
   - Added filtering requirement to Step 2.2 (Nutrition Calculation)

3. **Example Files**:
   - `data/recipes/recipes.json.example` already correctly includes "to taste" ingredients

## Design Consistency

All design decisions align with KNOWLEDGE.md:
- ✅ Weekly nutrient tracking (running totals) - Line 12
- ✅ Daily flexibility with weekly requirements - Line 12
- ✅ Busyness scale (1-4) - Line 15
- ✅ Satiety considerations - Line 16
- ✅ "To taste" ingredient exclusion - Line 17 ⭐
- ✅ Meal prep integration (post-MVP) - Line 18

## Next Steps

The design is now fully aligned with KNOWLEDGE.md. Ready to proceed with implementation following IMPLEMENTATION_PLAN.md.

