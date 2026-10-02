# Planner benchmark v1: failure analysis

**Date:** 2026-09-18
**Snapshot:** branch `140-dollar-sprint`, commit `58e1ed8`, `.venv` Python 3.12. Nothing in `src/`, `data/`, or `config/` was modified.
**Inputs:** `evaluation/benchmark/` (151 scenarios with oracle labels), `docs/planner/mealplan-specification-v3.md`, `evaluation/reports/reconciliation.md`.
**Method:** ran every scenario through the real planner with `evaluation/harness/run_benchmark.py`, compared the outcome and failure code against the oracle labels, and re-checked every returned plan against the hard constraints with a checker that does not import `src/planning` (`evaluation/harness/compare.py`). Then clustered the disagreements by root cause, confirmed each cause in source, and tested the causes with counterfactual runs and targeted probes.

---

## 1. Summary

| Result | Count |
|---|---|
| Exact match with oracle | **151** (was 149 after C4/C5; 145 after C2a; 125 after C2b; 123 before C2b; 112 after C3; 109 before C1) |
| Different code, but listed in `acceptable_failure_codes` | 0 |
| Disagreement | **0** |

The original 39 disagreements came from **7 root causes**, not 39 separate bugs. C1–C6 are fixed.

- **Wrong-code-only diagnoses for C2a/C2b are resolved** (20 + 2 scenarios now MATCH).
- **C6 allergy class expansion** closes the last two unsafe-success disagreements (MB-143, MB-145).

On infeasible requests, the planner reaches the correct *outcome* in all labelled cases that remain measurable on this harness. Multi-day micronutrient floors (C4) and the D=1 floor gap (C5) are closed by the tight valid-day bound; allergy intent (C6) is closed by class expansion at profile conversion.

Four more issues don't appear in the score at all, because the harness had to route around them or the benchmark doesn't measure them. Section 4 covers them. The calorie ceiling API gap (§4.1) is fixed.

## 2. How the harness runs scenarios

The harness follows the same steps as `/api/v1/plan`: `PlanRequest` validation, `_build_user_profile`, `convert_profile`, `_attach_canonical_recipe_tags`, then `plan_meals`. There are two deliberate deviations:

1. **Nutrition is injected, not computed.** A stub calculator returns each recipe's stored per-serving nutrition from `recipes.json`, which is exactly what the oracle used. This follows the reconciliation's advice (§5) to keep the data track and the search track separate. Nothing here measures the ingredient-resolution layer.
2. **Pins and batches go through the real repositories.** Pins become `ProfilePin`. Batches go through `MealPrepBatchRepository.create` (including `_validate_create`), then `list_active()`, then `planning_batch_locks_from_batches`, which matches what `hydrate_parity_plan_context` does.

## 3. Root-cause clusters

### C1. Meal-prep batches with every serving assigned are silently dropped (11 scenarios)

**Status:** fixed. `consumed` is set only by an explicit saved action (`cancel()`); assignment count no longer changes status, so fully assigned batches stay in `list_active()` and all 11 C1 scenarios match.

**Type:** API/contract issue (what a batch's lifecycle status means). **Scenarios:** MB-028, 117, 118, 119, 120, 124, 126, 127, 128, 129, 130.

**Cause (historical, fixed):** `_effective_status` in `src/data_layer/meal_prep.py` used to set a batch's status to `"consumed"` when `servings_remaining == 0`. `servings_remaining` is `total_servings − Σ assigned servings`, so "every serving has a slot", which is the normal way to use meal prep, counts the same as "already eaten". `list_active()` then leaves the batch out, and the planner never sees its locks. A batch only reaches the planner if it has spare servings. That's why MB-121 and MB-125 work.

**Effect:**
- 5 scenarios return **success** where the spec requires FM-3 (MB-117, 118, 119, 124, 130). The locked recipe breaks cook-time, HC-8 or exclusion rules, but because the lock was dropped, nothing checks it.
- 6 scenarios return plans that put something else in the slot the user prepped for.
- There is no warning in any of these cases.

**Counterfactual (now realized by the fix):** with `ALL_BATCHES=1`, which hands every non-orphaned batch to the planner, all 15 batch scenarios matched the oracle; after the fix the default `list_active()` path gives the same result. Since the fix, `ALL_BATCHES` differs from `list_active()` only by also including explicitly cancelled (`consumed`) batches, so it is no longer a pure counterfactual. Everything downstream of `list_active()` (lock-to-pin merge, pre-validation, the FM-BATCH-CONFLICT and FM-3 reports) is correct. The whole defect is this one status rule.

### C2a. When the search runs out of options, the failure code comes from the last event, not the cause (20 scenarios)

**Status:** fixed. Post-search attribution (steps 2–3 in `src/planning/failure_attribution.py`) rewrites exhausted FM-1/FM-2 exits: day check → FM-2 or FM-3; across-days → FM-4 or FM-1. All 20 C2a scenarios MATCH.

**Type:** planner defect in how failures are reported, plus a spec gap. **Scenarios:** all 17 scenarios expected to fail with FM-2 (MB-013, 030, 046, 050–057, 060, 064, 083, 084, 087, 138), plus MB-065 (expected FM-4) and MB-147/148 (expected FM-3).

**Cause (historical, fixed):** the planner could reach "nothing left to try" in two places, and they reported different codes:
- when a slot's list of candidates has been used up: reported as FM-2;
- when building a slot's candidate list comes back empty because the macro feasibility checks FC-1/FC-2 or the look-ahead FC-5 removed everything: reported as **FM-1 "Empty candidate set or FC-5"**.

On a day where no combination of recipes fits the macro targets, the search almost always ended on the second path. So a macro conflict was reported as a recipe-pool shortage. **The planner never returned FM-2 for a genuinely macro-infeasible day in this benchmark (0 of 17) before the fix.**

**Spec gap (closed):** §11 now states the attribution rule for choosing a code when exhaustive search ends (day check → FM-2/FM-3; across-days → FM-4 or FM-1; inconclusive fallback keeps the last-event code).

**Effect (historical):** the outcome was correct in all 20. The diagnosis was wrong in all 20. Users were told to "widen the recipe pool or relax slot constraints" when the real problem was conflicting macro targets, a pinned meal, or a micronutrient floor.

### C2b. A required-tag failure is hidden by the look-ahead check (2 scenarios)

**Status:** fixed. Static slot check before search reports FM-TAG-EMPTY/FM-1 for the first unfillable slot, ahead of FC-5.

**Type:** planner defect. **Scenarios:** MB-107, MB-114.

**Cause:** FM-TAG-EMPTY is only checked when the search reaches the slot with the required tag. The FC-5 look-ahead at an earlier slot on the same day spots that slot's empty candidate set first and ends the search through the FM-1 path. The four FM-TAG-EMPTY scenarios that match all put the tagged slot at slot 0. The two that fail put it at slot 2 and slot 1.

**Effect:** the right failure, but the wrong code and the wrong slot. The fix hint doesn't name the tag.

### C3. A day where every slot is pinned is never validated (1 scenario, plus probes)

**Status:** fixed. Fully pinned days are validated before search (FM-3 on failure) and completed through the shared day-completion / end-of-plan path on success. Covered by MB-099, MB-151, and `evaluation/harness/probes.py`.

**Type:** planner defect; a hard constraint can go unchecked. **Scenarios:** MB-099, plus MB-098, which got an acceptable code by coincidence.

**Cause:** a pinned slot is already filled when the search starts, so the loop just moves past it with `i += 1; continue` (`phase7_search.py:703-706`). That skips the day-completion step (`_daily_validation`, `_update_weekly_after_day`, `completed_days`) and the end-of-plan success check. A day with at least one free slot is still validated when its last *free* slot is filled. **A day with no free slots never is.**

**Effect:**

| Case | Result |
|---|---|
| MB-099: one-day plan, all slots pinned, fits every window | **FM-2** ("exhaustion"), should be OK |
| Probe P2: 2 days, day 0 fully pinned at 1,376 kcal against a 1,800 target | **success**; the re-check finds the kcal, protein and carbs windows all broken on day 0 |
| Probe P3: same plan with fiber tracked | FM-4 reports 15.9 g "achieved", which is day 1 alone. Day 0's 15.7 g is missing from the weekly total. |

P2 is the most serious finding in this report: **the planner returns a plan that breaks the hard macro constraints and calls it a success.** The benchmark doesn't include a fully pinned day inside a longer plan, so the score misses it.

### C4. Day-by-day backtracking gets stuck on multi-day micronutrient floors (2 scenarios)

**Status:** fixed. Tight `max_daily_achievable` from enumerated valid days plus per-slot prefix/suffix pruning; MB-068/MB-071 succeed within 50k, MB-067 is pre-search FM-4.

**Type:** planner algorithm defect. **Scenarios:** MB-068, MB-071 (feasible, returned FM-5), and MB-067 (infeasible, returned FM-5; accepted).

**Evidence (before fix):** MB-068 still returned FM-5 at 200,000 attempts (42 s, 151,906 backtracks). The oracle finds a valid plan in **25** multi-day search nodes. So this was the search order, not the attempt budget.

This settles **reconciliation Q5** for these instances. The scope was narrow: 11 of the 13 feasible or borderline multi-day micronutrient scenarios already succeeded. The fix reuses day enumeration from C2a attribution (`_enumerate_day`) to replace the loose top-M FC-4 bound, checks the bound at every slot, and keeps top-M as a fallback when primary-carb downscaling is on or enumeration is capped.

### C5. One-day plans skip the end-of-plan micronutrient check (1 scenario)

**Status:** fixed (as a side effect of C4). The tight structural check rejects MB-059 pre-search with FM-4 when no valid day can reach the floor, so the up-front bound and the intended final floor agree for D=1 without waiting on reconciliation Q8's success-path weekly check.

**Type:** was spec ambiguity (reconciliation Q8). **Scenario:** MB-059.

For D = 1, the planner still returns success before `_weekly_validation` runs when the pool *can* meet the floor. When it cannot, structural FM-4 now fires (previously the loose top-M bound let search succeed with 23 mg vitamin C against a 400 mg floor). Q8 remains open only for the success-path question of whether D=1 should run the same weekly soft-deficit reporting as D>1.

### C6. Allergy exclusion matches exact ingredient names only (2 scenarios)

**Status:** fixed (Q10 = guarantee). Allergy terms expand via `data/reference/allergen_classes.json` at `convert_profile`; dislikes stay exact. One HC-1 matcher; unmatched terms warn; classification required for committed ingredients and LLM drafts.

**Type:** was spec ambiguity (reconciliation Q10). **Scenarios:** MB-143 (`peanuts` → excludes `peanut butter`), MB-145 (`dairy` → milk-class members including cheese).

MB-144 remains clean under class expansion. **Follow-ups (out of scope for C6):** unify `dietary_flags` with HC-1; fix MB-146 (recipe tag that lies); substring matchers in `recipe_scorer` / `recipe_retriever`; validator prefix false positives (`egg`↔`eggplant`); gate user-authored recipes outside the LLM path.

## 4. Issues the scorecard hides

### 4.1 The calorie ceiling can't reach the planner through the API (API/contract issue)

**Status:** fixed. `PlanRequest` carries `max_daily_calories`, `_build_user_profile` passes it through, the OpenAPI snapshot and Flutter `PlanRequest`/`UserProfile` send it, and the harness no longer overrides the profile after `_build_user_profile`.

Previously `PlanRequest` (`src/api/server.py`) had no `max_daily_calories` field, and `_build_user_profile` never set one. The CLI's YAML loader (`src/data_layer/user_profile.py`) carried the number, but the Flutter model only treated `max_daily_calories` as an on/off flag (`calorieDeficitMode`) and dropped the value. HC-5 therefore worked in the CLI and in the harness override path, but not over HTTP.

With `API_FIDELITY=1` (now removed), which reproduced the API's old behaviour, on the 5 ceiling scenarios:

| Scenario | Ceiling | Result through the API |
|---|---|---|
| MB-035 | 1,800 | success at **1,830 kcal** (over the ceiling) |
| MB-054 | 1,700 | success at **2,110 kcal**, should be FM-2 |
| MB-095 | 1,100 | FM-1, should be FM-3 |
| MB-019, MB-074 | — | unaffected |

The benchmark README's run instructions ("build `PlanRequest` from each scenario's profile") therefore led to a harness that silently tested without HC-5. That gap is closed.

### 4.2 Negative derived carbs are accepted (validation issue)

In MB-053, the targets imply −10 g of carbs per day. The backend accepts that and plans against it. The frontend clamps derived carbs to 0 (`frontend/lib/models/user_profile.dart:449-451`), so the two sides disagree about the same profile. Neither rejects it.

### 4.3 A slot's meal type is only a label (spec ambiguity and a gap in the benchmark)

`MealSlot.meal_type` is described as a "Label" (spec line 129). It isn't used in the hard constraints, candidate generation or scoring. In the 94 successful plans:

- **45%** of slots (322 of 708) hold a recipe not tagged for that meal type;
- **53%** of breakfast slots hold a non-breakfast recipe;
- **85 of 94** plans have at least one mismatch.

The oracle doesn't check meal type either, so the benchmark reports these plans as correct. Whether "breakfast" on a slot is a constraint, a scoring preference or just a label is a product decision the spec hasn't made.

### 4.4 The data track is untested → measured (E0 / E1 / E1b)

**Status:** measured (draft panel; decision gate open — see reconciliation Q1/Q2). Harness: `evaluation/data_track/` (`reproduce.py`, `decompose.py`, `cache_audit.py`). Results: `evaluation/data_track/results/e{0,1,1b}.json` (generated, gitignored; summary in `results/decision_gate.md`).

Every benchmark result still uses **stored** nutrition (`StubCalc` in `evaluation/harness/run_benchmark.py`). `/api/v1/plan` recomputes via `NutritionCalculator` from `ingredient_source` local or api. No §3 disagreement is caused mainly by bad data; this section measures the ingredient layer the scorecard skips.

#### E0 — reproduce the real path

| Config | Benchmark (64 recipes) | Notes |
|---|---|---|
| `local-machine` / `local-clean` | **64/64** recipes have ≥1 skipped ingredient; median \|Δkcal\| vs stored ≈ **489** | Local JSON has **7** entries; `NutritionDB` has **no fallback**. `calculate_recipe_nutrition` silently `continue`s on `IngredientNotFoundError`. |
| `api-cache` | **0** skips; median \|Δkcal\| ≈ **0** | Stored benchmark nutrition **is** the cache recomputation. |
| `api-clean` | `resolve_all` **hard-fails** on first miss | API path does **not** silent-zero; it raises `IngredientResolutionError`. |

Also confirmed: `data/recipes/recipes.json` is gitignored (only `.example` is committed), same class of problem as untracked `custom_ingredients.json`. A fresh clone cannot reproduce this machine's nutrition.

#### E1 — error decomposition (draft panel, 78 ingredients)

Against hand-chosen correct FDC IDs (`panel.json`, `review_status: draft`):

| Channel | Share of abs kcal error (all four) | Share excluding coverage |
|---|---|---|
| **coverage** (absent from local source) | **84.0%** | — |
| **resolution** (wrong USDA food) | **15.5%** | **96.3%** |
| **mapping** (cache ≠ remap of same raw) | **0.0%** of kcal | **0.0%** of kcal |
| **units** (volume/count as grams) | **0.6%** | **3.7%** |

- **13** wrong resolutions (quarantine list minus acai, where no fruit FDC exists). Worst kcal/100 g gaps: oats→oil (+505), bell pepper→nachos (+330), banana→powder (+257), eggs→egg bread (+144).
- **20** recipes with api-cache kcal **>20%** off truth; all resolution-dominated.
- Units bite on `tbsp`/`tsp`/`cup` (calculator treats quantity as grams): e.g. 2 tbsp yogurt → 2 g instead of ~30 g; 1 cup tomato → 1 g instead of ~180 g.
- Mapping contributes negligible **kcal** but large **micronutrient** error on salmon (see E1b).

#### E1b — cache provenance

83 cache entries vs current `NutrientMapper`: **82 consistent**, **1 superseded** (`salmon_canned`: cached vitamin D 761 IU vs remapped **30,459** IU; omega-3 5.0 vs 0.695 g). Egg yolk is consistent. Four keys have **0 kcal with carbs** (`kiwi_fruit_green`, `mushrooms`, `sweet_potato`, `tomato`); `spaghetti_squash` is 0/0. **Recommendation: patch** (not full rebuild) — drop/replace quarantined wrong-food keys and fix salmon; fraction superseded ≈ 1.2%.

#### Decision gate → fix (Q2 = d+a)

Decisions: curated table + plausibility; drop unresolved recipes with warnings; commit `data/recipes/recipes.json` and keep example/benchmark coverage; fix order as measured.

Shipped: `data/reference/ingredient_nutrition.json` (default local source; `review_status: draft`, human review pending), `convert_recipes(drop_unresolved=True)` + `warnings.nutrition`, cache plausibility gate, coverage test `tests/test_ingredient_nutrition_reference.py`, harness `--nutrition computed`.

## 5. Classification

| Category | Clusters | Open disagreements |
|---|---|---|
| Planner algorithm defect | C4 fixed (C2a/C2b/C3 fixed) | 0 |
| API/contract issue | §4.1 fixed, C1 fixed | 0 |
| Specification ambiguity | C5 fixed (structural agreement); C6 done; §4.3 open; **§4.4 Q2 open** | 2 (meal-type + data acceptability) |
| Validation issue | §4.2 | 0 (hidden) |
| Recipe/data limitation | **§4.4 measured** — coverage dominates local; resolution dominates api-cache | 0 planner mismatches (data track separate) |
| Expected infeasibility | 57 of 57 infeasible scenarios fail correctly after C5 | — |
| Test-design problem | no meal-type scoring (§4.3); no fully pinned day inside a multi-day plan (C3, fixed); **benchmark uses stored nutrition only** | 0 |

C2a's spec gap is closed in §11 attribution steps 2–3.

## 6. Recurring patterns

1. **Wrong last-event failure codes (C2a, C2b; fixed).** Post-search attribution and the static slot pre-check now choose the structural cause.
2. **Silent drops at the edges (C5 fixed via C4 bound; C1/C3/§4.1 fixed).** The calorie ceiling reaches the planner over HTTP; impossible micronutrient floors fail pre-search for D=1 and multi-day alike.
3. **Search order against multi-day micronutrient floors (C4; fixed).** Valid-day enumeration and per-slot pruning replace the loose top-M bound.

## 7. Suggested order

| Order | Item | Why this position |
|---|---|---|
| 1 | C1 batch status | **Done.** One condition; 11 scenarios, all now match |
| 2 | C3 fully pinned day validation | **Done.** Hard constraint checked; fully pinned days validated |
| 3 | §4.1 ceiling in `PlanRequest` | **Done.** HC-5 reaches the planner over HTTP; OpenAPI and Flutter carry the number |
| 4 | C2a / C2b failure attribution | **Done.** C2b static pre-check + C2a post-search steps 2–3; 22 diagnoses corrected; exact matches 125 → 145 |
| 5 | C4 search order (+ C5 structural agreement) | **Done.** Tight valid-day FC-4 bound and per-slot pruning; 145 → 149 exact; MB-067 ACCEPTABLE → MATCH |
| 6 | C6 allergy class expansion (Q10) | **Done.** Allergies expand via allergen class table; harness sends safety scenarios as allergies; 149 → 151 exact |
| 7 | §4.4 data track (Q1) | **Measured.** E0/E1/E1b in `evaluation/data_track/`; coverage then resolution dominate. Fix blocked on Q2 gate. |
| — | §4.2, §4.3 | Remaining specification decisions (input validity, meal type) |

Fixes 1–6 have resolved their clusters: the benchmark is at **151 of 151** exact matches. MB-151 (a fully pinned day inside a two-day plan) keeps C3 covered by the benchmark.

## 8. Reproducing

```bash
.venv/bin/python evaluation/harness/run_benchmark.py
```

```bash
.venv/bin/python evaluation/harness/compare.py
```

```bash
.venv/bin/python evaluation/harness/probes.py
```

Counterfactual runs set environment variables on `run_benchmark.py`:
- `ALL_BATCHES=1`: pass every non-orphaned batch, including cancelled ones, to the planner (C1 counterfactual; now differs from the default only by cancelled batches);
- `LIMIT=200000`: raise the attempt limit (tests C4);
- `OUT=<path>`: write results to a different file.

Raw outputs are in `evaluation/harness/results/`. The full run takes about 5–7 seconds after C4 (was ~36 s when C4 scenarios exhausted the attempt budget). The harness imports `src/`; `compare.py`'s plan checker only uses the tag loader and the oracle's constants.
