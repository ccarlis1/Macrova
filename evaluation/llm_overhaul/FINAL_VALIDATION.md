# FINAL_VALIDATION.md — Baseline vs overhauled LLM layer

**Baseline:** branch `llm-overhaul` at `779af36` (measurements in `EVALUATION_RESULTS.md`, result files without suffix).
**Overhauled:** same branch, working tree after Stages 0–9 (`IMPLEMENTATION_LOG.md`; result files with `_after` suffix).
**Model for live runs:** `gpt-4o-mini`, temperature 0, through the repo's `LLMClient`. Live calls after: 84 (NL) + 12 (tagging) + 9 (recovery probes).
**Test suite:** 1074 → 1119 passed (45 added, 0 removed; 9 assertions changed because they encoded behaviour the evaluation showed to be defective, each listed in the log). OpenAPI snapshot unchanged. No `src/planning/phase*` file was touched: the deterministic planner is byte-identical.

---

## 1. Recovery loop (15 scripted cases, real planner, real validator, cache-only USDA provider)

| Case | Situation | Before → terminal | After → terminal | LLM calls before/after | Residue before/after | Intent violations before/after |
|---|---|---|---|---|---|---|
| R-01 | fitting pool | SUCCESS | NOT_ATTEMPTED (success, loop idle) | 0/0 | 0/0 | 0/0 |
| R-02 | one recipe missing, resolvable draft | SUCCESS | SUCCESS | 1/1 | 1/1 (with provenance) | 1 (tags lost) / 0 |
| R-03 | unresolvable ingredient names | NO_USEFUL (demoted recipe persisted) | INVALID_RECOVERY_OUTPUT (`INGREDIENT_UNRESOLVED` ×3) | 1/3 | **1/0** | 3/0 |
| R-04 | one recipe, three slots | SUCCESS | SUCCESS | 1/1 | 2/2 | 1/0 |
| R-05 | negative carbs | NO_USEFUL after generating | **UNRECOVERABLE (IMPOSSIBLE_TARGETS)** | **1/0** | **1/0** | 2/0 |
| R-06 | pool emptied by filter | SUCCESS by bypassing the filter | **UNRECOVERABLE (EMPTY_POOL)** | **1/0** | 3/0 | **1/0** |
| R-07 | required tag unheld | RECOVERY_LIMIT after 3 generations | **UNRECOVERABLE (REQUIRED_TAG_UNHELD)** | **3/0** | **3/0** | 2/0 |
| R-08 | iron structural gap | SUCCESS | SUCCESS | 1/1 | 1/1 | 1/0 |
| R-09 | 5-minute slot | SUCCESS on fabricated cook time | SUCCESS on author-claimed 3 min (provenance `llm_claimed`) | 1/1 | 1/1 | **1/0** |
| R-10 | batch lock conflict | UNRECOVERABLE | UNRECOVERABLE | 0/0 | 0/0 | 0/0 |
| R-11 | feasible instance at attempt cap | NO_USEFUL after generating | **UNRECOVERABLE (SEARCH_BUDGET)** | **1/0** | **1/0** | 2/0 |
| R-12 | LLM garbage | **exception; planner result lost** | DATA_SOURCE_FAILURE with planner result preserved | 1/1 | 0/0 | 1/0 |
| R-13 | peanuts excluded, peanut-butter draft | **SUCCESS with allergen in plan** | INVALID_RECOVERY_OUTPUT (`EXCLUDED_INGREDIENT` ×3) | 1/3 | 1/0 | **2/0** |
| R-14 | same non-fitting draft repeated | NO_USEFUL | RECOVERY_LIMIT_REACHED (no residue) | 1/3 | **1/0** | 2/0 |
| R-15 | pool update fails | SUCCESS after silent rebuild, pool 6 → 64, tags dropped | SYSTEM_ERROR (`pool_update_failed`), pool unchanged | 1/1 | 1/0 | **2/0** |

Aggregates:

| Metric | Before | After |
|---|---|---|
| Positive cases recovered (R-02, R-04, R-08, R-09) | 4/4 | 4/4 |
| Unrecoverable cases that called the LLM (R-05, 06, 07, 10, 11) | 4/5 | **0/5** |
| Cases with intent-violation flags | 12/15 | **0/15** |
| Recipes persisted by requests that ended in failure | 7 | **0** |
| Terminal states distinguishable by the caller | 2 (success / not) | 7, typed, with reason and per-attempt rejections |
| Retry pool with lost tag attributes | 11/15 | 0/15 |
| Planner re-run when nothing was accepted | yes | no |

Cross-request replay (baseline: R-13 received R-02's cached drafts) is gone by construction: the cache key now contains the `GapSpec`, which includes the exclusions.

### Live probes (real model, real contexts)

| Context | Before (empty context) | After (GapSpec) |
|---|---|---|
| R-02 macro gap | Quinoa Salad / Grilled Chicken / Oatmeal (the same three dishes for every failure) | Avocado Chickpea Salad / Quinoa and Black Bean Bowl / Spinach and Feta Omelette; 11 of 13 ingredient names from the offered vocabulary resolve offline |
| R-08 iron gap | targeted, but 5/11 names resolvable | 1 draft accepted at the envelope level (2 rejected per draft), 4/6 names resolvable |
| R-13 peanuts excluded | not told; no peanut by luck | told; 0 excluded hits; 10/11 resolvable |
| R-05, R-07, R-11 | drafts generated | no call made |

---

## 2. Natural-language interpretation (42 prompts, 2 runs each)

| Metric | Before | After |
|---|---|---|
| Numeric fields (days, meals, calories, protein) | 36/37, 35/35, 34/35, 34/34 | 36/36, 34/34, 34/34, 33/33 |
| Constraints the schema can carry | 6 field classes | 15 field classes |
| Stated allergies reaching `UserProfile.allergies` | **0/3** | **3/3** (NL-03 peanuts, NL-04 shellfish, NL-40 tree nuts) |
| Dislikes reaching the profile | 0/2 | 2/2 |
| Calorie ceiling → `max_daily_calories` | never | 1/1 (NL-13: 1500) |
| Stated fat range honoured | replaced by budget | 1/1 (NL-15: 50–70 g) |
| Micronutrient goals | dropped | 1/1 (NL-14) |
| Diet restrictions | placed in `cuisine` (became a hard filter on a taxonomy with no such cuisine) | 2/2 in `dietary_flags` (canonical tag filter) |
| τ | dropped | 1/1 |
| Structural omissions | 15 constraints in 11 prompts | **0** (13 would still be dropped under the old schema) |
| Invented schedule kept as a hard cook-time cap | 14 prompts | **0** (1 emitted, dropped by mapping because `stated_fields` did not list it) |
| Hard/soft misclassifications at the system level | 7 | **0** |
| `stated_fields` reported by the model | n/a | 36/37 prompts; precision 0.96, recall 0.92 |
| Invalid inputs rejected | 3/4 (NL-28 "0 days" silently clamped to 1) | **4/4** (NL-28 now rejected by schema) |
| Unit handling | kJ not converted (NL-33 → 8400) | NL-33 correct (2007 kcal) |
| Keto (NL-16) | accepted, planned at 240 g carbs | rejected: `NEGATIVE_CARBS_DERIVED` (75 % fat + 150 g protein exceeds 2000 kcal) — a correct refusal |
| Determinism | 38/42 | 37/42 (differences: `stated_fields` list in 2, `schedule_days` in 2, `constraints` in 1) |
| Regression | — | NL-23 "breakfast must be meal-prep friendly": before, the model emitted `required_tag_slugs=["meal-prep"]` in `schedule_days`; after, with the instruction to emit `schedule_days` only when the schedule is described, it omitted it (0/1). |

---

## 3. Tagging (6 recipes × 2 live runs + offline gates)

| Metric | Before | After |
|---|---|---|
| Valid `RecipeTagsJson` objects from the model | **0/6, 0/6** | **6/6, 6/6** |
| Effect of a tagging run on curated `tags_by_id` (64 entries) | **erased (64 → 0)** | preserved (merge; 64 → 64 + tagged) |
| `prep_time_bucket` equals the deterministic bucket of `cooking_time_minutes` | not measurable | 6/6 (derived) |
| Cuisine strings | free text | 4 distinct, all in the closed vocabulary (`american`, `greek`, `mexican`, `unknown`) |
| Dietary-flag contradictions vs ingredient keywords | not measurable | 0 |
| Proposed registry slugs quarantined (`llm`/`proposed`, not hard-eligible) | no producer existed | 100 % (e.g. `dinner`, `snack`, `high-protein` proposed; `time-*` derived and hard-eligible) |
| Determinism | not measurable | 6/6 |
| Unknown slug in a slot, proposed-tag hard eligibility, alias resolution | pass | pass |

---

## 4. FoodData Central pipeline

| Metric | Before | After |
|---|---|---|
| Provenance visible past the provider | `['name', 'per_100g']` | `+ provenance {fdc_id, description, data_type, method, rank_confidence, margin, mapper_version, resolved_at}`; legacy entries labelled `legacy_cache` |
| Matcher `canonical_name` | echo of the query | resolved USDA description |
| Persisted recipe → USDA record traceable | no | yes (`provenance.resolved_fdc_ids`) |
| Identity gate on the 83 cached resolutions | none | rejects `oats`→oat oil, `eggs`→egg bread, `bell pepper`→nachos, `milk 1%`→cottage cheese; 0 false positives; misses the 5 same-head-word form errors |
| Plausibility gate | none | oil-based and >2500 kcal single recipes rejected |
| Cache writes triggered by rejected LLM drafts | yes (any resolvable name) | unchanged (see Unresolved) |
| Mapper defects (vitamin D units, Foundation energy) | present | present, now attributable via `MAPPER_VERSION` (out of scope, see Unresolved) |

---

## 5. Verdict by category

### PROVEN IMPROVEMENTS (measured, offline and reproducible unless marked live)
1. The loop refuses to call the LLM for the five kinds of failure recipes cannot fix, with a typed reason (R-05/06/07/10/11: 4 LLM calls → 0).
2. Failed requests leave no residue (7 recipes → 0); successes persist only what the plan used, with provenance.
3. Excluded ingredients cannot be planned through generated recipes (R-13), and the exclusion match is class-aware (peanuts → peanut butter).
4. Unresolvable ingredients reject the draft instead of silently removing them (R-03, P5).
5. Cook time is an author claim with provenance, checked against the slot cap, never a fabricated 5×steps value when a cap applies (R-09).
6. LLM and USDA errors are contained; the deterministic result survives (R-12).
7. The request's pool is never rebuilt from disk (R-15: 6 → 64 no longer happens).
8. Every exit reports one of seven typed states with per-attempt rejection codes, and it reaches API and CLI JSON.
9. Stated allergies, dislikes, ceilings, fat ranges, micronutrient goals, diet flags and τ reach the planner (0 → 15 constraint classes; 0/3 → 3/3 allergies, live).
10. NL cuisine and budget are soft; invented schedules are dropped; invalid inputs are rejected rather than clamped (live).
11. LLM tagging produces valid, deterministic, vocabulary-bound, quarantined proposals and never erases curated tags (0/6 → 6/6, live; 64 → 0 → 64 preserved).
12. Provenance travels from the USDA cache to persisted recipes; the matcher returns the real USDA description.

### UNRESOLVED PROBLEMS (measured, not fixed here)
1. Resolution identity: 5 of the 9 wrong-food cache resolutions share the head word with the query (cherries/cherry tomatoes, banana powder, deli roll, flour tortillas, acai drink) and pass the identity gate. A curated identity panel or a form-aware ranker is needed (Q2 in the reconciliation).
2. Mapper values: vitamin D IU/µg swap and Foundation energy IDs remain (outside this mission's scope); `MAPPER_VERSION` now makes a correction attributable but the 83 legacy cache entries carry `mapper_version=None`.
3. Validation still writes USDA cache entries for names in rejected drafts (FDC-9); the provider has no dry-run mode.
4. Planner failure attribution (C2a/C2b) is unchanged; the diagnosis step works around it by inspecting pool and profile directly, but the planner's own `failure_mode` for macro-infeasible days is still `FM-1`.
5. NL-23 regression: slot-level required tags expressed in prose are no longer emitted after the "only when described" instruction.
6. Live determinism is 37/42; `assisted_cached` replay remains a convenience, not a correctness guarantee.
7. Frontend: `report.llm_recovery` and `warnings.nl_interpretation` are not rendered by the Flutter client (DTOs accept extra keys; no UI change made).

### KNOWN LIMITATIONS (by design)
1. Diagnosis is conservative: `REQUIRED_TAG_UNHELD` refuses recovery even though a curator could approve a proposed tag later; recipes generated in-loop carry only derived `time-*` tags.
2. `NO_USEFUL_RECOVERY_FOUND` is decided by a cheap heuristic signal (candidate counts, reachable nutrient totals, per-meal calorie band), not by search; it can stop one attempt early on a macro gap.
3. The fitness band for macro gaps (0.4×–1.8× per-meal calories) and the plausibility ceiling (2500 kcal, 85 % fat) are fixed constants.
4. Generated recipes are single-serving; `default_servings` is 1.
5. `DeterministicCacheMissError` still raises in `assisted_cached` mode (explicit caller contract preserved).

### UNTESTED ASSUMPTIONS
1. That the identity gate's 0 false positives on the 83 cached entries generalize to the names the live model produces (11/13, 4/6 and 10/11 resolvable offline in the probes; resolution correctness of those names was not adjudicated).
2. That the per-meal calorie band and nutrient minimums are the right fitness criteria for multi-day horizons; all scripted cases are one-day.
3. That `stated_fields` precision (0.96) holds on prompts outside this 42-case benchmark.
4. That merging tags by default has no caller that relied on replacement (none found in `src/` or `tests/`).
5. Live USDA resolution (network) of LLM-authored names was not exercised; every after-run used the cache-only provider.

---

## 6. The defensible answer

**What the LLM layer is responsible for:** interpreting natural language into a typed `PlannerConfigJson` that carries every constraint class the planner has and says what the user stated; proposing recipe drafts and tag proposals only in response to a deterministic `GapSpec`; and tie-breaking among deterministic candidates when asked. It is not responsible for deciding feasibility, deciding whether recovery should run, validating itself, writing to any store, or supplying facts (nutrition, cook time, tags) without provenance.

**How it interacts with the planner and data systems:** through three deterministic gates that it cannot bypass — diagnosis before it is called, semantic validation of what it returns, and persist-only-on-success with provenance afterwards — and through a typed outcome that tells the caller which of seven things happened.

**Evidence:** the 15-case recovery suite (0 intent violations, 0 residue, 0 LLM calls on unrecoverable cases, 4/4 positive recoveries), the 42-prompt live NL benchmark (0 structural omissions, 3/3 allergies reaching the planner, 0 hard/soft inversions), the live tagging run (6/6 valid, curated tags preserved), the provenance and identity-gate measurements on the real cache, and a test suite that grew from 1074 to 1119 with the deterministic planner untouched.
