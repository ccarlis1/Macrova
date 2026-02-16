# Meal Plan Formal Algorithm Specification

**Scope:** Steps 3 and 4 of NEXT_STEPS.md — micronutrient-aware scoring, daily tracking, validation, pinned meal slots, and multi-day backtracking (up to 7 days).

**Authoritative References:** SYSTEM_RULES.md, REASONING_LOGIC.md, KNOWLEDGE.md, NEXT_STEPS.md.

**Convention:** This document uses "shall" for normative requirements and "should" for recommendations. Items marked **REQUIRES CLARIFICATION** denote underspecified behavior in the authoritative references that must be resolved before implementation.

---

## 1. Problem Definition

Given a user profile U, a finite recipe pool R, and a planning horizon of D days (1 ≤ D ≤ 7), produce a complete meal plan P that assigns exactly one recipe to every meal slot across all D days such that:

1. Every hard constraint (Section 4) is satisfied.
2. Each day's macronutrient totals fall within defined tolerances of the daily targets.
3. Each day's micronutrient totals do not exceed any applicable Upper Tolerable Intake (UL).
4. The aggregate of all micronutrients across the D planned days meets or exceeds the prorated RDI target for each tracked micronutrient (see Section 6.6).
5. Among all valid plans, the plan selected is the one found first by the search strategy (Section 6), which uses a score-maximizing heuristic at every decision point.

The algorithm is **deterministic**: identical inputs shall produce identical output. The algorithm uses a **greedy** selection strategy with **chronological backtracking** to explore the assignment space.

---

## 2. Inputs

### 2.1 User Profile (U)

| Field | Type | Description |
|---|---|---|
| `daily_calories` | int | Daily calorie target (kcal) |
| `daily_protein_g` | float | Daily protein target (grams) |
| `daily_fat_g` | (float, float) | Daily fat range (min, max) in grams |
| `daily_carbs_g` | float | Daily carbohydrate target (grams); derived as `(daily_calories - protein*4 - fat_median*9) / 4` |
| `max_daily_calories` | Optional[int] | Hard daily calorie ceiling (Calorie Deficit Mode). When set, any day exceeding this value is invalid. |
| `schedule` | see 2.1.1 | Ordered meal slot definitions per day |
| `excluded_ingredients` | List[str] | Ingredients that shall never appear in any assigned recipe. This single list encompasses both allergens and strongly disliked foods — the algorithm treats them identically as hard exclusions (see Section 4, HC-1). |
| `liked_foods` | List[str] | Ingredients the user prefers. Used as a tie-breaking signal (see Section 7.1), not as a scoring component. |
| `demographic` | str | Demographic category for UL reference lookup (e.g., `adult_male`) |
| `upper_limits_overrides` | Optional[Dict[str, float]] | Per-nutrient UL overrides (replaces reference value for that nutrient) |
| `pinned_assignments` | Dict[(day, slot), recipe_id] | Meal slots with mandatory recipe assignments (Section 4, HC-6) |
| `micronutrient_targets` | Dict[str, float] | Daily RDI targets for each tracked micronutrient, keyed by nutrient name. Only nutrients present in this dictionary participate in scoring, carryover tracking, and weekly validation. Nutrients the user does not wish to track (e.g., Vitamin D if obtained via supplementation) are simply omitted. |
| `activity_schedule` | Dict[str, str] | Activity entries (e.g., workout times) used to derive activity context per slot |

**Design note — `excluded_ingredients`:** This field replaces the previously separate `allergies` and `disliked_foods` lists. The rationale is that both categories produce identical algorithmic behavior (hard exclusion from candidate generation). The user-facing label should communicate that this list is for ingredients the user cannot or will not eat, for any reason.

**Design note — `micronutrient_targets`:** This field replaces a prior `nutrient_exemptions` list. Rather than tracking all known micronutrients and exempting some, the system only tracks what the user explicitly targets. If a micronutrient is not relevant to the user's dietary goals (e.g., Vitamin D obtained from sun/supplementation), it is omitted from this dictionary and the algorithm has no awareness of it for scoring or validation purposes. UL enforcement (Section 4, HC-4) is independent — a nutrient may have a UL even if it is not in `micronutrient_targets`.

#### 2.1.1 Schedule Structure

The schedule defines, for each day in the planning horizon, an ordered sequence of meal slots. Each day may define a distinct set of meal slots (e.g., weekday vs. weekend schedules). Each slot is defined by:

| Field | Type | Description |
|---|---|---|
| `time` | str (HH:MM) | Scheduled meal time |
| `busyness_level` | int (1–4) | Cooking time constraint for this slot |
| `meal_type` | str | Label (e.g., "breakfast", "lunch", "snack", "dinner") |

Meal slots within a day are ordered chronologically by `time`. The ordering is strict and deterministic (Source: SYSTEM_RULES.md — "Meal slots are ordered and deterministic").

The maximum number of meal slots per day is **8**. A day with zero slots is not permitted (every day in the planning horizon must have at least one slot).

#### 2.1.2 Derived Slot Attributes

For each meal slot, the following attributes are derived from the user profile and schedule at plan time (not stored as input):

- **`activity_context`**: A set drawn from {`pre_workout`, `post_workout`, `sedentary`, `overnight_fast_ahead`}, derived as:
  - `pre_workout`: a workout begins within 2 hours after this slot's time
  - `post_workout`: a workout ended within 3 hours before this slot's time
  - `sedentary`: no workout within the above windows
  - `overnight_fast_ahead`: the time until the next meal slot (or end of day) exceeds 4 hours, OR the slot is the last slot of the day and the overnight fast is ≥ 12 hours
  - (Source: REASONING_LOGIC.md, Step 1)
  - **Note:** A slot may carry multiple context flags simultaneously (e.g., `post_workout` AND `overnight_fast_ahead`).

- **`is_workout_slot`**: Boolean, derived as `true` if `activity_context` contains `pre_workout` or `post_workout`; `false` otherwise. Used by HC-8 (consecutive-day repetition constraint).

- **`time_until_next_meal`**: Duration in hours until the next meal slot on the same day, or until the first slot of the next day if this is the last slot.

- **`satiety_requirement`**: One of {`high`, `moderate`}, derived as:
  - `high`: if `time_until_next_meal` > 4 hours OR overnight fast ≥ 12 hours
  - `moderate`: otherwise
  - (Source: REASONING_LOGIC.md, Rule 4)

- **`cooking_time_max`**: Maximum cooking time in minutes, derived from `busyness_level`:
  - 1 → 5 minutes
  - 2 → 15 minutes
  - 3 → 30 minutes
  - 4 → no upper bound
  - (Source: REASONING_LOGIC.md, Rule 3)

### 2.2 Recipe Pool (R)

A finite, non-empty set of Recipe objects. Each recipe r ∈ R has:

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique identifier |
| `name` | str | Recipe name |
| `ingredients` | List[Ingredient] | Ingredient list; "to taste" ingredients have `is_to_taste=True` and are excluded from nutrition |
| `cooking_time_minutes` | int | Total preparation and cooking time |
| `nutrition` | NutritionProfile | Pre-computed macronutrient and micronutrient totals (excluding "to taste" ingredients) |

**Input Assumption:** All recipe nutrition profiles are pre-computed before the algorithm begins. The algorithm does not perform nutrition calculation during planning; it reads nutrition as a property of each recipe.

### 2.3 Reference Data

- **Upper Tolerable Intake (UL) Table:** Daily ULs by demographic, loaded from `data/reference/ul_by_demographic.json`. Merged with user overrides (user value replaces reference value per nutrient). A `null` value for a nutrient means no UL is established; that nutrient is exempt from UL validation.

- **Micronutrient RDI Reference:** Daily RDI targets per micronutrient, as defined by `U.micronutrient_targets`. Weekly targets are computed as `daily_RDI × D` (prorated to the planning horizon). Daily RDIs are based on maintenance calories (not deficit calories). (Source: KNOWLEDGE.md)

### 2.4 Planning Horizon

- **D**: Number of days to plan, where 1 ≤ D ≤ 7.
- **Total slots**: The sum of meal slots across all D days. Let N = total number of decision points (slots) across the plan.

---

## 3. State Representation

At any point during the search, the algorithm state S is defined as:

### 3.1 Assignment Sequence

**`assignments`**: An ordered list of tuples `(day, slot_index, recipe_id)` representing all recipe-to-slot assignments made so far. The length of this list equals the number of decisions made. The ordering corresponds exactly to the decision order defined in Section 6.1.

### 3.2 Daily Trackers

For each day d (1 ≤ d ≤ D) that has at least one assignment, a daily tracker `T_d` contains:

| Field | Type | Description |
|---|---|---|
| `calories_consumed` | float | Sum of calories from all recipes assigned to day d so far |
| `protein_consumed` | float | Sum of protein (g) |
| `fat_consumed` | float | Sum of fat (g) |
| `carbs_consumed` | float | Sum of carbs (g) |
| `micronutrients_consumed` | Dict[str, float] | Sum of each tracked micronutrient from all recipes assigned to day d so far |
| `used_recipe_ids` | Set[str] | Set of recipe IDs assigned to day d so far |
| `non_workout_recipe_ids` | Set[str] | Subset of `used_recipe_ids`: only recipes assigned to slots where `is_workout_slot = false`. Used to enforce HC-8. |
| `slots_assigned` | int | Number of slots assigned for day d |
| `slots_total` | int | Total number of slots for day d |

### 3.3 Weekly Tracker

A single weekly tracker `W` contains:

| Field | Type | Description |
|---|---|---|
| `weekly_totals` | NutritionProfile | Aggregate nutrition across all fully completed days plus the current partial day |
| `days_completed` | int | Number of days that have been fully planned and validated |
| `days_remaining` | int | D − `days_completed` |
| `carryover_needs` | Dict[str, float] | For each tracked micronutrient: the accumulated deficit that must be compensated by remaining days. Computed as `max(0, (daily_RDI × days_completed) − weekly_totals[nutrient])` |

### 3.4 Adjusted Daily Micronutrient Targets

At the start of each day d, the per-day micronutrient targets are adjusted to account for accumulated deficits:

For each tracked micronutrient `n` (i.e., `n ∈ U.micronutrient_targets`):
- `base_daily_target(n) = U.micronutrient_targets[n]`
- `adjusted_daily_target(n) = base_daily_target(n) + (carryover_needs(n) / days_remaining)`

Where `days_remaining` includes the current day.

(Source: REASONING_LOGIC.md, Initialization Phase)

### 3.5 Initial State

The initial state S₀ is constructed as follows:

1. `assignments` is initialized with all pinned assignments (HC-6). Pinned assignments are inserted at their corresponding positions in the decision order.
2. Daily trackers for days with pinned assignments are initialized with the nutrition from those pinned recipes. `non_workout_recipe_ids` is populated based on whether each pinned slot's `is_workout_slot` is false.
3. Weekly tracker is initialized at zero, then updated with nutrition from pinned recipes.
4. All non-pinned decision points are unassigned.

**Pinned assignment pre-validation:** Before the search begins, all pinned assignments shall be validated against hard constraints. If any pinned recipe violates HC-1 (excluded ingredient), HC-3 (cooking time), HC-5 (would single-handedly exceed calorie ceiling), or HC-8 (consecutive-day non-workout repetition with another pinned assignment), the algorithm shall reject immediately with failure mode FM-3 (Section 11) without entering the search.

### 3.6 Per-Meal Target Distribution

At each decision point `(d, s)`, the algorithm computes a **per-meal target** that represents the ideal nutritional contribution of the recipe to be assigned. This target is derived by distributing the day's remaining nutritional budget across the remaining unassigned slots for that day:

- `remaining_calories = daily_calories − T_d.calories_consumed`
- `remaining_protein = daily_protein_g − T_d.protein_consumed`
- `remaining_fat_max = daily_fat_g.max − T_d.fat_consumed`
- `remaining_carbs = daily_carbs_g − T_d.carbs_consumed`
- `slots_left = T_d.slots_total − T_d.slots_assigned` (including the current slot)

Base per-meal target = remaining / slots_left, with the following adjustments for activity context:

| Context | Adjustment |
|---|---|
| `pre_workout` | Protein reduced (factor < 1.0); carbs increased (factor > 1.0); prefer low fiber, low fat macro profile |
| `post_workout` | Protein increased (factor > 1.0); carbs increased (factor > 1.0) |
| `high satiety` | Calories increased; protein increased; fat increased |
| default | Even distribution |

(Source: REASONING_LOGIC.md, Rule 2 and Step 3)

The exact multiplicative factors (e.g., 0.8× protein for pre-workout, 1.2× for post-workout) are defined by the current implementation and are considered normative. The specification requires these adjustments to exist with the relative ordering shown above.

---

## 4. Hard Constraints

A hard constraint violation renders the assignment (or plan) **invalid**. The algorithm shall never produce output that violates a hard constraint.

### HC-1: Ingredient Exclusion

No recipe assigned to any slot shall contain an ingredient matching any entry in `U.excluded_ingredients`. Matching is performed on normalized ingredient names.

This constraint encompasses both allergens and strongly disliked foods. The algorithm makes no distinction between reasons for exclusion — all entries in `excluded_ingredients` are treated as absolute prohibitions.

### HC-2: Recipe Uniqueness Per Day

For any single day d, no recipe ID shall appear more than once across all meal slots of day d.

(Source: SYSTEM_RULES.md — "A recipe may not appear more than once in a single day")

### HC-3: Cooking Time

For each meal slot with derived `cooking_time_max` (from busyness level), the assigned recipe's `cooking_time_minutes` shall not exceed `cooking_time_max`.

Busyness level 4 has no upper bound; any cooking time is permitted.

(Source: REASONING_LOGIC.md, Rule 3)

### HC-4: Daily Upper Tolerable Intake (UL)

For each completed day d, and for each micronutrient with a non-null resolved UL:

`T_d.micronutrients_consumed[nutrient] ≤ resolved_UL[nutrient]`

Intake exactly equal to the UL is valid. Only strict excess (>) constitutes a violation.

ULs are **daily** limits. They are enforced independently for each day. Weekly averaging shall not weaken daily UL enforcement.

UL enforcement is independent of `U.micronutrient_targets`. A nutrient may have a UL (from demographic reference data) even if the user has not set an RDI target for it. The daily total for that nutrient is still computed and checked against the UL.

(Source: SYSTEM_RULES.md, REASONING_LOGIC.md, NEXT_STEPS.md — "ULs are DAILY limits — enforced per-day, never averaged")

### HC-5: Calorie Deficit Mode

If `U.max_daily_calories` is set (non-null), then for every day d:

`T_d.calories_consumed ≤ U.max_daily_calories`

Any day exceeding this ceiling is invalid.

(Source: KNOWLEDGE.md, REASONING_LOGIC.md, DESIGN_UNDERSTANDING.md)

### HC-6: Pinned Meal Assignments

If `U.pinned_assignments` contains an entry `(d, s) → recipe_id`, then:

1. Slot `(d, s)` shall be assigned exactly `recipe_id`. No alternative recipe may be assigned.
2. The algorithm shall not modify or remove a pinned assignment during backtracking.
3. Backtracking shall skip over pinned slots (Section 9.2).

Pinned assignments are validated before the search begins (Section 3.5). A pinned recipe that violates HC-1, HC-3, HC-5, or HC-8 is an immediate failure (FM-3).

(Source: NEXT_STEPS.md, Step 3d — "The algorithm cannot ignore this")

### HC-7: Preference Shall Not Override Feasibility

Preference scoring (liked foods, taste matching) shall not cause the selection of a recipe that renders the plan nutritionally infeasible. Specifically: if selecting a higher-preference recipe would prevent any subsequent combination of recipes from meeting daily or weekly nutritional targets, and a lower-preference recipe would not, the lower-preference recipe shall be preferred.

This constraint is enforced structurally by the search strategy: hard constraints and feasibility checks (Section 5) take precedence over scoring (Section 8).

(Source: SYSTEM_RULES.md — "Preference scoring MUST NOT override nutrition feasibility")

### HC-8: Consecutive-Day Non-Workout Repetition

For two consecutive days d and d+1 in the planning horizon: if recipe r is assigned to a slot on day d where `is_workout_slot = false`, then recipe r shall not be assigned to any slot on day d+1 where `is_workout_slot = false`.

Formally: for all d ∈ {1, ..., D−1}, if `r ∈ T_d.non_workout_recipe_ids`, then r shall not appear in `T_{d+1}.non_workout_recipe_ids`.

**Exemptions:** Recipes assigned to workout slots (`is_workout_slot = true`, i.e., slots whose `activity_context` includes `pre_workout` or `post_workout`) are exempt. The exemption applies per-assignment, not per-recipe:
- A recipe assigned to a workout slot on day d does not restrict that recipe on day d+1 in any slot type.
- A recipe assigned to a non-workout slot on day d is restricted on day d+1 only for non-workout slots — it may still appear in a workout slot on day d+1.

**Non-consecutive repetition is permitted:** A recipe in a non-workout slot on day d may appear in a non-workout slot on day d+2 or later.

**Day 1 special case:** On the first day (d = 1), there is no prior day, so HC-8 imposes no restrictions.

**Rationale:** Prevents monotonous plans where the same non-workout meals repeat daily, while allowing workout-timed meals (pre/post-workout) to repeat freely since these recipes are often selected for specific macro profiles (e.g., high-carb pre-workout) where variety is less important than function.

---

## 5. Feasibility (Forward-Looking) Constraints

Feasibility constraints are evaluated when a candidate recipe r is tentatively considered for assignment at decision point `(d, s)`. They determine whether the remaining unassigned slots — given the tentative assignment — can still yield a valid plan. If any feasibility constraint fails, candidate r is pruned (not assigned).

Feasibility checks are **conservative**: they may permit candidates that ultimately lead to infeasible plans (detected later and resolved by backtracking), but they shall not prune candidates that could lead to valid plans.

### FC-1: Daily Calorie Feasibility

After tentatively assigning r to `(d, s)`:

- Let `C_used = T_d.calories_consumed + r.nutrition.calories`
- Let `C_remaining = daily_calories_target − C_used`
- Let `k = slots_remaining_today` (non-pinned, unassigned slots after s on day d)

If `U.max_daily_calories` is set and `C_used > U.max_daily_calories`: **reject** (violates HC-5).

If `k > 0`: verify that `C_remaining` can be plausibly distributed among k slots. The check uses the ±10% daily calorie tolerance defined in Section 6.5: if the minimum achievable calories from k remaining eligible recipes would still leave the day's total within `daily_calories ± 10%`, the check passes. If the day is already beyond the +10% overage with no slots to compensate (`C_remaining < -0.10 × daily_calories` and `k = 0`), the check fails.

### FC-2: Daily Macro Feasibility

After tentatively assigning r, verify for each macronutrient (protein, fat, carbs) that the remaining gap can be plausibly filled by the remaining slots. The check is analogous to FC-1 applied per-macro:

- For protein and carbs: the remaining target minus consumed-so-far must be achievable by the remaining slots, within the ±10% tolerance.
- For fat: the remaining fat consumed must be capable of staying within `[fat_min, fat_max]` given the remaining slots.

### FC-3: Daily UL Feasibility (Incremental)

After tentatively assigning r, for each micronutrient with a non-null UL:

`T_d.micronutrients_consumed[nutrient] + r.nutrition.micronutrients[nutrient] ≤ resolved_UL[nutrient]`

If any UL is strictly exceeded by the tentative running total, **reject** r. (This is an incremental application of HC-4.)

### FC-4: Weekly Micronutrient Feasibility

Evaluated at the start of each day d (d > 1), before assigning any slot for that day:

For each tracked micronutrient n (i.e., `n ∈ U.micronutrient_targets`):
- Let `deficit(n) = (daily_RDI(n) × D) − W.weekly_totals[n]`
- Let `days_left = W.days_remaining` (including the current day)
- Let `max_daily_achievable(n)` = the maximum amount of nutrient n achievable in a single day, estimated from the recipe pool and the day's slot count.

If `deficit(n) > days_left × max_daily_achievable(n)` for any tracked nutrient n: the deficit is **irrecoverable**. Trigger backtracking to the previous day (Section 9).

**Precomputation of `max_daily_achievable(n)`:** Because the recipe pool R is static for the duration of the search, `max_daily_achievable(n)` shall be precomputed once before the search begins for each distinct slot count M that appears in the schedule. For a day with M slots, `max_daily_achievable(n)` is the sum of the M highest values of nutrient n across all recipes in R that are mutually eligible (distinct recipe IDs, per HC-2). This precomputed table is indexed by `(nutrient, slot_count)` and reused at every day boundary without redundant recipe pool traversal.

### FC-5: Recipe Pool Sufficiency

At each decision point `(d, s)`, after filtering the recipe pool by hard constraints (HC-1, HC-2, HC-3, HC-6, HC-8) and removing recipes already used on day d (HC-2):

If the resulting candidate set is **empty**, the current partial assignment is infeasible. Trigger backtracking (Section 9).

Additionally, for each remaining unassigned slot `(d, s')` where `s' > s` on day d: verify that at least one eligible recipe exists (accounting for recipes that will be marked as used by earlier slots). If any future slot on the same day has zero eligible candidates under the most optimistic assumptions, trigger backtracking.

---

## 6. Search Strategy

### 6.1 Decision Ordering

Decisions are made in a fixed, deterministic total order:

1. Days are processed sequentially: d = 1, 2, ..., D.
2. Within each day, meal slots are processed in chronological order (by `time`).
3. The decision sequence is: `(1, 1), (1, 2), ..., (1, M₁), (2, 1), ..., (D, M_D)` where `M_d` is the number of meal slots on day d.

This defines a total of N = Σ M_d decision points.

### 6.2 Handling of Pinned Slots

At each decision point `(d, s)`:
- If `(d, s)` has a pinned assignment (HC-6): accept the pinned recipe immediately. No scoring is performed. No alternatives are considered. Update state and advance.
- Otherwise: proceed with candidate generation and scoring.

### 6.3 Candidate Generation

At each non-pinned decision point `(d, s)`:

1. Start with the full recipe pool R.
2. **Remove** recipes that violate HC-1 (excluded ingredients).
3. **Remove** recipes already assigned to day d (HC-2).
4. **Remove** recipes whose `cooking_time_minutes` exceeds the slot's `cooking_time_max` (HC-3).
5. **Remove** recipes that would cause the day's calories to exceed `max_daily_calories` if set (HC-5).
6. If `is_workout_slot = false` for slot s AND d > 1: **Remove** recipes that appear in `T_{d-1}.non_workout_recipe_ids` (HC-8).
7. **Remove** recipes that fail feasibility checks FC-1 through FC-3.
8. The remaining set is the **candidate set** `C(d, s)`.

If `C(d, s)` is empty, trigger backtracking (Section 9, BT-1).

### 6.4 Greedy Selection

All candidates in `C(d, s)` are scored using the cost function (Section 8). Candidates are sorted by score descending (highest first), with ties broken as defined in Section 7. The algorithm selects the first (highest-scoring) candidate.

### 6.5 Day Completion Validation

When all slots for a day d have been assigned, perform **daily validation**:

**Macro Validation:**
- Calories: `|T_d.calories_consumed − daily_calories| ≤ 0.10 × daily_calories` (±10% tolerance)
- Protein: `|T_d.protein_consumed − daily_protein_g| ≤ 0.10 × daily_protein_g` (±10% tolerance)
- Carbs: `|T_d.carbs_consumed − daily_carbs_g| ≤ 0.10 × daily_carbs_g` (±10% tolerance)
- Fat: `daily_fat_g.min ≤ T_d.fat_consumed ≤ daily_fat_g.max`

**UL Validation:**
- For each micronutrient with non-null UL: verify HC-4.

**Calorie Ceiling Validation:**
- If `max_daily_calories` is set: verify HC-5.

If any validation check fails, trigger backtracking (Section 9, BT-2).

If all checks pass:
- Increment `W.days_completed`.
- Add day d's nutrition totals to `W.weekly_totals`.
- Recompute `W.carryover_needs` for all tracked micronutrients.
- Proceed to day d+1.

### 6.6 Plan Completion Validation (Weekly)

When all D days have been fully assigned and individually validated, perform **weekly validation**:

For each tracked micronutrient n (i.e., `n ∈ U.micronutrient_targets`):
- `W.weekly_totals[n] ≥ daily_RDI(n) × D`

The weekly target is **prorated** to the planning horizon. If D = 3, the target is `daily_RDI × 3`, not the full 7-day RDI. This ensures the algorithm's validation is meaningful regardless of how many days are planned.

(Source: SYSTEM_RULES.md — "Weekly micronutrient logic may allow daily variance but MUST meet weekly RDI"; KNOWLEDGE.md — "it is not negotiable that [...] the weekly calculation of micronutrient RDIs are reached")

**Sodium advisory:** If the planned total for Sodium exceeds 200% of `daily_RDI × D`, this should be flagged as a warning in the output. It is not a hard constraint and does not trigger backtracking. (Source: REASONING_LOGIC.md)

If weekly validation fails, trigger backtracking (Section 9, BT-3).

If weekly validation passes, the algorithm terminates successfully (Section 10, TC-1).

---

## 7. Heuristic Ordering

At each non-pinned decision point `(d, s)`, candidates in `C(d, s)` are ordered by composite score (Section 8), from highest to lowest.

### 7.1 Tie-Breaking

If two or more candidates have identical composite scores, ties are broken by the following cascade (applied in order until the tie is resolved):

1. **Higher micronutrient gap-fill coverage:** Prefer the recipe that provides non-zero amounts of more currently-deficient micronutrients (those below `adjusted_daily_target`).
2. **Higher total deficit reduction:** Among recipes covering the same count of deficient nutrients, prefer the one whose summed contributions to deficient nutrients (as a fraction of their respective remaining gaps) is greater.
3. **Liked food presence:** Prefer the recipe that contains more ingredients matching entries in `U.liked_foods`.
4. **Lexicographic recipe ID:** As a final deterministic tie-breaker, prefer the recipe with the lexicographically smaller `id`.

Rule 4 ensures determinism: no two recipes share the same ID, so ties are always fully resolved.

---

## 8. Cost Function Definition

The cost function assigns a **score** to each candidate recipe r at decision point `(d, s)` in state S. **Higher scores are better.** The algorithm selects the candidate with the highest score.

### 8.1 Composite Score

`Score(r, d, s, S) = w₁·NutritionMatch + w₂·MicronutrientMatch + w₃·SatietyMatch + w₄·Balance + w₅·ScheduleMatch`

Each component is normalized to the range [0, 100].

### 8.2 Component Weights

The weights are derived from REASONING_LOGIC.md (Step 4) with the following adjustments: Schedule Match is reduced from 20 to 10 points (since HC-3 already filters over-time recipes, reducing the discriminative value of this component), and the freed 10 points are redistributed equally to Satiety Match and Balance. The total remains 110:

| Component | Points | Normalized Weight |
|---|---|---|
| Nutrition Match | 40 | 40/110 ≈ 0.364 |
| Micronutrient Match | 30 | 30/110 ≈ 0.273 |
| Satiety Match | 15 | 15/110 ≈ 0.136 |
| Balance | 15 | 15/110 ≈ 0.136 |
| Schedule Match | 10 | 10/110 ≈ 0.091 |

The normalized weights sum to 1.0. The maximum achievable composite score is 100.

**Note:** These weights may be revised after empirical testing with real recipe pools and user profiles. The structural framework (weighted composite of normalized components) remains stable; only the numeric weights are subject to tuning.

**Note on Preference scoring:** REASONING_LOGIC.md does not define a separate Preference component. Liked-food preference is addressed exclusively through tie-breaking (Section 7.1). Disliked foods are handled by hard exclusion in candidate generation (HC-1). No scoring weight is allocated to preference matching.

### 8.3 Nutrition Match (w₁ = 40/110)

Evaluates how well r's macronutrient profile matches the per-meal targets for slot `(d, s)` (Section 3.6).

**Sub-scores** (each 0–100, combined by equal-weight average unless otherwise specified):

- **Calories sub-score:** Let `deviation = |r.nutrition.calories − meal_calorie_target| / meal_calorie_target`. Score = `max(0, 100 × (1 − deviation / 0.10))`. Deviation ≤ 10% yields score ≥ 0; deviation = 0 yields 100.

- **Protein sub-score:** Same formula as calories, using protein values. The meal protein target is adjusted for activity context:
  - `pre_workout`: target reduced (favor lower protein to maximize carb absorption)
  - `post_workout`: target increased (favor higher protein for synthesis)
  - (Source: REASONING_LOGIC.md, Rule 2)

- **Fat sub-score:** Evaluates whether r's fat contribution keeps the day's running fat total on track to land within `[fat_min, fat_max]`. Score is highest when the running total plus r's fat, divided proportionally, projects toward the midpoint of the range.

- **Carbs sub-score:** Same deviation formula as calories, using carb values. Adjusted for timing context:
  - `pre_workout`: adequate carb amount with low-fiber, low-fat, medium-low-protein profile is favored
  - `post_workout`: good carb amount for recovery
  - `sedentary`: lower carbs preferred, but shall not dominate over hitting the daily carb target
  - `overnight_fast_ahead`: complex carbs preferred for satiety
  - (Source: REASONING_LOGIC.md, Rule 2)

### 8.4 Micronutrient Match (w₂ = 30/110)

Evaluates how well r addresses outstanding micronutrient gaps.

**Inputs from state S:**
- `nutrients_still_needed`: set of tracked micronutrients where `T_d.micronutrients_consumed[n] < adjusted_daily_target(n)`, each with its remaining gap
- `carryover_needs`: tracked micronutrients with accumulated deficit from `W.carryover_needs`
- `nutrients_already_covered`: tracked micronutrients at or above `adjusted_daily_target`

**Scoring logic:**
- For each tracked micronutrient n provided by recipe r:
  - If n ∈ `nutrients_still_needed`: contribution is scored proportionally to the fraction of the remaining gap that r fills. Nutrients with larger gaps (relative to target) receive higher weight.
  - If n ∈ `carryover_needs`: additional bonus proportional to the weekly deficit for n.
  - If n ∈ `nutrients_already_covered`: no contribution (score = 0 for this nutrient).

The component score is the weighted sum of per-nutrient contributions, normalized to [0, 100].

**Priority nutrients** (those with the greatest combined daily and weekly deficits) contribute disproportionately to the score. (Source: REASONING_LOGIC.md, Rule 1 — "PRIORITIZE nutrients that are most below daily target, needed for weekly carryover, not already covered")

### 8.5 Satiety Match (w₃ = 15/110)

Evaluates how well r matches the satiety requirement for slot `(d, s)`.

**If `satiety_requirement = high`:**
- Higher fiber content → higher score
- Higher protein content → higher score
- Lower calorie density (calories per gram) → higher score
- Higher total calories → higher score (bigger meal for longer fasts)
- (Source: REASONING_LOGIC.md, Rule 4 — "meal should be BIGGER with more calories")

**If `satiety_requirement = moderate`:**
- Moderate, balanced macros → higher score
- Avoids excessive satiety in a single meal → higher score

### 8.6 Balance (w₄ = 15/110)

Evaluates how well r complements the meals already assigned to day d.

**Sub-components:**
- **Nutrient diversity:** Avoids excessive duplication of micronutrients already well-covered by prior meals today. Recipes providing novel micronutrient contributions score higher.
- **Fat source diversity:** Penalizes over-reliance on the same fat sources (e.g., if prior meals are all beef/egg fat, prefer a recipe with different fat sources). (Source: KNOWLEDGE.md — "we really want to make sure we are getting a proper fat diversity")
- **Macro trajectory:** Evaluates whether the day's running macro totals are on track toward targets. Recipes that correct a macro imbalance score higher.

### 8.7 Schedule Match (w₅ = 10/110)

Evaluates the fit between r's cooking time and the slot's busyness level.

- `cooking_time_minutes ≤ cooking_time_max`: full score (100).
- For busyness level 4 (no upper bound): score based on proximity to a reasonable cooking time. Recipes closer to 30 minutes score higher than those requiring several hours.

**Note:** Recipes exceeding `cooking_time_max` for levels 1–3 are excluded during candidate generation (HC-3). This component differentiates recipes *within* the allowed range — a 5-minute recipe scores higher than a 14-minute recipe for a 15-minute slot. The weight (10/110) reflects the reduced discriminative value of this component given HC-3's filtering.

---

## 9. Backtracking Rules

### 9.1 Trigger Conditions

| Code | Condition | Triggered At |
|---|---|---|
| BT-1 | Empty candidate set `C(d, s) = ∅` | Decision point `(d, s)` during candidate generation |
| BT-2 | Daily validation failure for day d | Day d completion (Section 6.5) |
| BT-3 | Weekly validation failure | Plan completion (Section 6.6) |
| BT-4 | Weekly feasibility failure (FC-4) | Start of day d (d > 1) |

### 9.2 Backtracking Procedure

Backtracking follows **chronological backtracking** — the algorithm unwinds decisions in reverse decision order.

When backtracking is triggered:

**Step 1: Identify the backtrack target.**
- Starting from the current decision point, move backward through the decision order to find the most recent non-pinned decision point that has untried candidates. Call this `(d_b, s_b)`.

**Step 2: Unwind.**
- For every decision point between the current point and `(d_b, s_b)` (exclusive), in reverse order:
  - If the decision point is non-pinned: remove its assignment from the state. Decrement the corresponding daily tracker (including `non_workout_recipe_ids` if applicable). Remove the recipe ID from `used_recipe_ids`. Decrement `slots_assigned`.
  - If the decision point is pinned: **do not modify it**. The pinned assignment remains.
- At `(d_b, s_b)`: remove its current assignment from the state.

**Step 3: Advance the candidate pointer at `(d_b, s_b)`.**
- Move to the next candidate in the heuristic ordering (Section 7) that has not yet been tried at this decision point.

**Step 4: Re-enter forward search.**
- Assign the new candidate to `(d_b, s_b)`. Update the state. Proceed forward to `(d_b, s_b + 1)` (or the next day's first slot if `s_b` was the last slot of day `d_b`).

**Day boundary behavior:** If backtracking unwinds past the first slot of day d into day d−1, the daily tracker for day d is reset. The weekly tracker is updated to remove day d−1's contribution (since day d−1 is now being re-planned from the point of the backtrack target). All candidate lists for decision points on day d and beyond are invalidated and will be regenerated on the next forward pass — this is necessary because HC-8 exclusions for day d depend on day d−1's `non_workout_recipe_ids`, which may have changed.

### 9.3 Candidate List Persistence

At each decision point `(d, s)`, when the point is first visited during the current forward pass:
- The candidate set `C(d, s)` is generated and scored **once**.
- The sorted candidate list and a pointer (indicating which candidates have been tried) are stored.
- Upon backtracking to `(d, s)` without crossing a day boundary behind it, the pointer advances to the next untried candidate. The list is **not** regenerated or re-scored.
- If backtracking crossed a day boundary (i.e., assignments on a prior day changed), the candidate list for `(d, s)` is invalidated and regenerated on the next forward visit, since HC-8 exclusions may have changed.

This policy balances simplicity with correctness. Within a single day, score-once ensures monotonic progress and termination. Across day boundaries, regeneration ensures HC-8 consistency.

### 9.4 Backtracking Depth Limit

The algorithm shall implement a configurable attempt limit to bound worst-case runtime. When the limit is reached, the algorithm terminates under TC-3 (Section 10).

The specific numeric value of this limit is **deferred to empirical testing**. The implementation shall expose it as a configurable parameter with a sensible default. Test cases shall be designed to exercise backtracking behavior at various depths to inform the final value.

Possible formulations for the limit:
- Maximum total assignments attempted across the entire search.
- Maximum number of backtracks from any single decision point.
- Wall-clock time limit.

---

## 10. Termination Conditions

| Code | Condition | Output |
|---|---|---|
| TC-1 | **Success.** All D days assigned; daily validation passes for each day; weekly validation passes. | Complete, valid meal plan P. |
| TC-2 | **Exhaustion.** The algorithm has backtracked to the very first non-pinned decision point in the ordering and all candidates at that point have been exhausted. | Failure: no valid plan exists for the given inputs. Report the best partial plan and the specific constraints that could not be satisfied. |
| TC-3 | **Attempt limit reached.** The configurable backtracking/attempt limit (Section 9.4) has been reached. | Failure: search space not fully explored. Return the best complete-but-invalid or best partial plan found during the search, with a summary of unmet constraints. |
| TC-4 | **Single-day mode.** When D = 1, termination occurs after daily validation (Section 6.5). Weekly validation is not performed. | If daily validation passes: success (equivalent to TC-1). If daily validation fails and backtracking is exhausted: failure (equivalent to TC-2). |

---

## 11. Failure Modes

When the algorithm terminates without a valid plan (TC-2 or TC-3), it shall report a structured failure result. The failure modes are categorized as follows:

### FM-1: Insufficient Recipe Pool

**Condition:** The recipe pool does not contain enough distinct recipes that pass hard constraint filtering (HC-1, HC-2, HC-3, HC-8) to fill all meal slots for one or more days.

**Detection:** FC-5 (Recipe Pool Sufficiency) detects this at the first decision point of the affected day, or earlier if filtering eliminates too many candidates.

**Report shall include:**
- Which day(s) and slot(s) cannot be filled.
- Which hard constraints are eliminating candidates (e.g., "All recipes with cooking time ≤ 5 minutes contain excluded ingredients" or "All eligible recipes were used in non-workout slots yesterday").
- The number of eligible recipes per slot.

### FM-2: Daily Nutritional Infeasibility

**Condition:** The recipe pool contains enough recipes to fill all slots, but no combination of eligible recipes yields daily macro totals within tolerance or daily UL compliance for one or more days.

**Examples:**
- All high-protein recipes are also high-fat, making it impossible to meet protein targets within the fat range.
- A day's eligible recipes all contain high levels of a UL-constrained nutrient, causing every combination to violate HC-4.

**Report shall include:**
- The day(s) that failed validation.
- The specific macro or UL violations (e.g., "Day 3: fat = 125g, exceeds max of 100g in all explored combinations").
- The closest-to-valid plan found (minimum total deviation from targets).

### FM-3: Pinned Meal Conflict

**Condition:** Pinned assignments (HC-6) consume a nutritional budget that leaves the remaining slots unable to reach daily targets, or a pinned recipe itself violates a hard constraint for its slot.

**Examples:**
- A pinned breakfast recipe provides 1800 of 2400 daily calories, leaving only 600 calories for the remaining three slots.
- A pinned recipe exceeds `cooking_time_max` for its slot.
- A pinned recipe contains an excluded ingredient.
- Two pinned non-workout recipes on consecutive days use the same recipe (violates HC-8).

**Detection:** Pinned recipes that directly violate HC-1, HC-3, HC-5, or HC-8 are caught during pre-validation (Section 3.5) before the search begins. Downstream nutritional infeasibility caused by pinned assignments is detected during the search via feasibility checks or backtracking exhaustion.

**Report shall include:**
- The specific pinned assignment causing the conflict.
- The nutritional budget remaining after pinned assignments.
- Whether the conflict is a hard constraint violation of the pinned recipe itself, or a downstream infeasibility.

### FM-4: Weekly Micronutrient Infeasibility

**Condition:** Each individual day can be planned to pass daily validation, but the accumulated totals for one or more tracked micronutrients fall below the prorated RDI target (`daily_RDI × D`) after all D days.

**Detection:** BT-3 (weekly validation failure) or FC-4 (weekly feasibility check at day boundary).

**Report shall include:**
- Which micronutrient(s) are deficient and by what amount.
- The total achieved vs. the prorated RDI target for each deficient nutrient.
- Whether the deficiency is marginal (close to target, potentially resolvable with recipe pool expansion) or structural (no combination in the pool can meet it).

### FM-5: Search Budget Exhaustion

**Condition:** The algorithm reached the backtracking/attempt limit (TC-3) without finding a valid plan or proving that none exists.

**Report shall include:**
- The number of assignments attempted and backtracks performed.
- The best plan found during the search (may be complete-but-invalid, or partial).
- The specific validation failures of the best plan.
- Indication that the search was not exhaustive — a valid plan may exist but was not found within the budget.

---

## Appendix A: Glossary

| Term | Definition |
|---|---|
| **Decision point** | A single `(day, slot)` pair requiring a recipe assignment. |
| **Candidate set** | The filtered set of eligible recipes for a given decision point. |
| **Daily tracker** | Running nutritional totals for a single day. |
| **Weekly tracker** | Running nutritional totals and carryover across all planned days. |
| **Pinned assignment** | A user-specified mandatory recipe-to-slot mapping. |
| **UL** | Upper Tolerable Intake — the maximum safe daily intake for a micronutrient. |
| **RDI** | Recommended Daily Intake — the target intake for a micronutrient. |
| **Carryover** | Micronutrient deficit from prior days that increases subsequent days' targets. |
| **Feasibility check** | A forward-looking test of whether remaining slots can still yield a valid plan. |
| **Hard constraint** | An inviolable requirement; any violation renders the plan invalid. |
| **Composite score** | The weighted sum of scoring components used to rank candidates. |
| **Excluded ingredient** | An ingredient the user cannot or will not eat (allergen or strong dislike). |
| **Tracked micronutrient** | A micronutrient present in `U.micronutrient_targets`; participates in scoring and validation. |
| **Workout slot** | A meal slot whose `activity_context` includes `pre_workout` or `post_workout`. |
| **Non-workout slot** | A meal slot whose `activity_context` does not include `pre_workout` or `post_workout`. |

## Appendix B: REQUIRES CLARIFICATION — Open Items

All previously open items have been resolved. No open clarifications remain.

## Appendix C: REQUIRES CLARIFICATION — Resolved Items

| # | Section | Original Item | Resolution |
|---|---|---|---|
| 1 | 2.1 | Whether a `nutrient_exemptions` field is necessary. | **Removed.** Nutrients not in `micronutrient_targets` are not tracked. Omission from the targets dict is the exemption mechanism. |
| 2 | 2.1.1 | Whether the schedule is uniform across all days or may vary per day. | **Each day may define a distinct schedule.** |
| 3 | 2.1.1 | Maximum number of meal slots permitted per day. | **8 slots per day.** |
| 4 | 3.6 | Exact multiplicative factors for activity-context macro adjustments. | **Preserve the existing implementation's factors as normative.** |
| 5 | 4 (HC-8) | Whether disliked foods are a hard exclusion or soft penalty. | **Merged with allergens into a single `excluded_ingredients` list with hard exclusion semantics. Former HC-8 removed; replaced by new HC-8 (consecutive-day repetition).** |
| 6 | 4 (HC-2) | Whether cross-day recipe repetition should have a frequency limit. | **Yes. HC-8 added: recipes in non-workout slots cannot repeat on consecutive days. Workout-slot recipes are exempt.** |
| 7 | 5 (FC-1) | Precision of daily calorie feasibility bounds. | **Adopt ±10% tolerance from Section 6.5.** |
| 8 | 5 (FC-4) | Method for computing `max_daily_achievable(n)`. | **Precomputed once before search, indexed by (nutrient, slot_count).** |
| 9 | 6.6 | Whether Omega-3:Omega-6 ratio is a hard constraint or advisory. | **Removed as special case. Omega-3 is a normal tracked micronutrient with an RDI target.** |
| 10 | 7.1 | Whether tie-breaking should include liked-food preference. | **Yes. Added as tie-breaking rule 3 (before lexicographic ID).** |
| 11 | 8.2 | Whether a separate Preference scoring component should exist. | **No. Preference addressed via exclusion (HC-1) and tie-breaking (Section 7.1) only.** |
| 12 | 8.5 | Utility of Schedule Match weight given HC-3 filtering. | **Reduced from 20 to 10 points. Freed 10 points redistributed: Satiety 10→15, Balance 10→15.** |
| 13 | 9.3 | Whether candidates should be re-scored upon backtracking. | **Score-once within a day. Candidate lists invalidated and regenerated when backtracking crosses a day boundary (for HC-8 correctness).** |
| 14 | 9.4 | Specific backtracking depth/attempt limit values. | **Deferred to empirical testing. Implementation exposes a configurable parameter.** |
