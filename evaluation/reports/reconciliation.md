# Reconciliation: architecture tribunal vs. OR formulation review

**Date:** 2026-09-17
**Inputs:** `evaluation/reports/architecture_tribunal.md`, `evaluation/reports/or_formulation_review.md`, `evaluation/initial_state.md`
**Method:** read both reports in full, then re-read source at every point where the two disagree or where only one report made a load-bearing claim. Verifications are marked **[verified]** with the file and line. No code was changed.

---

## 0. What the two reports are, and why they mostly do not overlap

The tribunal is an **adversarial audit of the numbers and the plumbing**: does the data entering the planner mean what it claims, and are the advertised constraints actually wired to an entry point. The OR review is a **formulation critique**: is the problem stated correctly as a constraint model, independent of whether the data is right.

They share only one region — constraints and feasibility — and in that region they largely corroborate each other. Outside it they are complementary, not redundant: the tribunal has no view on the objective function, and the OR review has no view on the LLM pipeline, the test suite, or CI.

The combined statement neither report makes alone:

> Macrova is an unvalidated constraint-satisfaction model running over unvalidated nutrition vectors. Because the numbers are wrong, **every observation either report made about search behaviour is confounded** — including the tribunal's headline claim that the search fails on a feasible 3-day instance. That instance was feasible *with respect to the wrong numbers*. The two defect classes must be measured on separate tracks or neither can be measured at all.

This has a direct consequence for the sprint: `evaluation/initial_state.md` designates the default `TC-2` / `FM-4` outcome as a known infeasibility to be **preserved** as a regression guard. Both reports independently conclude it is a data-coverage artifact, not infeasibility. Preserving it freezes the defect and makes any "reduce FM-4" metric measure the wrong quantity. The baseline's guard should be re-anchored before sprint metrics are set.

---

## 1. Where the reports agree (treat as settled; no further investigation needed)

Independently reached by both, same mechanism, same direction:

| Finding | Tribunal | OR review | Verified |
|---|---|---|---|
| Unresolved ingredients are silently skipped; most recipes compute to zero nutrition; the resulting FM-4 misnames the cause | A1, F2 | 5.4 | **[verified]** `src/nutrition/calculator.py:166` catches `IngredientNotFoundError` and continues |
| Upper limits are computed in the CLI and discarded; absent from the API; demographic hard-coded `adult_male` | B1 | 3.4 | **[verified]** `src/cli.py:421` builds `resolved_ul`, `src/cli.py:432` calls `plan_meals(...)` without it; `src/api/server.py:1036,1242` likewise |
| Magnesium UL (350 mg) is a supplement-only figure below the profile's 400 mg RDI; same caveat for niacin, folate, vitamin E | B6 | 3.5 | agreed by both |
| HC-1 allergen exclusion is exact normalized-string equality | B2 | 3.1 | agreed by both |
| Sodium (and omega-6) are modelled as floors the scorer rewards reaching | B7 | 4.6 | agreed by both |
| `tags_by_id` is empty, so HC-9 / required tags cannot be exercised end to end | B4, D8 | 3.10, 9 | agreed by both |
| Chronological backtracking thrashes on the horizon micronutrient floor; the 50k cap yields FM-5 with no infeasibility proof | C1, C2 | 5.2 | agreed by both |
| Duplicate LLM recipes; meal identity is by ID, so variety constraints are defeated | D4 | 2.3 | agreed by both |
| Small pools are structurally brittle under simultaneous ±10% macro windows | C3 | 2.1, 5.5, 8 | agreed by both |
| `.cursor/architecture.json`'s "tag filter falls back to full pool" is false | B4, G | 8 | **[verified]** `src/llm/tag_filtering_service.py:26` documents empty-list-on-no-match as intended |

One refinement on the last row: the tribunal frames the empty-pool behaviour as a defect, but the code's own docstring states the empty-list outcome deliberately. It is therefore a **specification decision with a stale doc**, not an implementation bug. The defect is that the resulting failure report names a nutrition cause for a candidate-set cause.

---

## 2. Where the reports conflict, and how each conflict resolves

### 2.1 Are the feasibility bounds conservative? — **tribunal is right, OR review over-generalized**

The OR review states (5.1, §17) that the feasibility bounds "never prune a feasible branch" and lists this among the things that hold up. The tribunal (B5) says FC-4's bound can be too tight when per-day slot counts differ.

**[verified]** `src/planning/phase3_feasibility.py:376` takes `slot_count = len(state.schedule[day_index])` — the *current* day's slot count — and `phase3_feasibility.py:381` tests `deficit > days_left * max_achievable`. If a later day has more slots than the current one, the per-day achievable ceiling is understated for every remaining day and the bound can reject a satisfiable branch.

The OR review's claim is correct for FC-1/FC-2 and incorrect for FC-4. Note the contrast with the structural pre-check, which sums per-day correctly (`phase3_feasibility.py:336`, `for day_index in range(D)`). So this is a localized FC-4 defect, not a pervasive one — which is why one reviewer missed it.

### 2.2 Is a one-day plan the strictest case or the loosest? — **both are half right; the real answer is neither report's**

The OR review (5.6) argues D=1 is the strictest instance: the prorated floor τ×RDI×1 must be met in a single day. The tribunal (B3) argues the opposite: for D=1 the search returns TC-4 before weekly validation, so floors are never checked.

**[verified]** Both mechanisms are present and they apply at different ends of the same run:

- `src/planning/phase7_search.py:629` runs `check_structural_feasibility` with **no gating on D**, so a D=1 instance whose pool cannot reach the floor is rejected up front with FM-4.
- `src/planning/phase7_search.py:980` returns `result_from_success(..., "TC-4", ...)` for `D == 1` **without calling `_weekly_validation`**, so a D=1 instance that *could* have met the floor but didn't is returned as success, unwarned.

The system is therefore **strict at the gate and silent at the exit for the same constraint**. A one-day plan can be refused as structurally impossible, or accepted with hard floors unmet, but it cannot be accepted with a warning. Neither report stated this pairing; it is the sharpest contradiction the reconciliation produced, and it is a specification question, not a bug to patch blindly (§4, Q8).

### 2.3 Which failure code does an empty candidate pool produce? — **not a real conflict**

Tribunal B4 observed FM-4; OR §8 predicted FM-1. Both are correct under different configurations: with micronutrient targets set, the structural pre-check fires first and emits FM-4; with targets removed, the run reaches day 1 slot 0 and emits FM-1 — which the OR review itself notes at 5.4. The shared substance is that neither code names the actual cause.

### 2.4 Determinism — **compatible, tribunal refines**

The OR review lists determinism among the sound elements. The tribunal (F5) narrows this: content-deterministic (sorted-JSON hashes stable across `PYTHONHASHSEED`), not byte-deterministic (micronutrient dicts rebuilt from sets). This is a constraint on the *evaluation harness* (use canonical serialization for snapshots), not a planner defect. No conflict.

### 2.5 Divergent framings of "validated"

The tribunal's D1/D2 treat LLM validation as hollow — most severely, `validate_recipe_draft` demotes unresolvable ingredients to `to taste` and persists the recipe anyway, in direct contradiction of the AGENTS.md rule. The OR review does not cover the LLM pipeline at all. This is a coverage gap, not a disagreement, but it matters for §4 Q2: the two reports use "validated" to mean different things (syntactically resolvable vs. nutritionally plausible), and the codebase uses the weaker one.

---

## 3. The ten most important unresolved questions

Ordered by how much the answer changes the design. Each is genuinely open — findings both reports settled are excluded.

**Q1. How much of the nutrition error comes from each of the four channels: coverage (ingredient absent), resolution (wrong USDA food), mapping (wrong nutrient ID or unit), and units (volume treated as grams)?**
Both reports establish that all four channels are broken. Neither quantifies their relative contribution, so there is no basis for ordering the work. A fix to resolution is worthless if mapping dominates the error, and vice versa.

**Q2. What makes a resolved ingredient acceptable — i.e. what does "USDA-validated" assert, and what gate enforces it?**
Currently it asserts only that the name resolved to some record and that nutrition computation did not raise. `oats` → "Oil, oat" satisfies that. The open question is whether the bar is (a) a plausibility envelope on macros per 100 g, (b) a description-similarity threshold, (c) human adjudication, or (d) restriction to a curated ingredient vocabulary. Each implies a different system.

**Q3. What is the decision variable — an atomic recipe at stored quantity, or a recipe with a portion multiplier; and is stored nutrition per serving or per batch?**
The OR review calls the missing portion variable the single largest formulation choice in the system (2.1), and the per-serving/per-batch ambiguity (2.2) is the same modeling decision seen from the data side. With a portion multiplier most macro windows become trivially satisfiable linear constraints and the subset-sum brittleness largely dissolves; without one, pool arithmetic governs feasibility. Nothing downstream can be settled before this.

**Q4. Is there an objective over complete plans, or is first-feasible the contract?**
The spec states first-feasible (Section 1, item 5); Sections 8 and 11 promise "minimum total deviation from targets". Both cannot be true. The system currently cannot distinguish a plan within 1% of every target from one sitting at every ±10% edge.

**Q5. On correct nutrition data, does the search still fail on feasible instances — and is that a budget problem or a structural one?**
The tribunal brute-forced a feasible 3-day instance the planner missed at 50k attempts. That instance was built from the miscomputed nutrition, so the result does not transfer. The question is whether false-infeasibility survives correct data, and if so whether raising the cap fixes it or the chronological order must change.

**Q6. What is the feasibility frontier — what combination of pool size, horizon, tolerance width, and τ admits plans reliably?**
Both reports assert small pools are brittle; the tribunal's synthetic sweep suggests a threshold somewhere between 60 and 120 recipes. This is the number the product depends on (how many recipes must a user have?) and nobody has it.

**Q7. For each tracked nutrient: is it a floor, a ceiling, a range, or not worth tracking — and is it constrained per day, per horizon, or both?**
Sodium is a floor that should be a ceiling. Omega-6 likewise. Vitamin D is a hard floor the product docs say does not matter. Magnesium's UL contradicts its RDI. Vitamins K, B12, potassium and fibre have null ULs and no daily floor, so a week's supply may come from one day. This is one decision per nutrient, not one global decision.

**Q8. For D=1, should micronutrient floors be enforced, warned about, or ignored?**
Per §2.2 the implementation does two different things at the two ends of the run. Whichever is chosen, the gate and the exit must agree.

**Q9. Can meal prep coexist with the current variety and cooking-time constraints, or must one be re-specified?**
Locking one batch across days fails HC-8 pre-validation; locking a 40-minute recipe into a 5-minute slot fails HC-3 — precisely the slot a prepped meal is for. The OR review calls this the most concrete specification conflict in the system: the feature cannot be used for its purpose. The open question is which constraint yields (per-slot effort vs. total cook time; batch-exempt variety vs. content-level variety).

**Q10. Is HC-1 a safety guarantee or a best-effort preference?**
It is the only constraint with a safety dimension and it is the weakest one. If it is a guarantee, exact-string matching is a blocker and an allergen class table is required. If it is best-effort, that must be stated in the product surface. Two uncoordinated encodings (HC-1 names and `dietary_flags` tags) currently exist and can disagree.

*Just outside the top ten, in order:* whether the 1074-test suite can detect any of these defects at all (tribunal F1 — one test enshrines the silent-skip); whether the LLM feedback loop's writes to `recipes.json` during a plan request are acceptable; whether pins and batches need a date origin (both are currently relative to an undated plan); and whether the per-meal scoring cliff at 10% leaves the nutrition component discriminating at all.

---

## 4. Classification

### 4a. Answerable experimentally (no specification decision needed)

| # | Question | What settles it |
|---|---|---|
| Q1 | Error decomposition | Ground-truth ingredient panel; recompute each channel in isolation (E1) |
| Q5 | False infeasibility | Brute-force oracle vs. planner on known-nutrition pools (E2, E3) |
| Q6 | Feasibility frontier | Parameter sweep over pool size × horizon × tolerance × τ (E2) |
| — | Does "no objective" cost anything? | Regret vs. enumerated optimum on small instances (E5) |
| — | Is the scoring cliff non-discriminating? | Score-distribution and rank-correlation measurement (E6) |
| — | How bad is exact-match allergen recall? | Exclusion panel against the real corpus (E8) |
| — | Is meal prep usable at all? | Enumerate batch-lock configurations, count pre-validation passes (E9) |
| — | Would wiring ULs break the product? | Counterfactual run with `resolved_ul` supplied (E10) |
| — | Can the test suite detect any of this? | Fault injection against the existing suite (E11) |

Q10 has an experimental *input* (recall measurement) but the acceptability decision is specification.

### 4b. Require specification decisions (no experiment can answer them)

- **Q2** — what "validated" asserts. A value judgement about acceptable error, not a measurable.
- **Q3** — the decision variable, and the meaning of one stored recipe. Pure modeling choice.
- **Q4** — objective vs. first-feasible. E5 can tell you the *cost* of having no objective; it cannot decide whether plan quality is a product commitment.
- **Q7** — per-nutrient direction and granularity. Informed by nutrition reference data, decided by product.
- **Q8** — D=1 semantics.
- **Q9** — which of meal prep / variety / cook-time yields.
- **Q10** — whether HC-1 is a guarantee.

Six of the top ten are specification decisions. That is the reconciliation's main scheduling finding: **most of what is wrong with Macrova cannot be fixed by writing code**, and a sprint that opens with implementation will implement the wrong thing.

### 4c. Already adequately addressed by the current implementation

Verified as sound; both reports either affirm these or do not dispute them. No work warranted.

- **Determinism and stable decision order.** Both affirm. The tribunal's byte-stability caveat is a harness requirement (canonical serialization for snapshots), not a planner defect.
- **Hard-constraint predicates** in `phase2_constraints.py` — pure, single-purpose, matching their spec text (OR §17; undisputed).
- **Constraint precedence** lock > pin > required tag > scoring — clearly specified and consistently applied (OR §6, explicitly "no issue"). The only wrinkle is that a "required" tag yields to a lock, which is intentional and needs a doc sentence, not a change.
- **τ centralization** in `micronutrient_policy.py` — acceptance, feasibility, structural pre-check and FC-4 all derive τ from one place, so they cannot drift. **[verified]** all four call sites route through `tau_from_profile`.
- **FC-1 / FC-2 interval bounds** — conservative in the correct direction and cheap. The tribunal's counterexample applies to FC-4 only (§2.1). Looseness is a performance property, not a correctness defect.
- **The structural pre-check's arithmetic** — correct in principle and correctly summed per day **[verified]** `phase3_feasibility.py:336`. Its *report text* is misleading, which is a reporting fix, not a feasibility fix.
- **Structured failure codes with stable `fix_hint`** — the right contract shape. Both reports' complaint is that the text names the wrong cause, which presupposes the mechanism is worth keeping.
- **The tag lifecycle gate** (only `approved` or non-LLM tags may act as hard constraints) — well-defined and correctly gated (OR §9, "no issue"). The tribunal's objection (D8) is that no data flows through it, which is a data gap, not a design gap.
- **Workout-gap / activity-context conversion** — deterministic and correct (OR §12, "no issue").
- **No network during planning** — holds; ingredient resolution completes up front.

---

## 5. Proposed evaluation plan

**Governing principle:** the data track and the search track are confounded in both reports. Separate them by constructing the search experiments so they never touch the ingredient layer — build `PlanningRecipe` objects with known-correct nutrition directly, as the existing planner tests already do. The two tracks then run in parallel and neither blocks the other.

**Harness required (all outside `src/`; this is the only build work the questions justify):**

1. **Ground-truth ingredient panel** — the ~65 distinct ingredient names in the local corpus, each hand-labelled with the intended USDA FDC ID and per-100 g values pulled from the raw record. Data, not code.
2. **Known-nutrition recipe corpus** — synthetic recipes with nutrition vectors supplied directly, parameterized by pool size and macro spread. Bypasses resolution entirely.
3. **Feasibility oracle** — brute-force enumerator over days and day-sequences for D ≤ 3 and pools ≤ 40. The tribunal already built one ad hoc; commit it as a harness so results are reproducible.
4. **Canonical-JSON comparator** — for stable snapshots given §2.4.
5. Existing planner stats (`attempts`, `backtracks`, `day_runtimes`) are sufficient instrumentation; nothing new needed in `src/`.

### Track A — data integrity (answers Q1; informs Q2)

- **E1. Error decomposition.** For each ingredient in the panel, compute four deltas against ground truth: coverage (absent from source), resolution (resolved description is a different food — adjudicated by hand from the panel), mapping (cached value vs. value recomputed from the raw record, per nutrient), and units (recipe recomputed via `NutritionScaler` vs. `NutritionCalculator`). Roll up to per-recipe kcal / protein / per-micronutrient error, attributing each recipe's error to its dominant channel.
  *Primary metric:* share of total absolute kcal and per-micronutrient error attributable to each channel. *Secondary:* count of recipes whose kcal error exceeds 20%, by channel.
  *Decision this drives:* the ordering of any data work, and whether the mapping table alone accounts for the micronutrient failures.
- **E1b. Cache provenance audit.** Partition the on-disk cache by whether each entry is consistent with the current mapping (the tribunal found salmon and egg yolk disagree). *Metric:* fraction of entries attributable to a superseded mapping. *Decision:* whether the cache can be trusted at all or must be rebuilt.
- **E8. Allergen recall.** Exclusion panel (peanuts → peanut butter / peanut oil; shellfish → shrimp / crab / prawn; egg → eggs / egg white; milk → whole milk / skim) run against the real corpus under HC-1.
  *Metric:* recall of exact-match matching per allergen class. *Decision:* whether Q10 can be answered "best-effort, documented" or must be "guarantee, requires taxonomy".

### Track B — search and formulation (answers Q5, Q6; informs Q3, Q4)

- **E2. Frontier sweep.** Known-nutrition pools of {15, 30, 60, 120} recipes × D ∈ {1, 2, 3, 5, 7} × τ ∈ {0.7, 0.8, 1.0} × macro tolerance ∈ {±10%, ±15%, ±20%}, with and without micronutrient targets. Record termination code, attempts, backtracks, wall time. For D ≤ 3 and pools ≤ 40, compare against the oracle.
  *Primary metric:* **false-infeasible rate** — instances the oracle proves feasible that the planner terminates as FM-2/FM-5. *Secondary:* attempts-to-success distribution; the (pool size, horizon) contour where the false-infeasible rate crosses 5%.
  *Exoneration criterion (state this up front):* if the false-infeasible rate is ≈0 at pool ≥ 60 on correct data, then the tribunal's C1/C2 and the OR review's 5.2 are data artifacts and **no search redesign is warranted** — raise the cap and document the pool-size requirement instead.
- **E3. FC-4 soundness (decisive, single instance).** Construct a schedule where day 1 has 2 slots and day 2 has 4, and the only feasible plan uses day 2's extra capacity to meet the horizon floor. Prediction from §2.1: FC-4 prunes at the day-2 boundary and the run returns FM-4 despite an oracle-verified solution.
  *Metric:* binary. This resolves the reports' one direct factual conflict.
- **E4. D=1 asymmetry (decisive, two instances).** (i) A D=1 instance whose floors are achievable but unmet by the first feasible leaf — expect `TC-4` success with floors unmet and no warning. (ii) A D=1 instance that is structurally impossible — expect FM-4. Documents the strict-gate/silent-exit pair for the Q8 decision.
- **E5. Objective regret.** On instances small enough to enumerate all feasible plans, compute total normalized deviation from targets for the planner's returned plan and for the minimum-deviation plan.
  *Metric:* regret distribution (median, p90). *Decision:* if median regret is small, Q4 resolves as "first-feasible is fine, fix the docs"; if large, plan quality needs an objective.
- **E6. Scoring discrimination.** At each decision point, record the distribution of the nutrition sub-score and the fraction of candidates tied at zero; measure rank correlation between composite score and the final plan's deviation; ablate the preferred-tag bonus and the synthesized `high-<nutrient>` tags.
  *Metric:* share of decision points where the nutrition component does not discriminate. *Decision:* whether the ±10% cliff (OR 4.2) and the unbounded bonus (4.4) are actually governing candidate order.
- **E7. Variety under duplicates.** Pool seeded with near-duplicate recipes under distinct IDs; measure distinct *content* meals per plan versus distinct IDs.
  *Metric:* distinct-content-meal count — propose adopting this as the variety metric regardless of what else changes.

### Track C — wiring counterfactuals and evaluation validity

- **E9. Meal-prep usability probe.** Enumerate batch-lock configurations (2–5 servings × placements across days and slots × cook times 10/20/40 min × busyness 1–4) and record how many survive pre-validation.
  *Metric:* pass rate. Prediction: near zero. Confirms Q9 is a specification conflict, not tuning.
- **E10. UL counterfactual.** Call `plan_meals` from the harness with `resolved_ul` supplied (no `src/` change) across the E2 instance set.
  *Metric:* feasibility rate with ULs on vs. off, and per-nutrient binding frequency. *Decision:* whether wiring ULs — which both reports demand — is currently shippable, or whether the magnesium row must be corrected first (it would make the default instance infeasible by construction).
- **E11. Suite sensitivity (fault injection).** Inject each known defect class into a scratch copy and run `python3 scripts/run_pytest.py`: swap the vitamin D IDs back, zero all micronutrients, remove volume conversion, make resolution return an arbitrary record.
  *Metric:* fault detection rate across the 1074 tests. *Decision:* whether the suite can serve as the regression gate for anything above. Note `tests/test_nutrition_calculator.py::test_calculate_recipe_missing_ingredient` currently asserts the silent-skip as correct, so at least one injected fault is expected to pass.
- **E12. Baseline re-anchoring.** Re-record the baseline with the cause separated from the symptom: report ingredient coverage and the count of zero-nutrition recipes *alongside* the termination code, so a future FM-4 can be attributed.
  *Decision:* replaces `initial_state.md`'s "preserve FM-4" guard, which currently protects the defect.

### Sequencing

E1, E1b, E3, E4, E8, E9, E10, E11, E12 are independent of the harness corpus and of each other — all are days of work, several are hours. E2 gates E5, E6 and E7 (all need the known-nutrition corpus and the oracle). Tracks A and B do not gate one another, which is the point of the construction.

**Decision gate:** the six specification questions in §4b should be answered from E1, E2, E5, E8, E9 and E10 in hand, and before any implementation. The plan deliberately contains no remediation work; the only construction it calls for is the five harness items, each of which exists solely to answer a listed question.
