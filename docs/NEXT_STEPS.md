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
## Step 2: Connect Ingredient API (USDA FoodData Central)

### Purpose

This step integrates a **deterministic ingredient lookup pipeline** using the USDA FoodData Central (FDC) API. The goal is to automatically resolve ingredient nutrition data with high accuracy, removing the need for users to manually enter detailed nutrition information for each ingredient.

This step intentionally **does NOT** include a recipe API or advanced NLP parsing. Recipes are user-curated for now. Ingredient accuracy is the foundation that enables later improvements to the meal planner, micronutrient tracking, and scoring logic.

Reference API: USDA FoodData Central
[https://fdc.nal.usda.gov/api-guide](https://fdc.nal.usda.gov/api-guide)

---

### Scope (What This Step Includes)

* Deterministic ingredient lookup by name
* Retrieval of full macro + micronutrient profiles
* Unit-aware quantity scaling
* Internal normalization into app-specific nutrition models
* Caching and explicit error handling

### Non-Goals (Explicitly Out of Scope)

* Recipe API integration
* Natural-language recipe parsing
* Synonym inference or fuzzy matching
* LLM-assisted ingredient resolution

---

## Step 2.1: Ingredient Name Normalization

**Goal:** Prepare parsed ingredient names for reliable API lookup.

Actions:

* Normalize ingredient names (lowercase, trim whitespace)
* Remove controlled descriptors (e.g. "large", "raw", "fresh")
* Ensure output is a deterministic string

Output:

* Canonical ingredient name suitable for API search

---

## Step 2.2: Ingredient Search (USDA API)

**Goal:** Resolve a canonical ingredient name to a single USDA FDC ID.

Actions:

* Call USDA search endpoint using normalized ingredient name
* Filter out branded foods
* Select a single result using deterministic rules (e.g. first non-branded match)

Output:

* Selected `fdcId` for the ingredient

Failure Modes:

* No results found
* Multiple ambiguous results

---

## Step 2.3: Nutrition Data Retrieval

**Goal:** Fetch authoritative nutrition data for the resolved ingredient.

Actions:

* Call USDA food details endpoint using `fdcId`
* Retrieve macro and micronutrient data
* Preserve raw values for mapping

Output:

* Raw USDA nutrition payload

---

## Step 2.4: Nutrient Mapping

**Goal:** Convert USDA nutrient identifiers into internal schema fields.

Actions:

* Maintain a static mapping table (USDA nutrient ID → internal field name)
* Ignore nutrients not tracked by the app
* Convert units where required
* Default missing nutrients to zero

Output:

* Normalized micronutrient + macronutrient dictionary

---

## Step 2.5: Quantity & Unit Scaling

**Goal:** Scale nutrition data to match user-specified quantity and unit.

Actions:

* Define a unit-to-gram conversion table
* Resolve base serving weight (e.g. 1 large egg = 50g)
* Multiply nutrition values by scaled factor

Rules:

* Unknown units must raise explicit errors
* No heuristic guessing

Output:

* Nutrition values adjusted for actual ingredient quantity

---

## Step 2.6: NutritionProfile Construction

**Goal:** Produce a clean internal representation used throughout the app.

Actions:

* Populate `NutritionProfile` with scaled values
* Ensure schema consistency with existing models
* Strip all USDA-specific fields

Output:

* Fully populated `NutritionProfile`

---

## Step 2.7: Caching Layer

**Goal:** Prevent redundant API calls and stabilize tests.

Actions:

* Cache ingredient lookups by normalized name
* Store resolved `fdcId` and normalized nutrition data
* Prefer disk-based cache for development and testing

---

## Step 2.8: Explicit Error Handling

**Goal:** Ensure predictable failure behavior.

Actions:

* Define structured error types (e.g. INGREDIENT_NOT_FOUND, UNIT_NOT_SUPPORTED)
* Fail fast on ambiguity or missing data
* Surface errors to caller without silent fallback

---

## Outcome of Step 2

After completing this step, the system will:

* Reliably convert parsed ingredients into accurate nutrition data
* Support micronutrient-aware meal planning
* Enable UL validation and weekly aggregation
* Provide a stable foundation for future recipe APIs and LLM integration

This step unlocks meaningful refinement of the meal planner algorithm in subsequent phases.

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