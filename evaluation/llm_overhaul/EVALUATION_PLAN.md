# EVALUATION_PLAN.md — Test families that can separate architectural hypotheses

**Phase:** 3. No code changed. Harness lives in `evaluation/llm_overhaul/harness/`; results in `evaluation/llm_overhaul/results/`. Nothing here imports the LLM except where marked **live**; everything else is offline, deterministic, and uses temporary paths so repository data is never mutated.

## 0. Hypotheses the suite must be able to tell apart

| | Hypothesis | If true, we expect |
|---|---|---|
| H1 | "The LLM layer is sound; failures are data-quality noise." | Recovery cases succeed whenever a fitting recipe exists; contamination cases never write bad state; NL benchmark loses only unrepresentable fields. |
| H2 | "The layer is structurally sound but validation is too weak (targeted fixes suffice)." | Recovery mechanism reaches success on help-able cases, but accepts unsafe/implausible drafts; fixing validators would close the S0/S1 rows without touching the loop. |
| H3 | "The recovery loop itself is mis-specified (needs a diagnosis step and typed termination)." | Loop runs on cases where no recipe can help, cannot say why it stopped, and its 'progress' rule does not track feasibility; validator fixes alone leave FL-* rows open. |
| H4 | "Persistence/provenance is the root problem." | Every accepted draft contaminates permanently; the same failures recur across requests; nothing can be audited or rolled back. |

The families below are designed so that each hypothesis predicts a different pattern of pass/fail. Section 14 maps families to hypotheses.

## 1. Metrics that are machine-checkable

Every case declares an `expected` block and a scorer computes booleans; no case is scored by a subjective quality judgement. Where the current schema *cannot* represent a constraint, the case still declares the ground truth so that the omission is counted against the architecture, not hidden.

| Metric | Definition |
|---|---|
| field accuracy | output field equals expected (numeric within 2 %, sets case-insensitive) |
| omission rate | stated constraints absent from the structured output; split into *structural* (schema has no field) and *model* (field exists, value missing) |
| invented-constraint rate | output fields with values the user never stated; split into *documented default* and *non-default invented* |
| hard/soft misclassification | a soft preference that the downstream path treats as a hard constraint, or vice versa |
| invalid-configuration rate | schema rejection or mapping rejection; split into *expected* (input is invalid) and *unexpected* |
| determinism | identical structured output across two runs of the same prompt |
| recovery outcome | terminal state of the loop (7-state model, §12) vs the expected terminal state |
| intent-violation flags | plan contains an excluded ingredient; plan bypasses a user filter; success relies on fabricated cook time; retry pool ≠ requested pool |
| contamination count | recipes persisted, cache files written, tag entries replaced, per case |
| resolution correctness | adjudicated label per cache entry: correct / wrong food / wrong form / branded-substitute |
| tag correctness | prep bucket equals the deterministic bucket of `cooking_time_minutes`; dietary flags consistent with an ingredient keyword list; cuisine ∈ a closed vocabulary |

## 2. Family A — Natural-language interpretation (live)

Harness: `harness/run_nl_benchmark.py`, cases `harness/nl_cases.json` (NL-01 … NL-42). Each case is run through `parse_nl_config` and `user_profile_from_planner_config`, twice.

| Scenario | Initial state | Expected behaviour | Invariant | Observable | Failure interpretation |
|---|---|---|---|---|---|
| NL-01 fully specified request | none | all six representable fields exact | user-stated values survive unchanged | config JSON | field miss = model error |
| NL-02 "make me a meal plan" | none | every field defaulted | defaults must be marked as defaults | which fields carry non-null values | any value ≠ documented default = invented |
| NL-30 prompt injection | none | schema-valid output ignoring the injected key | LLM cannot alter the contract | parse success | failure = client/schema weakness |
| NL-39 typos | none | fields extracted | robustness | field accuracy | — |
| determinism (all) | none | run 1 == run 2 | temperature 0 is not a guarantee | agreement rate | <100 % ⇒ `assisted_cached` replay is unsound |

## 3. Family B — Constraint extraction (live)

| Scenario | Initial state | Expected | Invariant | Observable | Interpretation |
|---|---|---|---|---|---|
| NL-03/04/38 allergy and dislikes | none | ground truth lists declared; schema has no field | a stated allergy must never be silently dropped | structural omission count; misplacement (allergy text in `cuisine`) | any omission is **S0** and architectural |
| NL-13 calorie ceiling | none | ceiling declared | ceilings are hard | where the number lands (`calories`?) | landing in `targets.calories` converts a ceiling into a centre target |
| NL-14 micronutrients | none | targets declared | — | omission | structural |
| NL-15 fat range | none | range declared | fat must not be derived from budget when stated | `daily_fat_g` from mapping | mismatch = IN-7 |
| NL-24 liked foods | none | — | likes are soft | landing | in `cuisine` ⇒ becomes hard filter (IN-3) |
| NL-40 stress prompt with 9 constraints | none | each classified | — | per-constraint outcome | — |

## 4. Family C — Constraint classification (live + offline)

| Scenario | Expected | Invariant | Observable | Interpretation |
|---|---|---|---|---|
| NL-05 "prefer Mexican if possible" | soft | soft never becomes a hard pool filter | `cuisine` non-empty ⇒ in assisted plan-from-text it is a hard filter | misclassification at the *system* level even if the model is right |
| NL-06 "only Italian" | hard | hard filter is legitimate | same field | correct only by accident of B3 |
| NL-07/08 budget | budget is an economic preference | must not set macro bounds | `daily_fat_g` derived from budget | every budget case is a misclassification (IN-3) |
| NL-16 keto | low-carb is hard | — | mapped carbs | positive derived carbs = silent constraint loss |

## 5. Family D — Planner failure diagnosis (offline)

Harness: `harness/run_recovery.py` cases R-05, R-07, R-10, R-11 plus benchmark cross-reference (probe P10).

| Scenario | Initial state | Expected | Invariant | Observable | Interpretation |
|---|---|---|---|---|---|
| R-05 negative carbs | 2-slot day, fitting pool | classified unrecoverable before any LLM call | recovery only when recipes can help | `llm_calls == 0` | `>0` ⇒ H3 |
| R-07 required tag on slot 1 unsatisfiable | pool without the tag | classified "tag gap" not "recipe gap" | code names the cause | initial `failure_mode`, `llm_calls` | FM-1 + calls ⇒ C2b + H3 |
| R-10 batch lock exceeds slot cook time | one batch lock | FM-3, no loop | pins/locks excluded | `llm_calls == 0` | — |
| R-11 feasible instance under attempt cap | fitting pool, `attempt_limit=1` | search defect flagged, no generation | FM-5 ≠ inventory gap | `llm_calls` | `>0` ⇒ H3 |
| P10 benchmark cross-reference | results.json | 0 oracle-pin/tag/feasible cases eligible | — | count | 7 today |

## 6. Family E — Recipe discovery (offline scripted LLM; live sub-experiment)

| Scenario | Initial state | Expected | Invariant | Observable | Interpretation |
|---|---|---|---|---|---|
| R-01 fitting pool | 3 fitting recipes | success, no LLM | LLM never called on success | `llm_calls == 0` | — |
| R-02 one recipe missing, LLM supplies it (resolvable names) | 2 fitting + distractors | SUCCESS in 1 attempt | recovery works when it should | terminal state, attempts | failure ⇒ mechanism broken (against H1/H2) |
| R-03 same but LLM names unresolvable ingredients | same | INVALID_RECOVERY_OUTPUT or explicit rejection | never persist a demoted recipe | persisted count, demotion count | persisted>0 ⇒ RG-2 |
| R-04 one recipe, three slots (HC-2) | 1 fitting | SUCCESS after 2 recipes | — | attempts | — |
| R-14 LLM repeats itself | distractor draft twice | NO_USEFUL_RECOVERY after 2 | dedupe works | history statuses | — |
| L-01…L-04 **live**: real drafts for the R-02/R-05/R-07/R-08 contexts | real feedback context | drafts avoid excluded ingredients, resolve in cache, differ across attempts | — | offline resolvability rate, excluded-ingredient hits, name overlap | shows what the impoverished context (B6) actually produces |

## 7. Family F — FoodData Central resolution (offline)

Harness: `harness/fdc_audit.py` over the 83 cached entries; adjudication table in `EVALUATION_RESULTS.md`.

| Scenario | Expected | Invariant | Observable | Interpretation |
|---|---|---|---|---|
| F-01 adjudicate every cache entry | ≥95 % correct food | resolver is trustworthy enough to be an authority | correct / wrong-food / wrong-form / branded | <95 % ⇒ resolution needs a gate (Q2) |
| F-02 zero-kcal with non-zero macros | 0 entries | mapper complete | count | >0 ⇒ FDC-4 |
| F-03 vitamin D outliers (>500 IU/100 g) | 0 | mapper units correct | count | FDC-4 |
| F-04 duplicate keys (`banana`/`bananas`) | 0 | one identity per food | count | FDC-6 |
| F-05 provenance: recipe → ingredient → fdc_id | traceable | every persisted number is explainable | keys available at provider boundary | not traceable ⇒ FDC-8 |
| F-06 volume units in persisted recipes | 0 treated as grams | derived data honest | count of ml/cup/tbsp lines | FDC-3 |

## 8. Family G — Ingredient normalization (offline)

| Scenario | Expected | Invariant | Observable | Interpretation |
|---|---|---|---|---|
| G-01 descriptor stripping idempotent and does not create collisions | "large eggs"→"eggs", "raw spinach"→"spinach" | canonical name is stable | `IngredientNormalizer` outputs | — |
| G-02 matcher canonical name equals USDA description | description surfaced | caller can verify identity | `canonical_name` vs cache description | equal to query ⇒ echo (B-matching) |
| G-03 "to taste" units from LLM preserved, not used to hide main ingredients | quantity 0 only for seasonings | — | non-seasoning to-taste count in persisted recipes | 2 today |

## 9. Family H — Recipe validation (offline)

| Scenario | Expected | Invariant | Observable | Interpretation |
|---|---|---|---|---|
| R-13 draft contains `peanut butter`, profile excludes `peanuts` | rejected, or never planned | S0 | plan contents | planned ⇒ RG-6/FL-8 |
| R-09 draft with 1 instruction for a 20-minute dish | no cook-time claim, or claim marked unverified | fabricated facts must not drive HC-3 | success via 5-minute time | success ⇒ RG-7 |
| P5 implausible macro recipe (oat oil) | rejected | plausibility gate | accepted | RG-1/RG-4 |
| R-03 demotion | rejected | AGENTS.md rule | persisted | RG-2 |

## 10. Family I — Tagging (offline + live)

Harness: `harness/tag_eval.py`.

| Scenario | Expected | Invariant | Observable | Interpretation |
|---|---|---|---|---|
| T-01 unknown slug in `required_tag_slugs` | 422 | canonical taxonomy | validation error | — |
| T-02 proposed LLM tag in benchmark fixture | not hard-eligible | lifecycle gate | `load_hard_eligible_recipe_tag_slugs` | — |
| T-03 alias `batch-cook` | resolves to `meal-prep` | — | resolve | — |
| T-04 LLM tagging preserves existing `tags_by_id` | preserved | writes are non-destructive | keys before/after | lost ⇒ TG-8 |
| T-05 **live**: prep bucket vs deterministic bucket | equal | derivable facts are derived, not guessed | agreement rate | <100 % ⇒ TG-2 |
| T-06 **live**: dietary flags vs ingredient keywords | no contradictions | — | contradiction count | TG-4 |
| T-07 **live**: cuisine ∈ closed vocabulary | yes | — | distinct strings | free strings ⇒ TG-1 |
| T-08 **live**: determinism | run 1 == run 2 | — | agreement | — |

## 11. Family J — Pool mutation (offline)

| Scenario | Expected | Invariant | Observable | Interpretation |
|---|---|---|---|---|
| R-06 filter-emptied pool, drafts fit | must not bypass the user's filter | retry pool ⊆ requested pool semantics | success flag, pool provenance | success ⇒ FL-8/FL-2 |
| R-15 forced fallback rebuild | retry pool == requested subset with tags | — | pool size and tag attributes after rebuild | grows or loses tags ⇒ FL-2 |
| all R-cases: cache writes | 0 for rejected drafts | validation is read-only | files in temp cache dir | >0 ⇒ FDC-9 |
| all R-cases: recipes persisted on failed request | 0 | no residue from failed requests | temp recipes.json | >0 ⇒ ST-2/ST-3 |

## 12. Family K/L — Retry behaviour and termination (offline)

Seven-state terminal model applied to every R-case by a classifier over observables:

| Terminal state | Observable definition used by the harness |
|---|---|
| SUCCESS | final `success == True` |
| UNRECOVERABLE_INFEASIBILITY | loop refused before any LLM call because no recipe could help |
| NO_USEFUL_RECOVERY_FOUND | loop ran, accepted ≥1 recipe, stopped by the no-progress rule |
| RECOVERY_LIMIT_REACHED | loop ran, exhausted attempts, still failing |
| INVALID_RECOVERY_OUTPUT | loop ran, no attempt accepted any draft |
| DATA_SOURCE_FAILURE | LLM/USDA error surfaced as an exception |
| SYSTEM_ERROR | any other exception |

| Scenario | Expected terminal | Invariant | Observable |
|---|---|---|---|
| R-05 | UNRECOVERABLE | no LLM call | classifier |
| R-07 | UNRECOVERABLE (tag) | — | classifier; today: LIMIT or NO_USEFUL |
| R-12 LLM garbage | DATA_SOURCE_FAILURE **with the planner result preserved** | deterministic result never lost | exception vs result |
| R-14 | NO_USEFUL_RECOVERY | bounded | attempts == 2 |
| all | attempts ≤ 3, planner runs ≤ 4, LLM calls ≤ 3 | bounded | counters |

## 13. Family M — End-to-end recovery (offline scripted)

R-02, R-04, R-08 (nutrition gap), R-09 (schedule gap) are the positive end-to-end cases; R-05, R-06, R-07, R-13 are the negative ones. A design passes Family M when every positive case ends SUCCESS with zero intent-violation flags and every negative case ends in the declared non-success state with zero contamination.

## 14. Which family discriminates which hypothesis

| Family | H1 predicts | H2 predicts | H3 predicts | H4 predicts |
|---|---|---|---|---|
| A/B/C (NL) | only structural omissions | same | same | same |
| D (diagnosis) | pass | pass | **fail** | pass |
| E positive | pass | pass | pass | pass |
| H (validation) | pass | **fail** | fail | fail |
| I (tagging) | pass | fail | fail | **fail (T-04)** |
| J (mutation) | pass | pass | fail (R-06/R-15) | **fail** |
| K/L (termination) | pass | pass | **fail** | pass |

If D, H, J, and K/L all fail while E-positive passes, the evidence supports H2+H3+H4 jointly: the mechanism can recover when it should, but it cannot tell when it should, cannot validate what it accepts, and cannot contain what it writes. That combination is what Phase 9 must decide on.
