# IMPLEMENTATION_LOG.md

Baseline before Stage 0: 1074 passed (2 third-party warnings), OpenAPI snapshot matches, branch `llm-overhaul` at `779af36`.

## Stage 0 — Test hygiene and cache purge
- `tests/conftest.py`: autouse fixture redirects `LLM_FEEDBACK_CACHE_PATH` to a per-test tmp file.
- `data/llm/feedback_cache.json`: removed 6 entries whose content was the unit-test fixture ("Generated"/"Cook it."); 30 → 24 keys.
- Result: 1074 passed. Diff inspected: only the two files above.

## Stage 1 — Typed recovery outcome and error containment
- New `src/llm/recovery_types.py` (`RecoveryState`, `GapSpec`, `UnrecoverableReason`, `AttemptRecord`, `RecoveryOutcome`).
- `src/planning/orchestrator.py`: `plan_with_llm_feedback` rewritten around the same loop semantics; every exit attaches `report["llm_recovery"]`; generation/validation/pool-update exceptions are classified (`DATA_SOURCE_FAILURE` for LLM/USDA errors, `SYSTEM_ERROR` otherwise) and the deterministic result is returned; the fallback rebuild from disk is no longer used (R-15 defect). `DeterministicCacheMissError` still raises by contract of `assisted_cached`.
- Tests: new `tests/test_llm_recovery_outcome.py` (6). Updated 2 tests in `tests/test_planning_orchestrator_feedback.py` whose assertions encoded the rebuild fallback and the old attempt label.
- Result: 1084 passed.

## Stage 2 — Provenance at the resolution boundary
- `src/ingestion/nutrient_mapper.py`: `MAPPER_VERSION = "1"`.
- `src/ingestion/ingredient_cache.py`: `CacheEntry.provenance` (additive; legacy entries load with `None` and report `method="legacy_cache"`); `lookup()` records query, fdc_id, description, data type, method (`deterministic`/`llm_tiebreak`), rank confidence and margin, mapper version, timestamp, selection reasons.
- `src/providers/api_provider.py`: provider dict gains `provenance` (additive; `per_100g` unchanged).
- `src/llm/ingredient_matcher.py`: `canonical_name` is the resolved USDA description when available (was an echo of the query).
- Tests: new `tests/test_ingredient_provenance.py` (4). Result: 1084 passed (counted with Stage 1).
- Stage 10 decision: the mapper's vitamin D and Foundation-energy handling is *not* changed in this mission (out of the LLM layer's scope); `MAPPER_VERSION` makes a later correction attributable.

## Stage 3 — Deterministic diagnosis and GapSpec
- New `src/llm/recovery_diagnosis.py`: `diagnose()` returns `UnrecoverableReason` (PIN_OR_BATCH_CONFLICT, REQUIRED_TAG_UNHELD, IMPOSSIBLE_TARGETS, EMPTY_POOL, SEARCH_BUDGET) or a `GapSpec` (candidate_gap / uniqueness_gap / nutrient_gap / macro_gap) carrying per-meal targets, cook-time cap, exclusions, per-recipe nutrient minimums, gap slots, existing names and a known-ingredient vocabulary. `feasibility_signal()` / `improved()` measure progress in the gap's dimension.
- Tests: new `tests/test_llm_recovery_diagnosis.py` (10). Not yet wired into the loop (Stage 5).

## Stage 4 — Semantic validation gates
- `src/llm/recipe_validator.py` rewritten: no demotion (`INGREDIENT_UNRESOLVED`), class-aware exclusion match (`EXCLUDED_INGREDIENT`), identity gate on the resolved USDA description (`INGREDIENT_IDENTITY_MISMATCH`), plausibility envelope (`IMPLAUSIBLE_NUTRITION`), author-claimed cook time with provenance and slot-cap check (`COOK_TIME_EXCEEDS_CAP` / `COOK_TIME_UNKNOWN`), fitness against the GapSpec (`NOT_USEFUL`), near-duplicate rejection (`DUPLICATE`); accepted recipes carry `provenance`.
- `src/llm/schemas.py`: `RecipeDraft.cooking_time_minutes` (optional). `src/llm/recipe_generator.py`: aliases `cook_time`/`cooking_time` map to it; prompt asks for it and explains GapSpec keys.
- `src/data_layer/models.py`: `Recipe.provenance`. `src/data_layer/recipe_db.py` and `src/llm/repository.py`: read/write it; `find_near_duplicate()` helper.
- Identity gate measured on the 83 real cache entries: rejects `oats`→oat oil, `eggs`→egg bread, `bell pepper`→nachos, `milk 1%`→cottage cheese; 0 false positives; misses the 5 same-head-word errors (cherries, banana powder, deli roll, flour tortillas, acai drink).
- Tests changed because they asserted the defective behaviour: 3 demotion tests and 3 `EMPTY_RECIPE` expectations in `tests/test_llm_recipe_validator.py`, 1 in `tests/test_llm_pipeline.py`. New `tests/test_llm_recipe_validator_gates.py` (12).
- Result: 1106 passed.

## Stages 5 + 6 — Loop core: candidate pool, persist-on-success, improvement signal, termination
- `src/planning/orchestrator.py::plan_with_llm_feedback` rewritten: `diagnose()` runs before any LLM call and can refuse (typed reason, `llm_calls=0`); the LLM receives the `GapSpec` plus the previous attempt's rejection reasons; drafts are validated against the GapSpec and the current candidate pool; accepted recipes become in-memory candidates with deterministic `time-*` tags and hard-eligible attributes; the planner is re-run only when something was accepted; `feasibility_signal()`/`improved()` decide `NO_USEFUL_RECOVERY_FOUND`; persistence happens only after a successful retry and only for the recipes the plan uses, with provenance (`source=llm_feedback`, gap kind, attempt, model). Removed `_rebuild_recipe_pool` and `_append_new_recipes_to_pool` (the defective fallback path).
- `tests/test_planning_orchestrator_feedback.py` rewritten (11 contract tests through the real planner and a scripted client: success + provenance, GapSpec content, zero residue on failure, exclusion rejection, three unrecoverable refusals with 0 LLM calls, cook-time cap gap, rejection feedback, cache replay/model invalidation, strict-mode raise, dedupe, typed pool-update failure). Two API strict-cache tests given a non-empty pool (an empty pool is now refused before the cache is consulted).
- Result: 1109 passed.

## Stage 7 — Tagging
- `src/llm/tag_repository.py::upsert_recipe_tags` merges by default (`replace=True` is explicit).
- `src/llm/recipe_tagger.py` rewritten: prompt embeds the JSON schema and the registry's canonical slugs; closed cuisine vocabulary (unknown → `unknown`); `prep_time_bucket` and `time-*` derived from `cooking_time_minutes`; proposed slugs restricted to the registry and recorded per recipe with `source="llm"`, `eligibility="proposed"` (never hard-eligible); invalid outputs omitted.
- Tests: new `tests/test_llm_recipe_tagger_gates.py` (5); one expectation in `tests/test_llm_recipe_tagger.py` updated (bucket is derived, not guessed).

## Stage 8 — Natural-language intent
- `src/llm/schemas.py`: `PlannerConstraints` (allergies, dislikes, likes, calorie ceiling, fat range, micronutrient goals with validated keys, dietary flags, τ) and `stated_fields` on `PlannerConfigJson`; `defaulted_fields()`.
- `src/llm/constraint_parser.py`: prompt explains the constraints block, unit conversions, `stated_fields`, "never clamp invalid values", "emit schedule_days only when described".
- `src/data_layer/user_profile.py`: constraints mapped to `UserProfile` (allergies/dislikes → HC-1, ceiling → HC-5, stated fat range overrides the budget-derived one, micronutrient goals, τ); an unstated `schedule_days` is dropped when the model reported `stated_fields`; `planner_config_interpretation_report()`.
- `src/api/server.py` plan-from-text: NL cuisine/budget never become hard filters; `constraints.dietary_flags` feed the canonical tag filter; `warnings.nl_interpretation` lists stated/defaulted/derived/dropped fields.
- Tests: 4 added to `tests/test_nl_config_to_profile.py`, 1 to `tests/test_api_plan_from_text.py`.
- Result: 1119 passed.

## Stage 9 — Surface, contracts, docs
- `report["llm_recovery"]` reaches API and CLI JSON through the existing report passthrough (`format_result_json`); no formatter change needed. OpenAPI snapshot unchanged (`--check` passes; no request model changed).
- `src/llm/recipe_generator.py`: per-draft rejection (a malformed sibling no longer discards a whole batch; raises only when no draft parses). Motivated by a live probe where one of three drafts failed strict schema.
- Docs: `AGENTS.md` LLM Feature Rules and Tagging Rules rewritten to the new contracts; `docs/llm/roadmap.md` overhaul note.
- Harness: `evaluation/llm_overhaul/harness/` adapted to the typed outcome; after-runs written with `_after` suffix.
- Result: see FINAL_VALIDATION.md.

