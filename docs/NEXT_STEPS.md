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
3. Adjust the meal planner to handle micronutrient totals **IMPLEMENTED**
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