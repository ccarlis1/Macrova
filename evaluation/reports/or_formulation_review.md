# Macrova planner: operations-research formulation review

**Date:** 2026-09-17  
**Scope:** Is the deterministic meal planner correctly formulated as a constraint-driven planning problem?  
**Sources reviewed:** `docs/planner/mealplan-specification-v3.md`, `docs/planner/planner-rules.md`, `docs/planner/reasoning-logic.md`, `src/planning/*`, `src/api/server.py` (plan route), `src/data_layer/meal_prep.py`, `src/data_layer/user_profile.py`, `src/nutrition/calculator.py`, reference data under `data/reference/`, the example and local profile/recipe/ingredient files, and `evaluation/initial_state.md`.  
**Method:** Read the specification and code side by side, then ran read-only diagnostics against the example data, the local data, and small synthetic instances to confirm each claim. No code was changed. No code changes are proposed here.

Every criticism below carries one or more of these labels:

- **[SPEC]** specification problem: the requirement itself is missing, ambiguous, or in conflict.
- **[ALG]** algorithm problem: the search or scoring method is unsuited to the requirement.
- **[DATA]** data problem: reference data, recipe data, ingredient data, or profile defaults.
- **[UX]** user-experience problem: the user cannot express, see, or act on something.
- **[IMPL]** implementation detail: code diverges from spec or has a local defect, without changing the formulation.

---

## 1. Verdict

Macrova is formulated as a **constraint satisfaction problem with heuristic value ordering**, not as a constrained optimization problem. That is a legitimate design, and the specification is unusually explicit about it (Section 1, item 5: the plan returned is the first one the search finds). But the rest of the document, the failure-mode contracts, and the product language all speak as if an objective were being optimized. That mismatch is the root of most of the practical problems below.

The formulation as it actually stands:

| Element | What Macrova has |
|---|---|
| Decision variables | One atomic recipe ID per `(day, slot)`, plus an optional scaled-variant index for rice and potato recipes. No portion or serving variable. No decision about batching. |
| Hard constraints | HC-1 ingredient exclusion, HC-2 same-day uniqueness, HC-3 cooking time, HC-4 daily UL, HC-5 calorie ceiling, HC-6 pins and batch locks, HC-8 consecutive-day non-workout repetition, HC-9 slot required tags, daily macro windows (±10% kcal, protein, carbs; fat within a range), and a horizon-wide micronutrient floor τ × RDI × D. |
| Feasibility propagation | Interval bounds from the M smallest and M largest recipe values (FC-1, FC-2), incremental UL (FC-3), a per-day-boundary micronutrient bound (FC-4), and a pool non-emptiness look-ahead (FC-5). |
| Objective | None. A composite score orders candidates at each decision point. Complete plans are never compared. |
| Search | Depth-first chronological backtracking in a fixed `(day, slot)` order, score-once candidate lists, attempt cap of 50,000. |

Four structural conclusions follow, each expanded in the sections below:

1. **The variables are purely combinatorial**, so every macro window becomes a subset-sum condition over atomic recipes. Feasibility is then a property of the pool's arithmetic, not of the user's goals. Small pools are brittle by construction. [SPEC]
2. **There is no objective**, so "plan quality" is whatever the greedy ordering happens to produce at the first feasible leaf. The scoring function has a cliff at 10% deviation that flattens most candidates to the same score, which hands the real ordering to secondary components and tie-breaks. [SPEC] [ALG]
3. **Several requirements are in direct mathematical conflict**: meal-prep locks versus the variety and cooking-time constraints; the magnesium RDI versus its UL; a misplaced sodium floor. These are not tuning issues. [SPEC] [DATA]
4. **Current data cannot exercise the formulation at all**: most recipes in both the example and the local datasets compute to zero nutrition because unresolved ingredients are silently skipped, and the planner then reports micronutrient infeasibility. The failure codes the sprint is treating as a baseline are pointing at the wrong cause. [DATA] [UX]

---

## 2. Decision variables

### 2.1 Atomic recipes with no portion variable [SPEC]

Each slot receives exactly one recipe at its stored quantity. The only continuous relief valve is Primary Carb Downscaling (Section 6.7), which is off by default, applies only to rice and potato in sedentary slots, and requires a precomputed `primary_carb_contribution` that `convert_recipes` never populates. In the CLI and API paths that feature is therefore unreachable, so in production the variable set is strictly combinatorial. [IMPL for the unreachable feature]

Consequence: the daily macro windows (Section 6.5) require that the sum of three or four fixed vectors lands inside four simultaneous intervals. That is a multi-dimensional subset-sum condition. Whether a valid plan exists depends on arithmetic coincidences in the pool rather than on anything the user controls. A portion multiplier per assignment (even a coarse one) would turn most of these windows into trivially satisfiable linear constraints; its absence is the single largest formulation choice in the system.

### 2.2 What one recipe means [SPEC] [DATA]

`Recipe.default_servings` exists in the data model and the nutrition-summary endpoint divides by servings, but the planner consumes `calculator.calculate_recipe_nutrition(recipe)` for the whole ingredient list and treats that as one meal. `PlanningBatchLock.servings` is carried but never used in nutrition accounting. The spec never states whether `nutrition` is per serving or per batch. A meal-prep recipe entered for four servings will be credited with four servings of calories in each locked slot.

### 2.3 Identity is by ID, not by content [SPEC] [DATA]

HC-2 and HC-8 compare recipe IDs. The local `recipes.json` contains five byte-identical "Grilled Chicken with Vegetables" recipes and several identical "Oatmeal with Fruits" and "Quinoa Salad" recipes under distinct LLM-generated IDs. A plan serving the same chicken dish for breakfast, lunch, and dinner on every day of the week satisfies every hard constraint. The specification has no definition of "same meal" beyond the ID, and the LLM pipeline has no deduplication gate.

---

## 3. Hard constraints

### 3.1 HC-1 ingredient exclusion is exact-string matching [SPEC] [DATA]

The spec says matching is "performed on normalized ingredient names" and never defines normalization. The implementation lower-cases and strips, then tests set membership. Confirmed on a synthetic instance: excluding `peanuts` still selected a recipe whose ingredient is `peanut butter`. The example profile's allergy list (`shellfish`, `peanuts`) will not match `shrimp`, `crab`, `peanut oil`, or `peanut butter`. This is the one hard constraint with a safety dimension, and it is the weakest one. There is no ingredient taxonomy, no allergen class table, and no substring or token matching. The separate `dietary_flags` tag mechanism (for example `no-shellfish`) is a second, uncoordinated encoding of the same intent; the two can disagree, and tags are LLM-proposed until approved.

### 3.2 HC-2 and HC-8 are in direct conflict with meal prep [SPEC]

Meal prep means cooking once and eating the same dish repeatedly. HC-2 forbids the same recipe twice on one day; HC-8 forbids the same recipe in non-workout slots on consecutive days. Batch locks are normalized into pins and pins are pre-validated against HC-2 and HC-8. Confirmed: a batch locking one recipe to lunch on day 0 and day 1 fails before search with FM-3 (HC-8). A four-serving batch spread across four weekday lunches cannot be planned. The specification introduced HC-8 (Appendix C, item 6) and the batch-lock precedence rule separately and never reconciled them.

### 3.3 HC-3 cooking time conflates "cook once" with "effort per serving" [SPEC]

`cooking_time_minutes` is the recipe's total preparation time. For a prepped batch, the per-slot effort is reheating. Confirmed: a 40-minute recipe batch-locked into a busyness-1 (5-minute) slot fails pre-validation with FM-3 (HC-3), even though a 5-minute slot is exactly where a prepped meal belongs. The registry's `time-0` through `time-4` tags are a third encoding of the same time concept.

### 3.4 HC-4 upper limits are not enforced in the API path [IMPL] [DATA]

`plan_meals` accepts `resolved_ul` and skips HC-4 and FC-3 when it is `None`. The plan route in `src/api/server.py` calls `plan_meals(planning_profile, recipe_pool, plan_request.days)` with no UL argument. The CLI resolves ULs but hard-codes `adult_male`, and `convert_profile` hard-codes `demographic="adult_male"` regardless of the user's profile. The AGENTS.md invariant "daily ULs are enforced per-day, never averaged" is true in unit tests and false for Flutter users.

### 3.5 The UL reference table makes the default problem infeasible [DATA] [SPEC]

`data/reference/ul_by_demographic.json` lists magnesium UL 350 mg for adults. The IOM magnesium UL applies to supplemental magnesium only, not food. The example profile targets 400 mg/day. With the spec's default τ = 1.0 the plan must total ≥ 400 × D while no day may exceed 350, which is impossible for every D. At the shipped τ = 0.8 the admissible band is 320 to 350 mg per day, averaged, with each day capped at 350. The same "supplement-only" caveat applies to the niacin, folate, and vitamin E ULs in the table. Nothing in the spec or the loader checks the consistency condition τ × RDI(n) ≤ UL(n).

### 3.6 HC-5 calorie ceiling has no consistency check and no API surface [SPEC] [UX]

If `max_daily_calories` is below 0.9 × `daily_calories`, HC-5 and the ±10% window are jointly infeasible; nothing validates this. `PlanRequest` has no `max_daily_calories` field, so Calorie Deficit Mode is CLI/YAML only.

### 3.7 Pin pre-validation is partial, and its report is off by one [IMPL] [UX]

Pins are checked against HC-1, HC-2, HC-3, HC-5, and HC-8 but not HC-4 (a pinned recipe that alone exceeds a UL) or HC-9 (required tags). Those cases surface as search exhaustion instead of FM-3. The FM-3 report converts an already 1-based day to a label once more: a lock on planner day index 1 is reported as `day-3-slot-0`. The planner keys pins as `(day_1based, slot_0based)` while every other layer uses zero-based addresses; the spec acknowledges the conversion and the code pays for it.

### 3.8 HC-7 is not a constraint [SPEC]

"Preference shall not override feasibility" describes the search architecture. It is trivially satisfied because preference is not part of the objective at all (Section 8.2 note), and, as shown in 4.5, the liked-foods tie-break is not wired either.

### 3.9 HC-8 is a weak variety constraint [SPEC]

It looks back exactly one day, so day 1 / day 2 / day 1 / day 2 alternation is valid. Workout-slot recipes may repeat every day. Variety is defined at the recipe-ID level only; there is no ingredient-level or protein-source diversity constraint, though `nutrition-knowledge.md` asks for fat-source diversity.

### 3.10 HC-9 required tags cannot currently be satisfied [DATA]

The committed `data/recipes/recipe_tags.json` has an empty `tags_by_id`. Any slot with `required_tag_slugs` terminates with FM-TAG-EMPTY. The precedence rule that a batch lock overrides required tags with only a warning is intentional, but it means "required" is not required; the spec should say so plainly.

---

## 4. Soft constraints and the objective

### 4.1 There is no objective function [SPEC]

Section 8 is titled "Cost Function Definition" and Section 11 (FM-2, FM-5) promises "the closest-to-valid plan found (minimum total deviation from targets)". Neither exists as an evaluated quantity over complete plans. The composite score orders candidates at a single decision point against the state at that moment. The returned plan is the first feasible leaf in DFS order. The "best partial plan" tracked by the search is the longest prefix, not the least-deviating one. [IMPL for the best-partial gap]

The practical consequence: two feasible plans, one that lands every day within 1% of target and one that sits at the ±10% edges everywhere, are indistinguishable to the system. Whichever the greedy path reaches first is returned.

### 4.2 The per-meal scoring cliff flattens the ordering [ALG] [SPEC]

The nutrition sub-scores use `max(0, 100 × (1 − deviation / 0.10))` against an even split of the remaining daily budget. Measured: 5% deviation scores 50, 10% or more scores 0. For a 2400 kcal day with three slots the per-meal target is 800 kcal; a 900 kcal recipe and a 1400 kcal recipe both score zero on calories. The same cliff applies to protein and carbs. Realistic pools therefore have most candidates tied at or near zero on the 40-point nutrition component, and the effective ordering comes from satiety, balance, schedule, tag bonuses, and finally recipe ID. The activity-context factors (0.8×, 1.1×, 1.2×) shift the cliff by a few percent and do little else. Reusing the daily validation tolerance as the per-meal scoring tolerance is a specification choice with no stated rationale.

### 4.3 Component formulas are ad hoc and unit-blind [IMPL]

Satiety uses `fiber × 6`, `protein × 2.5`, `calories / 6`; moderate satiety is `70 − |protein − 25| × 0.5`. Balance counts a nutrient as "novel" when consumed-so-far is below 1.0 in whatever unit the field carries, so 0.9 µg of B12 and 0.9 mg of sodium are treated the same way. Schedule match rewards the shortest cooking time inside the bound, so a two-minute shake beats a fourteen-minute omelette in every 15-minute slot. Fat-source diversity (spec Section 8.6) is not implemented because no ingredient-level fat-source data exists. [DATA for the last point]

### 4.4 Additive bonuses are not bounded [ALG] [IMPL]

The spec calls `PreferredTagBonus` "bounded". The implementation adds 1.0 per matched slot tag and also synthesizes `high-<nutrient>` tags for every tracked nutrient currently below its adjusted target; with 25 tracked nutrients that is up to 25 points on a 0 to 100 scale before clamping, plus a flat −2 variety penalty over a three-day lookback. When the nutrition component is at zero for most candidates (4.2), these side terms can decide the ordering outright.

### 4.5 The tie-break cascade is not implemented as specified [IMPL] [UX]

Spec Section 7.1 orders ties by gap-fill coverage, deficit reduction, liked-food count, preferred tags, then ID. The implementation orders by preferred-tag count, ID, then a seeded random number that can never be reached because IDs are unique. `gap_fill_count`, `deficit_reduction`, and `liked_foods_count` exist in `phase5_ordering.py` and are not called. Net effect: `liked_foods` in the user profile has no influence on any planning decision.

### 4.6 Sodium and omega-6 are modeled as floors [SPEC] [DATA]

Every entry in `micronutrient_targets` is a minimum to reach. The example profile includes `sodium_mg: 1500` and `omega_6_g: 17`. The scorer rewards recipes for adding sodium while the day is below 1500 mg, the weekly floor requires ≥ τ × 1500 × D, and the only ceiling is an advisory at 200% of the horizon total, which triggers only if the average day exceeds 3000 mg. The local Grilled Chicken recipe carries 2212 mg per meal. The omega-3:omega-6 ratio, which `reasoning-logic.md` says matters more than either individual number, was removed in Appendix C item 9.

---

## 5. Feasibility

### 5.1 The interval bounds are sound but loose [ALG]

FC-1 and FC-2 bound the remaining slots by the M smallest and M largest values over the entire pool, ignoring HC-1, HC-3, HC-8, tags, and the recipes already used today. That is conservative in the correct direction (never prunes a feasible branch) and cheap. It is also weak: with a pool containing a 0 kcal recipe and a 1200 kcal recipe, almost any prefix passes. Most infeasibility is discovered only at the last slot of a day or, for the weekly floor, at the last slot of the horizon.

### 5.2 The weekly floor is a global constraint checked at the leaf [ALG]

BT-3 fires only after all D days are assigned. FC-4's day-boundary bound uses the M largest micronutrient values in the pool regardless of whether those recipes could ever coexist within a day's macro windows, so it rarely fires. When the weekly floor fails, chronological backtracking re-tries every alternative for the last slot of day D, then the second-to-last, and so on, exploring day D's subtree exhaustively before touching day 1. This is textbook thrashing on a non-chronological constraint. The 50,000-attempt cap then produces FM-5 with no proof of infeasibility. Carryover adjusts scoring targets only; nothing prevents early days from under-shooting, and where a UL caps the catch-up rate (magnesium, 3.5) the deficit becomes unrecoverable late.

### 5.3 The structural pre-check is right in principle and misleading in practice [UX] [DATA]

`check_structural_feasibility` correctly rejects before search when even the best-case sum cannot reach the floor. But the FM-4 report it emits shows `achieved: 0.0` for every nutrient because nothing was planned, and labels most as "structural" and some as "marginal" against a per-day bound that ignores macros. A misspelled target key (confirmed with `vitamin_c_mgs`) yields `max_daily_achievable = 0` and therefore a "structural" FM-4 for that key, with no validation error naming the typo.

### 5.4 Zero nutrition from unresolved ingredients is invisible to the planner [DATA] [UX]

`NutritionCalculator` skips ingredients it cannot resolve ("In MVP, we'll skip missing ingredients"). With the example ingredient file, 14 of 18 example recipes compute to 0 kcal and the highest is 198 kcal; with the local ingredient file, 20 of 32 local recipes compute to 0 kcal. The baseline report records the resulting CLI failure as FM-4 "weekly micronutrient targets infeasible". With micronutrient targets removed the same pool fails FM-1 at day 1 slot 0 because no three recipes can reach 2160 kcal. Neither code names the real cause. The formulation cannot distinguish "zero because absent" from "zero because unknown", and the sprint's baseline is anchored on a symptom.

### 5.5 The macro windows are coupled, not independent [SPEC]

Calories, protein, carbs, and fat are constrained as four independent intervals. They are linked by the Atwater identity (kcal ≈ 4P + 4C + 9F) only if the ingredient database's calorie figures obey it, which USDA data does not exactly. Carbs are derived from the median of the fat range and then given their own ±10% window, so a user who says "fat anywhere in 50 to 100 g" has also, without knowing it, said "carbs within 253 to 309 g". Carbs should be the slack variable that absorbs whatever fat and protein leave; making it an independent target is what turns the day into a four-dimensional subset-sum.

### 5.6 Short horizons are the hardest instances [SPEC]

The floor is prorated (τ × RDI × D) and there is no daily micronutrient constraint, so a one-day plan must reach τ × 100% of every tracked RDI in a single day, while a seven-day plan can average. Users will expect a one-day plan to be the easy case; it is the strictest.

---

## 6. Prioritization

- **Precedence among hard constraints is flat.** [SPEC] Every violation is fatal and there is no relaxation ladder. When the problem is infeasible the report names one code (the first exhaustion reason encountered), not the smallest set of constraints whose relaxation would restore feasibility. The user is told "widen the recipe pool or relax slot constraints" for an FM-1 that was really caused by zero-nutrition data.
- **Precedence between locks, pins, and tags is defined** (lock > pin > required tag > scoring) and implemented consistently. [no issue] The only ambiguity is that a "required" tag silently yields to a lock.
- **No priority among nutrients.** [SPEC] τ is a single scalar applied to iron and to vitamin D alike. The spec's advice to omit vitamin D from targets is contradicted by the shipped example profile, which includes 600 IU. [DATA]
- **Preference has zero weight by design and by accident.** [SPEC] [IMPL] Section 8.2 removes preference from scoring; the unwired tie-break (4.5) removes it from tie-breaking too.

---

## 7. Nutrition targets

- Tolerances are symmetric ±10% for calories, protein, and carbs. A deficit user cares about the upper edge, a bulking user about the lower; the model cannot express either. [SPEC]
- Micronutrient targets are floors only; the only ceilings are ULs, which are absent in the API path (3.4) and partly wrong for food (3.5). [SPEC] [DATA]
- The example profile ships τ = 0.8, below the spec's own 0.85 warning threshold, and the CLI warns on every run. [DATA] [UX]
- RDIs are stated to be "based on maintenance calories, not deficit", but nothing in the model links the calorie target to the RDI set. [SPEC, minor]
- The weekly aggregation with no daily floor allows a valid seven-day plan in which vitamin K, B12, potassium, or fiber (all with null UL) come entirely from one day and are zero on six. [SPEC]

---

## 8. Recipe availability

- Pools of 18 to 32 recipes with three slots per day, HC-2, HC-8, and HC-3 leave very few candidates per slot, and the subset-sum structure (2.1) needs several disjoint feasible day-sets for a week. The formulation is only as good as pool size squared. [DATA]
- Duplicate LLM recipes (2.3) inflate the apparent pool without adding options. [DATA]
- `.cursor/architecture.json` says the tag pre-filter "falls back to full pool if filter result is empty"; `apply_tag_filtering` returns an empty list in that case, which then surfaces as FM-1. Docs and code disagree; the code path is the harsher one. [SPEC] [UX]
- `recipe_ids` in `PlanRequest` silently drops unknown IDs. [IMPL]

---

## 9. Tags

- The canonical tag store is empty, so HC-9 cannot be exercised end-to-end. [DATA]
- Three encodings of one concept exist for time (busyness level, `cooking_time_minutes`, `time-N` tags) and two for dietary exclusion (HC-1 names, `dietary_flags` tags). Each pair can disagree. [SPEC]
- Slot-level preferred tags feed an unbounded bonus (4.4). [ALG]
- Tag lifecycle (proposed / approved / rejected) is well-specified and correctly gated for hard use. [no issue]

---

## 10. Pins

- Pins are persisted at profile level by relative `(day_index, slot_index)`, but a plan has no start date. A "day 0 dinner" pin applies to every plan generated from that profile, whatever day it starts on. [SPEC] [UX]
- Downstream infeasibility caused by a pin (a 1800 kcal pinned breakfast) is promised as FM-3 "downstream" in the spec but surfaces as FM-2 exhaustion, because the search has no way to attribute exhaustion to a pin. [IMPL versus SPEC]
- The 1-based/0-based split and the off-by-one FM-3 report (3.7). [IMPL]

---

## 11. Meal-prep constraints

- Locks conflict with HC-2, HC-8, and HC-3 (3.2, 3.3). This is the most concrete specification conflict in the system: the feature cannot be used for its purpose without failing pre-validation. [SPEC]
- Servings are ignored in nutrition (2.2). [SPEC] [DATA]
- Batch status ("active") is derived from `cook_date` against today's calendar, while the plan it locks into is undated and indexed relatively. A batch cooked last Sunday locks "day 2" of whatever plan is generated next. [SPEC]
- Meal prep is modeled only as a constraint the planner obeys, never as a decision the planner can make. The natural OR framing (choose which recipes to batch so that busy slots become feasible, at a variety cost) is absent. The current design cannot recommend batching. [SPEC]
- The scorer's meal-prep exemption from the variety penalty receives `None` from the search, so it is inert. [IMPL]

---

## 12. Schedule constraints

- Busyness maps to a cooking-time cap and nothing else. Prep-ahead, reheating, and "cook dinner tonight for tomorrow's lunch" are not representable. [SPEC]
- The last slot of the horizon has no next meal, so `time_until_next_meal` is infinite and satiety is always "high" there. [IMPL]
- When `schedule_days` has fewer entries than `days`, the converter pads with the last day rather than cycling; a Monday-to-Friday template asked for seven days repeats Friday twice. Intent is undefined in the spec. [SPEC] [UX]
- `meal_type` is derived positionally and used by nothing. [IMPL]
- Legacy busyness-0 workout entries are correctly converted to explicit workout gaps; activity context is deterministic. [no issue]

---

## 13. Multi-day constraints

- The only cross-day couplings are HC-8 (one day back) and the horizon micronutrient floor. Daily macro windows are independent per day; there is no weekly calorie or protein balance, no ingredient-reuse or shopping coupling, and no cross-day variety beyond one day. [SPEC]
- The horizon floor plus chronological backtracking thrashes (5.2). [ALG]
- Carryover raises later days' scoring targets without any constraint, so the mechanism is advisory; under a per-day UL it can become unrecoverable. [SPEC] [ALG]
- Short horizons are strictest (5.6). [SPEC]

---

## 14. Hidden assumptions

1. A recipe's stored nutrition is one meal for one person. (Unstated; contradicted by `default_servings`.)
2. Ingredient names in recipes and in the exclusion list are drawn from the same canonical vocabulary. (Unstated; false.)
3. The ideal meal is an even split of the remaining daily budget, adjusted by fixed factors. (Section 3.6; the scoring cliff makes it a near-hard assumption.)
4. Database calories are consistent with 4P + 4C + 9F. (Unstated.)
5. Distinct IDs are distinct meals. (Unstated; false in local data.)
6. Reference ULs bound food intake. (Unstated; false for magnesium, niacin, folate, vitamin E.)
7. Every tracked micronutrient is a floor. (Unstated; false for sodium.)
8. A zero nutrient value means the recipe contains none of it. (Unstated; usually means unresolved.)
9. Plans, pins, and batches share a day index origin. (Unstated; plans are undated.)
10. The fat range is a hard range and carbs are a target around a derived value, rather than the reverse. (Stated only by formula.)
11. The first feasible plan is an acceptable plan. (Stated in Section 1, item 5, then contradicted by Sections 8 and 11.)

---

## 15. Technically valid but practically poor plans

Each of these passes every hard constraint and every validation as currently specified.

| Scenario | Why it is valid | Which finding permits it |
|---|---|---|
| The same chicken dish three times a day, seven days, under five different IDs. | HC-2/HC-8 compare IDs. | 2.3 |
| Days alternate A-B-C / D-E-F / A-B-C / D-E-F for a week. | HC-8 looks back one day only. | 3.9 |
| A 900 kcal and a 1400 kcal breakfast rank identically on nutrition match; satiety then prefers the larger one. | Scoring cliff at 10%. | 4.2 |
| 2500 mg sodium every day of a seven-day plan, with the scorer having rewarded sodium while below 1500 mg. | Sodium is a floor; advisory only above 3000 mg/day average. | 4.6 |
| All week's vitamin K on Monday, zero on Tuesday to Sunday. | Prorated horizon floor, no daily floor, null UL. | 7 |
| A 5-minute shake chosen for every 15-minute slot because schedule match prefers the shortest time. | Schedule component formula. | 4.3 |
| A plan that sits at −10% calories, −10% protein, +10% carbs every day when a near-exact plan existed in the pool. | No objective over complete plans. | 4.1 |
| Weekly floor exactly met by a plan whose day 1 is micronutrient-empty. | Carryover is advisory. | 13 |

---

## 16. Summary table

| # | Finding | Labels |
|---|---|---|
| 2.1 | No portion variable; macro windows become subset-sum over atomic recipes | SPEC (IMPL for unreachable carb scaling) |
| 2.2 | "One recipe = one meal" unstated; servings ignored | SPEC, DATA |
| 2.3 | Uniqueness by ID; duplicate LLM recipes | SPEC, DATA |
| 3.1 | HC-1 exact-string allergen matching | SPEC, DATA |
| 3.2 | Meal-prep locks fail HC-2/HC-8 pre-validation | SPEC |
| 3.3 | Meal-prep locks fail HC-3; cook time conflated with per-slot effort | SPEC |
| 3.4 | ULs not passed in API path; demographic hard-coded | IMPL, DATA |
| 3.5 | Magnesium UL < RDI; supplement-only ULs applied to food | DATA, SPEC |
| 3.6 | No HC-5 consistency check; not in API | SPEC, UX |
| 3.7 | Pin pre-validation skips HC-4/HC-9; FM-3 day index off by one | IMPL, UX |
| 3.8 | HC-7 is not a constraint | SPEC |
| 3.9 | HC-8 permits two-day alternation; no ingredient-level variety | SPEC |
| 3.10 | Empty tag store; "required" yields to locks | DATA, SPEC |
| 4.1 | No objective over complete plans; "closest-to-valid" not computed | SPEC, IMPL |
| 4.2 | Per-meal scoring cliff at 10% | ALG, SPEC |
| 4.3 | Ad hoc, unit-blind component formulas; fat diversity missing | IMPL, DATA |
| 4.4 | Unbounded tag bonus | ALG, IMPL |
| 4.5 | Tie-break cascade not implemented; liked foods inert | IMPL, UX |
| 4.6 | Sodium and omega-6 as floors; ratio dropped | SPEC, DATA |
| 5.1 | Loose interval bounds | ALG |
| 5.2 | Horizon floor checked at leaf; chronological backtracking thrashes | ALG |
| 5.3 | Structural FM-4 report misleading; typo becomes "structural" | UX, DATA |
| 5.4 | Unresolved ingredients silently zero; baseline failure misattributed | DATA, UX |
| 5.5 | Coupled macro windows; carbs should be slack | SPEC |
| 5.6 | One-day plans are strictest | SPEC |
| 6 | Flat hard-constraint precedence; no infeasibility diagnosis | SPEC, UX |
| 7 | Symmetric tolerances; uniform τ; vitamin D in default targets | SPEC, DATA, UX |
| 8 | Tag pre-filter empties pool; docs say fallback | SPEC, UX |
| 9 | Duplicate encodings of time and exclusion | SPEC |
| 10 | Undated pins; downstream pin infeasibility reported as FM-2 | SPEC, UX, IMPL |
| 11 | Meal prep is constraint-only, undated, servings-blind | SPEC, DATA, IMPL |
| 12 | Schedule padding semantics; last-slot satiety | SPEC, UX, IMPL |
| 13 | Minimal cross-day coupling; advisory carryover | SPEC, ALG |

---

## 17. What is sound

For balance, the following parts of the formulation hold up under review and should be preserved in any redesign:

- Determinism, fixed decision order, and stable tie-breaking are correctly specified and implemented.
- The hard-constraint predicates in `phase2_constraints.py` are pure, single-purpose, and match their spec text.
- The feasibility bounds are conservative in the correct direction; they never prune a feasible branch.
- Lock > pin > required tag > scoring precedence is clear and consistently applied.
- The tag lifecycle gate (only approved or non-LLM tags may act as hard constraints) is well-defined.
- Structured failure codes with stable `fix_hint` strings are the right contract, even where the current text points at the wrong cause.
- τ is centralized in `micronutrient_policy.py` so acceptance, feasibility, and reporting cannot drift.
