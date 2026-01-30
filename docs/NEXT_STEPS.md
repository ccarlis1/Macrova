# Next Steps

## Separate MVP
Currently, the scope of the MVP is decent, but I think it should be slightly restructured. The Current MVP scope seems too primitive to be called a unique product. So what I shall do is separate the MVP into two parts, an alpha stage and a true MVP stage, to account for this

### Alpha Stage
**TODO:** Nearly complete
- Integration/Testing

### True MVP (User-Facing Validation)
1. Refine Data Layer to ensure micronutrient information for an ingredient and all associated data types is integrated
	1a. Extend data models Ex/ (NutritionProfile, NutritionGoals, UserProfile)
	1b. Update NutritionCalculator to calculate micronutrients
	1c. Update NutritionAggregator to aggregate micronutrients
	1d. Add weekly tracking data structures
2. Connect ingredient API
	- This is very important because it gives the most accurate description of an ingredients full nutrition array
	- Also saves the user a ton of bottleneck not having to manually enter all ingredients for a recipe and their corresponding nutrition info
	- The thought process of no recipe API yet is because its true power is not unlocked without LLM integration, which is a late stage feature, and manually entering recipes is much easier than ingredients
3. Adjust the meal planner to handle micronutrient totals
	3a. Update scoring to consider micronutrients (priority nutrients)
	3b. Update meal planner to track daily micronutrient totals
	3c. Add validation logic for daily micronutrient targets
4. Implement the backtracking portion of the meal planner to handle multiple days, up to a week
4.5. Test multi-day planning with micronutrient carryover
    - Verify weekly totals are met
    - Test edge cases (deficits, surpluses)
    - Validate backtracking logic
5. Create a simple, lightweight frontend portion of the app, mainly for open testing purposes. No web integration just yet