# Macrova planning benchmark (v1)

150 realistic meal-planning requests with oracle-verified expected outcomes, built only from the locally cached ingredients in `.cache/ingredients/`.

| File | What it is |
|---|---|
| `scenarios.json` | The benchmark: 150 scenarios, each with request inputs and an `expected` block |
| `scenarios_index.md` | One row per scenario: categories, horizon, pool size, class, expected code |
| `recipes.json` | 64 single-serving recipes (57 core, 2 duplicate-content, 5 data-hazard) with nutrition computed from the cache |
| `recipe_tags.json` | Tag registry plus `tags_by_id` fixture in the canonical `recipe_tags.json` shape, including LLM-`proposed` tags |
| `library.py`, `scenarios.py` | Source for the recipes and scenarios |
| `oracle.py` | Standalone spec-v3 feasibility oracle. It does not import `src/`. |
| `build.py` | Regenerates everything. `--check` exits 1 if any authored label disagrees with the oracle. |

```bash
python3 evaluation/benchmark/build.py --check
```

```bash
python3 evaluation/benchmark/build.py
```

The build uses only the standard library, takes about 6 seconds, and writes byte-identical output on every run.

## Outcome mix

| Class | Count | Meaning |
|---|---|---|
| feasible | 70 | A valid plan exists, and the tightest day has more than 12 distinct valid recipe sets |
| borderline | 23 | Either a plan exists but the tightest day has 12 or fewer valid recipe sets, or no plan exists at ±10% but one does at ±15% or less |
| infeasible | 57 | No valid plan exists, or the request or batch is rejected before planning |

Expected codes: OK 91, FM-2 17, FM-3 17, FM-1 10, FM-4 5, FM-TAG-EMPTY 6, FM-BATCH-CONFLICT 1, BATCH_REJECTED 2, INVALID_REQUEST 1.

## Coverage by theme

A scenario can carry several themes, and each class is computed by the oracle.

| Theme | n | feasible | borderline | infeasible |
|---|---|---|---|---|
| multi-day | 43 | 34 | 4 | 5 |
| nutrition-conflict | 30 | 9 | 8 | 13 |
| micronutrients | 19 | 13 | 1 | 5 |
| recipe-inventory | 19 | 1 | 5 | 13 |
| meal-timing | 15 | 11 | 2 | 2 |
| preferences | 15 | 7 | 2 | 6 |
| multi-day-conflict | 15 | 0 | 1 | 14 |
| tags | 14 | 13 | 1 | 0 |
| pin-conflict | 13 | 0 | 1 | 12 |
| cook-time | 11 | 3 | 1 | 7 |
| pins | 11 | 7 | 3 | 1 |
| data-quality | 10 | 5 | 2 | 3 |
| meal-prep-conflict | 10 | 0 | 2 | 8 |
| tag-conflict | 9 | 0 | 0 | 9 |
| baseline | 6 | 6 | 0 | 0 |
| meal-prep | 6 | 4 | 2 | 0 |
| calorie-ceiling | 5 | 3 | 0 | 2 |
| safety | 4 | 4 | 0 | 0 |
| input-validation | 3 | 0 | 0 | 3 |

Horizons: 83 one-day, 18 two-day, 22 three-day, 4 four-day, 10 five-day and 13 seven-day. 24 scenarios have pins, 15 have meal-prep batches, 21 have required tags, 19 track micronutrients and 10 have workouts.

Several scenarios look like conflicts but are feasible. The benchmark keeps these on purpose, because a planner that gives up on hard-looking requests should score badly. Examples:

- Dairy-free with 1,200 mg calcium works because calcium-set tofu is in the pool.
- A pinned 1,142 kcal mass gainer on an 1,800 kcal cut still leaves room for the other meals.
- A 7-day, 420 mg magnesium target is reachable.

## Scenario schema

The request fields mirror the real contracts. Every scenario passes `src.api.server.PlanRequest` validation against `recipe_tags.json`, except MB-108, which is meant to be rejected.

```jsonc
{
  "id": "MB-001",
  "title": "...",
  "user_request": "natural-language request as a user would type it",
  "categories": ["pin-conflict", "multi-day-conflict"],
  "intended_class": "infeasible",          // authored label; build fails if it differs from expected.class
  "profile": {
    "daily_calories": 2000, "daily_protein_g": 130,
    "daily_fat_g": {"min": 50, "max": 75},
    "max_daily_calories": null,            // HC-5 ceiling
    "excluded_ingredients": [...],         // HC-1, exact canonical ingredient names (allergies + dislikes)
    "intent_excluded_ingredients": [...],  // present only where the user's intent is broader than the exact string
    "liked_foods": [...],                  // tie-break only
    "demographic": "adult_male",
    "micronutrient_targets": {"iron_mg": 18},
    "micronutrient_weekly_min_fraction": 1.0   // tau
  },
  "horizon_days": 3,
  "schedule_days": [                       // DaySchedule shape; day_index is 1-based
    {"day_index": 1,
     "meals": [{"index": 1, "busyness_level": 2, "tags": ["breakfast"], "preferred_time": "07:30",
                "required_tag_slugs": [...], "preferred_tag_slugs": [...]}],
     "workouts": [{"after_meal_index": 2, "type": "PM", "intensity": "high"}]}
  ],
  "pins": [{"day_index": 0, "slot_index": 0, "recipe_id": "..."}],           // canonical 0-based
  "meal_prep_batches": [{"id": "...", "recipe_id": "...", "total_servings": 3, "cook_date": "2026-09-20",
                         "assignments": [{"day_index": 0, "slot_index": 1, "servings": 1.0}], "status": "planned"}],
  "recipe_pool": {"recipe_ids": [...], "size": 57, "description": "..."},    // maps to PlanRequest.recipe_ids
  "preferences_note": "...", "spec_notes": ["..."],
  "safety_expectation": {"must_not_contain_cache_keys": ["peanut_butter"], "severity": "allergen"},
  "expected": {
    "class": "feasible | borderline | infeasible",
    "outcome": "success | failure",
    "primary_failure_code": null,          // or FM-1 / FM-2 / FM-3 / FM-4 / FM-TAG-EMPTY / FM-BATCH-CONFLICT / INVALID_REQUEST / BATCH_REJECTED
    "acceptable_failure_codes": ["OK"],
    "failure_stage": "complete | input_validation | pre_search | candidate_generation | search",
    "derived_daily_carbs_g": 206.9,
    "intent_outcome": {...},               // only when intent_excluded_ingredients is present
    "oracle": {
      "distinct_meal_sets_per_day": [...], "valid_assignments_per_day": [...],
      "witness_plan": [["recipe", ...], ...],   // a valid plan when one exists
      "min_tolerance_for_feasibility": 0.12,    // for FM-2/FM-3: smallest widened tolerance that works
      "micronutrient_shortfall": {...}
    }
  }
}
```

## How the labels are derived

`oracle.py` checks every scenario exhaustively against the spec in `docs/planner/mealplan-specification-v3.md`. It applies these checks in order:

1. **Tag slugs.** Unknown slugs return `INVALID_REQUEST`. The `batch-cook` alias resolves to `meal-prep`.
2. **Batch creation rules.** These come from `MealPrepBatchRepository._validate_create`. A failure returns `BATCH_REJECTED`.
3. **Batch locks.** Locks are normalized, and they override explicit pins. Two locks on the same slot return `FM-BATCH-CONFLICT`.
4. **Pin pre-validation.** The oracle checks each pin for HC-1, HC-2, HC-3, HC-5 and HC-8, whether it is in range and whether it is in the pool. A failure returns `FM-3`.
5. **Candidate filtering, per slot.** The filters are HC-1, HC-3 and HC-9. HC-9 uses only hard-eligible tags: `nutrition_claim` tags and LLM `proposed` tags do not count, matching `tag_repository`. A slot with no recipes left returns `FM-1`. A slot where only the tag filter removed every recipe returns `FM-TAG-EMPTY`.
6. **Daily windows.** The oracle enumerates every day for kcal, protein and carbs within ±10%, fat within its range and the calorie ceiling. A day with no solution returns `FM-2`, or `FM-3` when the pins caused it.
7. **Multi-day search.** The oracle searches across days with HC-8 and the horizon floor of τ × RDI × D. Failure returns `FM-4` when micronutrients bind, and `FM-1` when HC-8 blocks every day sequence.

`acceptable_failure_codes` lists other codes a conforming implementation may legitimately return. `FM-5` is allowed on any search-stage infeasibility. `FM-4` is allowed where the structural micronutrient pre-check may fire first. `FM-2` is allowed for downstream pin failures.

Checks run on the outputs:

- Every witness plan was re-verified by a separate checker (91 of 91 valid).
- The fixture's hard-eligible tags match `load_hard_eligible_recipe_tag_slugs` for all 64 recipes.
- All 64 fixture entries load through `load_recipe_tags`.

## Caveats a harness must handle

- **The labels follow the spec, not current code.** Known differences between the two:
  - ULs are not wired into `plan_meals`, so the oracle ignores them (reconciliation B1). MB-076 notes that the magnesium UL would make that scenario infeasible.
  - For D = 1, the code skips weekly validation, so one-day micronutrient scenarios may come back as success where the spec says FM-4 (Q8).
  - FC-4 undercounts capacity when a later day has more slots (E3). MB-139 targets this.
  - Batch `servings` are not used in nutrition accounting (MB-129).
- **The unit of nutrition is one serving.** Every recipe is a single serving, so stored nutrition equals one meal and the per-serving vs per-batch question (Q3) cannot confound results.
- **Excluded ingredients are exact names.** HC-1 matches on exact names, as the spec says. The allergen scenarios (MB-143 to MB-146) are feasible under the spec, but they carry `safety_expectation` and `intent_outcome`. A plan that includes peanut butter for a user who wrote "peanuts" is spec-valid and unsafe, so score the two separately.
- **Cache data is partly wrong.** `recipes.json` lists 14 quarantined cache entries under `quarantined_cache_entries`, for example `oats` resolving to oat oil, `eggs` to egg bread, `bell_pepper` to Taco Bell nachos, and `chicken_breast` to a deli roll. There are also several 0-kcal entries. Core recipes avoid these entries, with one exception: `ln_roast_beef_wrap` and `dn_bean_quesadilla` use `tortillas_corn`, which is really a flour tortilla. Neither recipe is tagged gluten-free. Cached vitamin D values are implausible (for example 9,926 IU in the tilapia bowl), so no scenario tracks vitamin D except MB-149, which tests exactly that. The data-quality scenarios deliberately run on the bad entries.
- **Recipe identity is by ID.** MB-084 and MB-085 use three content-identical recipes with different IDs. A spec-valid plan can serve the same meal three times, so a variety metric should count distinct meal contents, not distinct IDs.

## Running it against Macrova

1. Build `PlanRequest` from each scenario's `profile`, `schedule_days`, `horizon_days` and `recipe_pool.recipe_ids`.
2. Put `excluded_ingredients` into `disliked_foods`, and `micronutrient_targets` into `micronutrient_goals`.
3. Load the recipes from `recipes.json`. Point `NUTRITION_TAG_REPO_PATH` and `recipe_tags_path` at `recipe_tags.json`.
4. Supply pins and batches through the profile pin and meal-prep repositories. `PlanRequest` has no pin or batch fields.
5. Score each run on:
   - the outcome and failure code against `expected`;
   - hard-constraint validity of any returned plan (re-check it; do not trust `success`);
   - `safety_expectation` violations;
   - distinct-content variety.
