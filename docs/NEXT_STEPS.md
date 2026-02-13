# Next Steps

## Separate MVP
Currently, the scope of the MVP is decent, but I think it should be slightly restructured. The Current MVP scope seems too primitive to be called a unique product. So what I shall do is separate the MVP into two parts, an alpha stage and a true MVP stage, to account for this

### Alpha Stage
	- Completed

### True MVP (User-Facing Validation)
1. Refine Data Layer to ensure micronutrient information for an ingredient and all associated data types is integrated
	1a. Extend data models Ex/ (NutritionProfile, NutritionGoals, UserProfile)
	1b. Update NutritionCalculator to calculate micronutrients
	1c. Update NutritionAggregator to aggregate micronutrients
	1d. Add weekly tracking data structures
	1e. ✅ Include maximum tolerable intake handling for micronutrients. **IMPLEMENTED**
		- **Status:** Data structures, reference loading, and daily validation complete
		- **Key constraint:** ULs are DAILY limits — enforced per-day, never averaged
		- Weekly tracking does NOT weaken daily UL enforcement
		- **Components:** `UpperLimits`, `UpperLimitsLoader`, `resolve_upper_limits()`, `validate_daily_upper_limits()`, `ULViolation`
		- **Tests:** 34 unit tests in `tests/test_upper_limits.py`
		- **Pending:** Integration with `MealPlanner` (requires Step 1b first)
	1e-original. Original requirement for reference:
		- This value should be calculated for every nutrient based on RDIs for each individual
		- The idea is that when a weekly meal plan is generated, no nutrient should be in the maximum tolerable intake value whatsoever, to avoid risk of poisoning
		- Most nutrients are exempt from this, however certain upper intake thresholds could be dangerous for some nutrients (Ex. Vitamin A)
			- For example if multiple recipes generated use liver, this could put the person at risk for vitamin A poisioning. To combat this, the algorithm should filter such combinations out, and that upper tolerable intake should be stored in the data layer.
		- **Schema (reference + user overrides):**
			- **Reference:** `data/reference/ul_by_demographic.json` — authoritative daily ULs by demographic (IOM/EFSA). Field names match `MicronutrientProfile`; use `null` for nutrients with no established UL.
			- **User overrides:** Optional `upper_limits` section in `user_profile.yaml` — same field names; only include nutrients to override. User value overrides reference for that nutrient.
			- **Resolution:** Look up reference by user demographic (e.g. `adult_male`, `adult_female`, `pregnancy`, `lactation`); merge in user overrides; use result for validation (each day’s total must not exceed daily UL).
			- See **Upper Tolerable Intake (UL) schema** below for concrete formats.
2. Connect ingredient API **IMPLEMENTED**
	- This is very important because it gives the most accurate description of an ingredients full nutrition array
	- Also saves the user a ton of bottleneck not having to manually enter all ingredients for a recipe and their corresponding nutrition info
	- The thought process of no recipe API yet is because its true power is not unlocked without LLM integration, which is a late stage feature, and manually entering recipes is much easier than ingredients
3. Adjust the meal planner to handle micronutrient totals
	3a. Update scoring to consider micronutrients (priority nutrients)
	3b. Update meal planner to track daily micronutrient totals
	3c. Add validation logic for daily micronutrient targets
	3d. Add custom options for meals in each meal slot for both daily and weekly meal generation
		- Example: Monday Breakfast Must be a certain recipe
			- The algorithm cannot ignore this
4. Implement the backtracking portion of the meal planner to handle multiple days, up to a week
4.5. Test multi-day planning with micronutrient carryover
    - Verify weekly totals are met
    - Test edge cases (deficits, surpluses)
    - Validate backtracking logic
5. Create a simple, lightweight frontend portion of the app, mainly for open testing purposes. No web integration just yet

---

## CURRENT STEP: 3