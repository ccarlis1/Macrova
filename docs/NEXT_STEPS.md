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
2. Connect ingredient API **IMPLEMENTED**
	- This is very important because it gives the most accurate description of an ingredients full nutrition array
	- Also saves the user a ton of bottleneck not having to manually enter all ingredients for a recipe and their corresponding nutrition info
	- The thought process of no recipe API yet is because its true power is not unlocked without LLM integration, which is a late stage feature, and manually entering recipes is much easier than ingredients
3. Adjust the meal planner to handle micronutrient totals **IMPLEMENTED**

## Step 2: Connect Ingredient API (USDA FoodData Central) **IMPLEMENTED**

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

---

3. Adjust the meal planner to handle micronutrient totals
	3a. Update scoring to consider micronutrients (priority nutrients)
	3b. Update meal planner to track daily micronutrient totals
	3c. Add validation logic for daily micronutrient targets
	3d. Add custom options for meals in each meal slot for both daily and weekly meal generation
		- Example: Monday Breakfast Must be a certain recipe
			- The algorithm cannot ignore this
4. Implement the backtracking portion of the meal planner to handle multiple days, up to a week **IMPLEMENTED**

---

# 4.5. Test multi-day planning with micronutrient carryover
## Purpose

Prove that the planner correctly handles nutrients that accumulate across days, specifically:

* Weekly totals computed correctly
* Partial-day progress handled safely
* Backtracking fully restores micronutrient state
* Failure modes (FM-2, FM-4, TC-3) remain accurate under carryover pressure

This step is less about performance and more about **cross-day correctness under search stress**.

---

# Phase A — Weekly Totals Correctness

## A1. Deterministic happy-path validation

**Goal:** Confirm weekly aggregation is mathematically correct.

### Test shape

* Small D (e.g., 3 or 5)
* Hand-crafted recipes
* Known micronutrient sums
* No backtracking required

### Assertions

For each micronutrient:

```
weekly_totals[nutrient]
==
sum(day_totals[d][nutrient] for d in completed_days)
```

Also verify:

* no negative values
* no double counting
* no missing days

**Why first:** establishes arithmetic trust before stressing search.

---

## A2. Partial-day protection (critical edge)

This targets your earlier bug class.

**Goal:** Ensure incomplete days do NOT affect weekly totals.

### Scenario

Construct cases where:

* day starts assignment
* day never completes
* search backtracks away

### Assertions

* weekly_totals unchanged
* completed_days set accurate
* no subtraction artifacts
* no negative drift

This is one of the highest-value tests in Step 4.5.

---

## A3. Carryover sufficiency tests

**Goal:** Verify weekly RDI logic behaves correctly.

Create three canonical profiles.

### Case 1 — Exact meet

Weekly micronutrients land exactly on prorated RDI.

Expect:

* success (TC-1)
* no FM-4
* no warning

---

### Case 2 — Marginal deficit

Weekly slightly below RDI.

Expect:

* FM-4 triggered
* “marginal vs structural” classification correct
* closest plan reported properly

---

### Case 3 — Structural deficit

Impossible to meet even with all recipes.

Expect:

* early FM-4 or TC-3
* correct diagnostic messaging
* search does not thrash excessively

---

# Phase B — Edge Case Stress

Now you intentionally stress the carryover math.

---

## B1. Front-loaded surplus

**Pattern:** early days massively oversupply a micronutrient.

**Goal:** Ensure:

* no artificial caps
* no overflow/precision issues
* later days not forced incorrectly

Watch for:

* numeric overflow
* pruning mistakes
* incorrect “already satisfied” logic

---

## B2. Late recovery scenario

**Pattern:**

* early days deficient
* only late recipes can fix weekly RDI

This is a classic backtracking trap.

**Goal:** Verify search can recover.

Assertions:

* planner does not prematurely fail FM-4
* backtracking explores recovery paths
* best-plan reporting correct if still infeasible

---

## B3. Knife-edge feasibility

Design a case where:

* exactly one valid weekly combination exists
* requires deep backtracking

This validates:

* cross-day reasoning
* pruning correctness
* search completeness (within budget)

---

# Phase C — Backtracking Integrity (High Value)

This is the most important part of Step 4.5.

---

## C1. Micronutrient state restoration

Instrument snapshots.

### During search

At each backtrack:

```
snapshot_before
apply
recurse
undo
snapshot_after
```

### Assert

```
snapshot_before == snapshot_after
```

for:

* daily trackers
* weekly tracker
* completed_days
* sodium totals

If this fails, you have silent corruption.

---

## C2. Pinned interaction with carryover

Combine two hard features.

**Scenario:**

* pinned meals provide key micronutrients
* backtracking occurs around them

Verify:

* pinned nutrition never removed
* weekly totals remain stable
* FM-3 reporting still correct

---

## C3. Deep backtrack scenario

Force:

* many assignments
* multiple day completions
* then deep unwind

Watch for:

* weekly totals drift
* completed_days corruption
* double subtraction

This catches subtle accounting bugs.

---

# Phase D — Failure Mode Validation Under Carryover

Now verify your Phase 10 work holds under pressure.

---

## D1. FM-2 with weekly context

Create cases where:

* daily macros fine
* weekly micronutrients fail

Verify report includes:

* specific deficient micronutrients
* achieved vs prorated RDI
* closest-to-valid plan

---

## D2. FM-4 classification accuracy

Test both:

* marginal deficiency
* structural impossibility

Ensure classification logic is correct and stable.

---

## D3. TC-3 exhaustion under micronutrient pressure

Force search exhaustion due to micronutrient coupling.

Verify report includes:

* attempts/backtracks
* best plan
* validation failures
* non-exhaustive indication

---

# Phase E — Statistical Confidence Pass (light fuzz)

Before moving to heavy fuzzing.

Run ~200–500 randomized tests with:

* varied D
* varied recipe pools
* random pins
* random micronutrient tightness

Track:

* invariant violations
* unexpected FM distributions
* runtime spikes

This is your early warning system.

---

# Exit Criteria for Step 4.5

You are ready to move on when:

* weekly totals always match summed days
* incomplete days never affect weekly totals
* backtracking perfectly restores micronutrient state
* FM-2 / FM-4 reports remain accurate
* pinned assignments remain invariant
* knife-edge feasibility cases succeed
* no negative or drifting totals observed
* randomized pass shows zero invariant violations

---

5. Create a simple, lightweight frontend portion of the app, mainly for open testing purposes. No web integration just yet

---

## CURRENT STEP: 4.5
## Upper Tolerable Intake (UL) schema

Field names match `MicronutrientProfile` / `WeeklyNutritionTargets`. ULs are **daily** values (IOM/EFSA). Validation: each day's total must not exceed the daily UL for that nutrient.

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

1. **Resolve ULs for user:** Load reference ULs for the user's demographic (from profile, e.g. `demographic: adult_male`). Override any nutrient present in `upper_limits` with the user's value.
2. **Validation (weekly plan):** For each day in the plan, for each nutrient that has a non-null UL, ensure `day_total[nutrient] <= resolved_ul[nutrient]`. If any day exceeds, fail or filter that combination (e.g. avoid multiple high–vitamin A meals like liver).
3. **Data layer:** Add a model (e.g. `UpperLimits` or `DailyNutritionLimits`) with the same field names as `MicronutrientProfile`; populate from reference + user overrides for the active user.

---

## CURRENT STEP: 3
