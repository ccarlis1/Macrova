# Nutrition Agent – Hard Constraints

## Ingredient Handling
- Ingredients marked "to taste" MUST:
  - Appear in recipe output
  - Be excluded from all macro and micronutrient calculations
  - Be flagged as is_to_taste = true in parsed output

## Nutrition Calculation
- Only ingredients with explicit quantities contribute to nutrition totals
- Daily totals are the sum of meal totals
- Weekly micronutrient logic may allow daily variance but MUST meet weekly RDI

## Meal Planning
- A recipe may not appear more than once in a single day
- Meal slots are ordered and deterministic
- Tests define expected behavior over prose examples

## Scoring
- Low-fat meals are allowed when explicitly tagged as pre-workout
- Preference scoring MUST NOT override nutrition feasibility
