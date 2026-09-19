# LLM_OVERHAUL_PLAN.md — Decision (Phase 9) and staged implementation plan (Phase 10)

Inputs: `CURRENT_ARCHITECTURE.md`, `FAILURE_TAXONOMY.md`, `LLM_LAYER_DIAGNOSTIC.md`, `EVALUATION_PLAN.md`, `EVALUATION_RESULTS.md`.

---

## Part 1 — Decision

### Options considered

| Option | What it means here | Evidence for | Evidence against |
|---|---|---|---|
| A. Preserve with targeted fixes | keep `plan_with_llm_feedback` as is; patch validator, tagger write, exception handling | E-positive cases recover (R-02/04/08); client, schemas, repository, tag registry gate are sound | D, J, K/L failures are in the loop's *shape*: no diagnosis, no fitness, persist-before-retry, no typed exit. Patches cannot add a missing step |
| B. Refactor substantially | rewrite orchestrator, validator, tagger, NL schema together | would address everything | violates rule 15 (preserve working behaviour) for parts that work: planner untouched anyway; client/schemas/repository/tag registry pass their families |
| **C. Partially replace** | replace the recovery *control loop* (diagnose → gap spec → generate → semantic validate → candidate pool → retry → typed outcome → persist-on-success with provenance); keep client, schema layer, repository, tag registry, planner, and API surface; extend rather than replace the NL schema; fix the two destructive write paths | matches the three root causes exactly; every replaced piece has a failing family; every kept piece has a passing family | more stages than A |
| D. Redesign around a new recovery architecture | new service boundary (e.g. agent with tools) | none in evidence | reintroduces the untested surface; nothing in the results says the *architecture* (LLM outside the planner, validation in between) is wrong — the *implementation* of that architecture is |

**Decision: C.** The intended architecture (deterministic planner as authority, LLM as untrusted assistant outside it) is right and already the shape of the code. What is missing is the middle: a deterministic diagnosis that decides whether the LLM should be asked at all and what for, a semantic gate on what comes back, a candidate pool that is not the persistent store, and a typed result that survives serialization. Those are additions and replacements of specific functions, not a new system.

### What the LLM layer is responsible for (the answer this mission must defend)

1. **Interpretation** of natural language into a typed `IntentSpec` that can carry every constraint class the planner understands, marks what the user stated versus what was defaulted, and never becomes a hard constraint without a deterministic mapping rule that says so.
2. **Proposal** of recipe drafts and tag proposals in response to a deterministic `GapSpec`, never in response to a bare failure code.
3. **Tie-breaking** among deterministic candidates (USDA disambiguation, alias suggestions) when the deterministic ranker reports low confidence — and only from the candidate set it is given.

It is **not** responsible for: deciding whether a plan is feasible; deciding whether recovery should run; validating its own output; writing to any store; assigning tags that act as hard constraints; supplying nutrition, cook times or serving sizes as facts.

### Per-change justification

| # | Problem (taxonomy) | Evidence | Root cause | Design | Alternatives | Why preferred | Migration | Tests | Risks |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Loop runs when no recipe can help; no gap spec (RG-9/10, FL-7) | R-05/06/07/11; P1/P2/P10 | recovery keyed on a code that names the last search event | deterministic `diagnose()` producing `GapSpec` or `Unrecoverable(reason)`; LLM called only with a `GapSpec` | fix planner codes first (C2a) | codes fixing is planner work outside scope; diagnosis works from pool+profile regardless of code | additive module | D family | diagnosis may be conservative (declare unrecoverable when a recipe could help) — measured by E-positive |
| 2 | Typed termination absent; exceptions destroy the planner result (FL-9/10, B13) | R-12, P4; stats dropped | loop returns bare `MealPlanResult`; exceptions uncaught | `RecoveryOutcome` (7 states) in `report["llm_recovery"]`; boundary catches LLM/data errors | log-only | a caller must be able to act on the state | additive report key | K/L | none |
| 3 | Validation is syntactic (RG-1/2/6/7, FL-8) | R-03/09/13, P5 | demotion, no exclusion check, fabricated cook time, no identity check | reject unresolvable; exclusion match by token (class-aware); identity gate on resolved description; LLM-claimed cook time with provenance and slot-cap check; fitness vs `GapSpec`; near-duplicate check | keep demotion, warn | AGENTS.md rule; S0 | tests asserting demotion change | H | identity gate false positives (measured 0 on correct entries with head-noun rule) |
| 4 | Persist-before-retry, no provenance, fallback rebuild (ST-1..7, FL-2/4) | 7 residue recipes; R-15 6→64 | writes as side effects | candidate pool in memory; persist only recipes used by a successful plan, with `provenance`; incremental update failure ⇒ `DATA_SOURCE_FAILURE`, never rebuild | keep persist-first with cleanup | cleanup is another mutation | additive recipe fields | J | recipes that helped but weren't used are not kept (acceptable) |
| 5 | Tagging write is destructive; tagger produces 0 valid outputs (TG-8, TG-1/2/7) | T-04; 0/6 | `upsert` replaces; prompt lacks schema and vocabulary | merge semantics; prompt embeds schema + registry slugs; deterministic time bucket; per-recipe `source`/`eligibility`; slugs restricted to registry, `proposed` | remove LLM tagging | hybrid decision in Results §7 | none | I | model still may fail schema; then nothing is written (safe) |
| 6 | NL schema drops safety constraints; defaults invisible; budget→fat; soft→hard (IN-1/2/3/7) | 15 dropped, 14 invented | schema shape and mapping rules | add optional `constraints` block and `stated_fields`; map allergies/dislikes/ceiling/fat/micros/diet; fat from budget only when unstated and flagged; drop unstated `schedule_days`; cuisine never a hard filter from NL | new schema | additive fields keep `extra="forbid"` safe | prompt+schema | A/B/C | model may not fill `stated_fields` reliably — measured |
| 7 | Provenance absent past the provider (FDC-8/9, ST-7) | audit | dict shape | `ResolutionRecord` on cache entries and provider dict; `fdc_id` on validated ingredients | none | Results §6 | additive | F | none |
| 8 | Feedback cache contaminated by tests; cross-request replay (ST-2, RG-8) | 6 fixtures; R-13 replay | tests don't redirect; key lacks intent | conftest redirects; key includes `GapSpec` (which includes exclusions) | delete cache | cache is useful for `assisted_cached` | purge fixtures | J | none |

Out of scope (recorded, not done): planner failure-code attribution (C2a/C2b), search-order defect (C4), batch status rule (C1), calorie ceiling in `PlanRequest` (§4.1), nutrient-mapper value corrections (A3) beyond adding a `mapper_version` to make future correction safe.

---

## Part 2 — Stages

Each stage is independently verifiable: `python3 scripts/run_pytest.py` must pass, the diff is inspected, and the result is recorded in `IMPLEMENTATION_LOG.md` before the next stage starts.

### Stage 0 — Test hygiene and cache purge
- **Goal:** tests never touch repository state; committed cache free of fixtures.
- **Files:** `tests/conftest.py`, `data/llm/feedback_cache.json`.
- **Invariant:** no test writes outside tmp.
- **Change:** autouse fixture sets `LLM_FEEDBACK_CACHE_PATH` to a tmp file; remove the 6 "Generated/Cook it." entries.
- **Tests:** existing suite. **Rollback:** revert. **Done:** suite green; `git diff data/llm` shows only fixture removal.

### Stage 1 — Typed recovery outcome and error containment
- **Goal:** every exit of `plan_with_llm_feedback` returns the deterministic result plus `report["llm_recovery"]`; LLM/data errors never escape.
- **Files:** new `src/llm/recovery_types.py` (`RecoveryState` enum, `RecoveryOutcome`), `src/planning/orchestrator.py`.
- **Invariant:** planner result is never replaced by an exception from the LLM layer.
- **Change:** wrap generation/validation/pool update in typed handlers; classify exits; attach outcome; keep `stats["llm_feedback_attempts"]` for compatibility.
- **Tests:** new `tests/test_llm_recovery_outcome.py` (R-12 shape; state per exit); preserve `test_planning_orchestrator_feedback.py`.
- **Rollback:** revert file. **Done:** R-12 returns a result with state `DATA_SOURCE_FAILURE`.

### Stage 2 — Provenance at the resolution boundary
- **Goal:** `fdc_id`, description, data type, method and mapper version travel with every resolved ingredient.
- **Files:** `src/ingestion/ingredient_cache.py` (`CacheEntry.provenance`, `mapper_version`), `src/ingestion/nutrient_mapper.py` (`MAPPER_VERSION`), `src/providers/api_provider.py` (`provenance` key), `src/llm/ingredient_matcher.py` (`canonical_name` = USDA description).
- **Invariant:** additive; `per_100g` unchanged; legacy cache files load.
- **Tests:** cache round-trip with/without provenance; provider dict contains `provenance`; matcher surfaces description.
- **Done:** F-05 passes (fdc_id visible).

### Stage 3 — Deterministic diagnosis and `GapSpec`
- **Goal:** decide *before* any LLM call whether recipes can help and what they must satisfy.
- **Files:** new `src/llm/recovery_diagnosis.py`; `src/planning/orchestrator.py` (call it).
- **Invariant:** LLM is called only with a `GapSpec`; unrecoverable reasons are typed.
- **Change:** checks for impossible targets, empty pool, unheld required tags, FM-3/batch/tag codes, FM-5 search budget; otherwise builds `GapSpec{kind, slots, per_meal_targets, cook_time_cap, excluded_ingredients, required_tags, nutrient_gaps, existing_recipe_names, known_ingredient_vocabulary}`; context sent to the LLM is the `GapSpec`.
- **Tests:** `tests/test_llm_recovery_diagnosis.py` (R-05/06/07/10/11 → unrecoverable; R-02/04/08 → GapSpec with expected fields).
- **Done:** Family D passes.

### Stage 4 — Semantic validation gates
- **Goal:** accepted drafts are resolvable, safe, plausible, useful, and not duplicates.
- **Files:** `src/llm/recipe_validator.py`, `src/llm/schemas.py` (`RecipeDraft.cooking_time_minutes` optional), `src/llm/recipe_generator.py` (prompt asks for cook time), `src/llm/repository.py` (near-duplicate helper).
- **Change:** unresolvable ⇒ `INGREDIENT_UNRESOLVED` (no demotion); `excluded_ingredients` token match ⇒ `EXCLUDED_INGREDIENT`; identity gate on provenance description ⇒ `INGREDIENT_IDENTITY_MISMATCH`; cook time from draft (provenance `llm_claimed`), fallback rejection when absent and a cap applies; fitness vs `GapSpec` ⇒ `NOT_USEFUL`; near-duplicate ⇒ `DUPLICATE`.
- **Existing tests to change:** the three `to_taste_fallback` tests and the `cooking_time == 10` assertion (they assert behaviour the evaluation showed to be defective).
- **Done:** Family H passes; P5 draft rejected.

### Stage 5 — Candidate pool, persist-on-success, provenance, no rebuild
- **Files:** `src/planning/orchestrator.py`, `src/llm/repository.py` (`provenance` on written recipes), `src/data_layer/recipe_db.py` (read `provenance`), `src/llm/types.py`.
- **Change:** accepted recipes go to an in-memory candidate pool with tags derived deterministically (time bucket); planner retries; on success, persist only the recipes the plan uses, with provenance; failed requests persist nothing; incremental update failure ⇒ `DATA_SOURCE_FAILURE`.
- **Tests:** J family; residue = 0 for failed requests; R-15 pool size unchanged.

### Stage 6 — Improvement criterion and termination
- **Files:** `src/llm/recovery_diagnosis.py` (`feasibility_signal`), orchestrator.
- **Change:** signal computed before/after each attempt in the dimension named by the `GapSpec`; no improvement ⇒ `NO_USEFUL_RECOVERY_FOUND`; attempts exhausted ⇒ `RECOVERY_LIMIT_REACHED`; nothing accepted ⇒ `INVALID_RECOVERY_OUTPUT`.
- **Tests:** K/L family.

### Stage 7 — Tagging: merge writes, schema-bearing prompt, deterministic buckets
- **Files:** `src/llm/tag_repository.py` (`upsert_recipe_tags(..., replace=False)` merge), `src/llm/recipe_tagger.py`, `src/api/server.py`, `src/cli.py`.
- **Change:** prompt embeds `RecipeTagsJson` schema and registry slugs; LLM may emit `tag_slugs_by_type` only from the registry; per-recipe `tag_metadata` gets `source="llm"`, `eligibility="proposed"`; `prep_time_bucket` overwritten by deterministic bucket; write merges.
- **Tests:** I family; T-04 preserved entries.

### Stage 8 — NL intent: constraints, stated fields, mapping rules
- **Files:** `src/llm/schemas.py` (`PlannerConstraints`, `stated_fields`), `src/llm/constraint_parser.py` (prompt), `src/data_layer/user_profile.py` (mapping), `src/api/server.py` (plan-from-text: no hard filters from NL; `defaulted_fields` warning).
- **Tests:** A/B/C via unit tests with fixed model outputs; live re-run in Phase 12.

### Stage 9 — Surface and contracts
- **Files:** `src/output/formatters.py` (nothing if `report` passthrough suffices — verify), `openapi/openapi.json` regen if any request model changed, docs (`docs/llm/roadmap.md` status note, AGENTS.md LLM rules).
- **Done:** OpenAPI check green; contract tests green.

### Stage 10 (conditional) — Mapper version and cache tagging
- Add `MAPPER_VERSION` and record it; do **not** change nutrient values in this mission unless the existing mapper tests already contradict USDA (they encode 1110 as µg×40 and 1114 as IU, which is the swap the tribunal verified). Decision deferred to the log after Stage 2.
