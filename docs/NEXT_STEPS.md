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
	1e. Include maximum tolerable intake handling for micronutrients.
		- This value should be calculated for every nutrient based on RDIs for each individual
		- The idea is that when a weekly meal plan is generated, no nutrient should be in the maximum tolerable intake value whatsoever, to avoid risk of poisoning
		- Most nutrients are exempt from this, however certain upper intake thresholds could be dangerous for some nutrients (Ex. Vitamin A)
			- For example if multiple recipes generated use liver, this could put the person at risk for vitamin A poisioning. To combat this, the algorithm should filter such combinations out, and that upper tolerable intake should be stored in the data layer.
		- **Schema (reference + user overrides):**
			- **Reference:** `data/reference/ul_by_demographic.json` — authoritative daily ULs by demographic (IOM/EFSA). Field names match `MicronutrientProfile`; use `null` for nutrients with no established UL.
			- **User overrides:** Optional `upper_limits` section in `user_profile.yaml` — same field names; only include nutrients to override. User value overrides reference for that nutrient.
			- **Resolution:** Look up reference by user demographic (e.g. `adult_male`, `adult_female`, `pregnancy`, `lactation`); merge in user overrides; use result for validation (each day’s total must not exceed daily UL).
			- See **Upper Tolerable Intake (UL) schema** below for concrete formats.
2. Connect ingredient API
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

## Upper Tolerable Intake (UL) schema

Field names match `MicronutrientProfile` / `WeeklyNutritionTargets`. ULs are **daily** values (IOM/EFSA). Validation: each day’s total must not exceed the daily UL for that nutrient.

### 1. Reference: `data/reference/ul_by_demographic.json`

Authoritative daily ULs by demographic. Source: IOM DRI tables (e.g. NIH ODS) or EFSA. Use `null` for nutrients with no established UL (e.g. vitamin K, thiamine, riboflavin, B12, potassium from food).

```json
{
  "source": "IOM DRI",
  "note": "Values are DAILY upper limits. Units match MicronutrientProfile.",
  "demographics": {
    "adult_male": {
      "vitamin_a_ug": 3000,
      "vitamin_c_mg": 2000,
      "vitamin_d_iu": 4000,
      "vitamin_e_mg": 1000,
      "vitamin_k_ug": null,
      "b1_thiamine_mg": null,
      "b2_riboflavin_mg": null,
      "b3_niacin_mg": 35,
      "b5_pantothenic_acid_mg": null,
      "b6_pyridoxine_mg": 100,
      "b12_cobalamin_ug": null,
      "folate_ug": 1000,
      "calcium_mg": 2500,
      "copper_mg": 10,
      "iron_mg": 45,
      "magnesium_mg": 350,
      "manganese_mg": 11,
      "phosphorus_mg": 4000,
      "potassium_mg": null,
      "selenium_ug": 400,
      "sodium_mg": null,
      "zinc_mg": 40,
      "fiber_g": null,
      "omega_3_g": null,
      "omega_6_g": null
    },
    "adult_female": {
      "vitamin_a_ug": 3000,
      "vitamin_c_mg": 2000,
      "vitamin_d_iu": 4000,
      "vitamin_e_mg": 1000,
      "vitamin_k_ug": null,
      "b3_niacin_mg": 35,
      "b6_pyridoxine_mg": 100,
      "folate_ug": 1000,
      "calcium_mg": 2500,
      "copper_mg": 10,
      "iron_mg": 45,
      "magnesium_mg": 350,
      "manganese_mg": 11,
      "phosphorus_mg": 4000,
      "selenium_ug": 400,
      "zinc_mg": 40
    },
    "pregnancy": {},
    "lactation": {}
  }
}
```

- Extend `demographics` with more keys as needed (e.g. `pregnancy`, `lactation`, age bands).
- Omitted fields in a demographic can default to `null` (no UL).

### 2. User overrides: `upper_limits` in `user_profile.yaml`

Optional. Only include nutrients the user (or clinician) wants to override. Same field names and units as `MicronutrientProfile`. These override the reference value for that user.

```yaml
# user_profile.yaml (excerpt)

nutrition_goals:
  daily_calories: 2400
  daily_protein_g: 138
  daily_fat_g: { min: 65, max: 85 }
  # ... other goals ...

# OPTIONAL: Override upper tolerable intake (UL) for specific nutrients.
# Only list nutrients to override; others use reference UL from ul_by_demographic.json.
# Units match MicronutrientProfile (e.g. vitamin_a_ug, vitamin_d_iu, iron_mg).
# Example: clinician sets lower vitamin A cap due to liver concern.
upper_limits:
  vitamin_a_ug: 2000
  # vitamin_d_iu: 2000
  # folate_ug: 800
```

### 3. Resolution and validation

1. **Resolve ULs for user:** Load reference ULs for the user’s demographic (from profile, e.g. `demographic: adult_male`). Override any nutrient present in `upper_limits` with the user’s value.
2. **Validation (weekly plan):** For each day in the plan, for each nutrient that has a non-null UL, ensure `day_total[nutrient] <= resolved_ul[nutrient]`. If any day exceeds, fail or filter that combination (e.g. avoid multiple high–vitamin A meals like liver).
3. **Data layer:** Add a model (e.g. `UpperLimits` or `DailyNutritionLimits`) with the same field names as `MicronutrientProfile`; populate from reference + user overrides for the active user.