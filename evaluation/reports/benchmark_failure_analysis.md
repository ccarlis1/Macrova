# Planner benchmark v1: failure analysis

**Date:** 2026-09-18
**Snapshot:** branch `140-dollar-sprint`, commit `58e1ed8`, `.venv` Python 3.12. Nothing in `src/`, `data/`, or `config/` was modified.
**Inputs:** `evaluation/benchmark/` (150 scenarios with oracle labels), `docs/planner/mealplan-specification-v3.md`, `evaluation/reports/reconciliation.md`.
**Method:** ran every scenario through the real planner with `evaluation/harness/run_benchmark.py`, compared the outcome and failure code against the oracle labels, and re-checked every returned plan against the hard constraints with a checker that does not import `src/planning` (`evaluation/harness/compare.py`). Then clustered the disagreements by root cause, confirmed each cause in source, and tested the causes with counterfactual runs and targeted probes.

---

## 1. Summary

| Result | Count |
|---|---|
| Exact match with oracle | 109 |
| Different code, but listed in `acceptable_failure_codes` | 2 (MB-067, MB-098) |
| Disagreement | **39** |

The 39 disagreements come from **7 root causes**, not 39 separate bugs.

- **17 give the user a wrong answer:** a success that should be a failure, a failure that should be a success, a plan that breaks a constraint, or an unsafe plan.
- **22 reach the right outcome with the wrong failure code**, so the fix hint points the user at the wrong problem.

On infeasible requests, the planner reaches the correct *outcome* in 51 of 57. The six misses come from two causes, C1 and C5. The planner's main weakness is explaining failures, not detecting them.

Four more issues don't appear in the score at all, because the harness had to route around them or the benchmark doesn't measure them. Section 4 covers them. The most serious is that the calorie ceiling can't reach the planner through the API.

## 2. How the harness runs scenarios

The harness follows the same steps as `/api/v1/plan`: `PlanRequest` validation, `_build_user_profile`, `convert_profile`, `_attach_canonical_recipe_tags`, then `plan_meals`. There are three deliberate deviations:

1. **Nutrition is injected, not computed.** A stub calculator returns each recipe's stored per-serving nutrition from `recipes.json`, which is exactly what the oracle used. This follows the reconciliation's advice (§5) to keep the data track and the search track separate. Nothing here measures the ingredient-resolution layer.
2. **Pins and batches go through the real repositories.** Pins become `ProfilePin`. Batches go through `MealPrepBatchRepository.create` (including `_validate_create`), then `list_active()`, then `planning_batch_locks_from_batches`, which matches what `hydrate_parity_plan_context` does.
3. **`max_daily_calories` is set on the profile directly**, because `PlanRequest` has no field for it (see §4.1). Setting `API_FIDELITY=1` reproduces what the API actually does.

## 3. Root-cause clusters

### C1. Meal-prep batches with every serving assigned are silently dropped (11 scenarios)

**Type:** API/contract issue (what a batch's lifecycle status means). **Scenarios:** MB-028, 117, 118, 119, 120, 124, 126, 127, 128, 129, 130.

**Cause:** `src/data_layer/meal_prep.py:124` sets a batch's status to `"consumed"` when `servings_remaining == 0`. `servings_remaining` is `total_servings − Σ assigned servings` (`meal_prep.py:37`), so "every serving has a slot", which is the normal way to use meal prep, counts the same as "already eaten". `list_active()` then leaves the batch out, and the planner never sees its locks. A batch only reaches the planner if it has spare servings. That's why MB-121 and MB-125 work.

**Effect:**
- 5 scenarios return **success** where the spec requires FM-3 (MB-117, 118, 119, 124, 130). The locked recipe breaks cook-time, HC-8 or exclusion rules, but because the lock was dropped, nothing checks it.
- 6 scenarios return plans that put something else in the slot the user prepped for.
- There is no warning in any of these cases.

**Counterfactual:** with `ALL_BATCHES=1`, which hands every non-orphaned batch to the planner, **all 15 batch scenarios match the oracle**. Everything downstream of `list_active()` (lock-to-pin merge, pre-validation, the FM-BATCH-CONFLICT and FM-3 reports) is correct. The whole defect is this one status rule.

### C2a. When the search runs out of options, the failure code comes from the last event, not the cause (20 scenarios)

**Type:** planner defect in how failures are reported, plus a spec gap. **Scenarios:** all 17 scenarios expected to fail with FM-2 (MB-013, 030, 046, 050–057, 060, 064, 083, 084, 087, 138), plus MB-065 (expected FM-4) and MB-147/148 (expected FM-3).

**Cause:** the planner can reach "nothing left to try" in two places, and they report different codes:
- when a slot's list of candidates has been used up: reported as FM-2 (`phase7_search.py:~858`);
- when building a slot's candidate list comes back empty because the macro feasibility checks FC-1/FC-2 or the look-ahead FC-5 removed everything: reported as **FM-1 "Empty candidate set or FC-5"** (`phase7_search.py:776-790`).

On a day where no combination of recipes fits the macro targets, the search almost always ends on the second path. So a macro conflict is reported as a recipe-pool shortage. **The planner never returned FM-2 for a genuinely macro-infeasible day in this benchmark (0 of 17).** The report can even contradict itself: MB-107 is reported as FM-1 with `eligible_recipe_count: 34`.

**Spec gap:** the spec defines each failure mode's *condition*. FM-1 means there aren't enough recipes that pass the hard constraints (§ FM-1). FM-2 means there are enough recipes but no combination hits the targets (§ FM-2). But its *detection* rules only describe where each mode can fire, not which code to report when an exhaustive search ends. The implementation fills that gap with whatever happened last.

**Effect:** the outcome is correct in all 20. The diagnosis is wrong in all 20. Users are told to "widen the recipe pool or relax slot constraints" when the real problem is conflicting macro targets, a pinned meal, or a micronutrient floor.

### C2b. A required-tag failure is hidden by the look-ahead check (2 scenarios)

**Type:** planner defect. **Scenarios:** MB-107, MB-114.

**Cause:** FM-TAG-EMPTY is only checked when the search reaches the slot with the required tag. The FC-5 look-ahead at an earlier slot on the same day spots that slot's empty candidate set first and ends the search through the FM-1 path. The four FM-TAG-EMPTY scenarios that match all put the tagged slot at slot 0. The two that fail put it at slot 2 and slot 1.

**Effect:** the right failure, but the wrong code and the wrong slot. The fix hint doesn't name the tag.

### C3. A day where every slot is pinned is never validated (1 scenario, plus probes)

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

**Type:** planner algorithm defect. **Scenarios:** MB-068, MB-071 (feasible, returned FM-5), and MB-067 (infeasible, returned FM-5; accepted).

**Evidence:** MB-068 still returns FM-5 at 200,000 attempts (42 s, 151,906 backtracks). The oracle finds a valid plan in **25** multi-day search nodes. So this is the search order, not the attempt budget.

This settles **reconciliation Q5** for these instances. The planner fails on feasible instances even with correct nutrition data, and raising the cap doesn't help. The scope is narrow: 11 of the 13 feasible or borderline multi-day micronutrient scenarios succeed.

### C5. One-day plans skip the end-of-plan micronutrient check (1 scenario)

**Type:** spec ambiguity (reconciliation Q8). **Scenario:** MB-059.

For D = 1, the planner returns success before `_weekly_validation` runs (`phase7_search.py:980`). MB-059 comes back as success with 23 mg vitamin C against a 400 mg floor, and no warning. The up-front structural check didn't fire because its per-slot upper bound is looser than what's actually reachable. The code needs no fix until Q8 is decided, but whatever is decided, the up-front check and the final check must agree.

### C6. Allergy exclusion matches exact ingredient names only (2 scenarios)

**Type:** spec ambiguity (reconciliation Q10); the planner behaves as the spec says. **Scenarios:** MB-143 (the plan includes `bk_pb_banana_toast` for a user who excluded "peanuts"), MB-145 (the plan includes `dn_bean_quesadilla` against an intent exclusion).

These plans are valid by the spec and unsafe for the user. MB-144 and MB-146 passed only because the planner happened not to pick an affected recipe. The benchmark's README already says to score safety separately. This cluster stays open until Q10 decides whether HC-1 is a safety guarantee.

## 4. Issues the scorecard hides

### 4.1 The calorie ceiling can't reach the planner through the API (API/contract issue)

`PlanRequest` (`src/api/server.py:130`) has no `max_daily_calories` field, and `_build_user_profile` never sets one. The CLI's YAML loader (`src/data_layer/user_profile.py:283`) and the Flutter model (`frontend/lib/models/user_profile.dart:454`) both carry it, so HC-5 works everywhere except the HTTP API.

With `API_FIDELITY=1`, which reproduces the API's behaviour, on the 5 ceiling scenarios:

| Scenario | Ceiling | Result through the API |
|---|---|---|
| MB-035 | 1,800 | success at **1,830 kcal** (over the ceiling) |
| MB-054 | 1,700 | success at **2,110 kcal**, should be FM-2 |
| MB-095 | 1,100 | FM-1, should be FM-3 |
| MB-019, MB-074 | — | unaffected |

The benchmark README's run instructions ("build `PlanRequest` from each scenario's profile") therefore lead to a harness that silently tests without HC-5.

### 4.2 Negative derived carbs are accepted (validation issue)

In MB-053, the targets imply −10 g of carbs per day. The backend accepts that and plans against it. The frontend clamps derived carbs to 0 (`frontend/lib/models/user_profile.dart:449-451`), so the two sides disagree about the same profile. Neither rejects it.

### 4.3 A slot's meal type is only a label (spec ambiguity and a gap in the benchmark)

`MealSlot.meal_type` is described as a "Label" (spec line 129). It isn't used in the hard constraints, candidate generation or scoring. In the 94 successful plans:

- **45%** of slots (322 of 708) hold a recipe not tagged for that meal type;
- **53%** of breakfast slots hold a non-breakfast recipe;
- **85 of 94** plans have at least one mismatch.

The oracle doesn't check meal type either, so the benchmark reports these plans as correct. Whether "breakfast" on a slot is a constraint, a scoring preference or just a label is a product decision the spec hasn't made.

### 4.4 The data track is untested

Every result above uses the stored nutrition. Through the real `/api/v1/plan` path, nutrition would be recomputed from `data/ingredients` with the problems listed in `recipes.json → quarantined_cache_entries` (oats resolved to oat oil, and so on). No disagreement in §3 is caused mainly by bad data. MB-083, 084, 138, 147 and 148 are correctly infeasible and only get the wrong code (C2a). The data-quality scenarios measure the planner's reporting, not the ingredient layer.

## 5. Classification

| Category | Clusters | Disagreements |
|---|---|---|
| Planner algorithm defect | C2a (partly), C2b, C3, C4 | 25 |
| API/contract issue | C1, §4.1 | 11 (plus 3 hidden) |
| Specification ambiguity | C5, C6, C2a (the spec gap), §4.3 | 3 (plus the meal-type finding) |
| Validation issue | §4.2 | 0 (hidden) |
| Recipe/data limitation | none as a primary cause (see §4.4) | 0 |
| Expected infeasibility | 51 of 57 infeasible scenarios fail correctly; the 6 misses are C1 and C5 | — |
| Test-design problem | README run instructions (§4.1); no meal-type scoring (§4.3); no fully pinned day inside a multi-day plan (C3) | 0 |

C2a appears in two rows: the code is wrong whatever the spec says, and the spec should also state the rule for choosing a code.

## 6. Recurring patterns

1. **The failure code comes from the last thing that happened, not the cause (C2a, C2b; 22 scenarios).** The planner is good at deciding that a request is infeasible and bad at saying why. Every failure path through candidate generation collapses into FM-1.
2. **Silent drops at the edges (C1, C3, C5, §4.1).** A batch, a fully pinned day, a one-day micronutrient floor or a calorie ceiling disappears somewhere between input and search, and the run still reports success with no warning. This is the reconciliation's "strict gate, silent exit" pattern (§2.2), and it goes well beyond Q8.
3. **Pinned and locked slots take a separate path in the search loop that skips checks (C3).** This compounds with C1: once batches reach the planner again, more slots take that path. The 15 batch scenarios don't include a fully locked day, so fixing C1 alone won't expose C3 in this benchmark. It will in real use.
4. **Search order against multi-day micronutrient floors (C4).** This is the only cluster that needs a design change rather than a local fix.

## 7. Suggested order

| Order | Item | Why this position |
|---|---|---|
| 1 | C1 batch status | One condition; 11 scenarios; the counterfactual already confirms the fix |
| 2 | C3 fully pinned day validation | A hard constraint goes unchecked and the plan is returned as success |
| 3 | §4.1 ceiling in `PlanRequest` | HC-5 doesn't work over HTTP; also update the OpenAPI snapshot and the frontend model |
| 4 | C2a / C2b failure attribution | Corrects 22 diagnoses; needs a one-paragraph spec rule first |
| 5 | C4 search order | A design change; the benchmark gives a clear pass/fail target |
| — | C5, C6, §4.2, §4.3 | Specification decisions (Q8, Q10, input validity, meal type) come before code |

If fixes 1–4 resolve their clusters, the benchmark should reach 145 of 150 (111 + 11 + 1 + 20 + 2). The remaining 5 are C4 (2 scenarios), C5 (1) and C6 (2), which wait on a design change or spec decisions. Adding a probe P2-style scenario (a fully pinned day inside a multi-day plan) to `scenarios.py` would keep C3 covered by the benchmark.

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
- `ALL_BATCHES=1`: pass every non-orphaned batch to the planner (tests C1);
- `API_FIDELITY=1`: drop the calorie ceiling, as the API does (§4.1);
- `LIMIT=200000`: raise the attempt limit (tests C4);
- `OUT=<path>`: write results to a different file.

Raw outputs are in `evaluation/harness/results/`. The full run takes about 36 seconds. The harness imports `src/`; `compare.py`'s plan checker only uses the tag loader and the oracle's constants.
