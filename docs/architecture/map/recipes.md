# Change recipes — which files to touch for common tasks

Each recipe: files in the order you'd edit them, then the checks that must pass. Procedures live in skills; this file says *where*.

## Add a planner hard constraint (HC-n)
Example: `9e776ae` Exempt meal-prep batch locks from HC-8 · `7b1f24f` benchmark: apply the HC-8 batch exemption to the oracle and labels · `b21294a` Fix C6: expand allergy exclusions by allergen class
1. `docs/planner/mealplan-specification-v3.md` — define it under §4 Hard Constraints. The next free number is HC-10; HC-7 and HC-9 exist in the spec but have no `check_hc*` function.
2. `src/planning/phase0_models.py::PlanningUserProfile` / `src/planning/phase0_models.py::MealSlot` — add any input the check reads (wire it from the API with the next recipe).
3. `src/planning/phase2_constraints.py` — add `check_hcN_*` beside `src/planning/phase2_constraints.py::check_hc5_max_daily_calories`, with the same signature.
4. `src/planning/phase6_candidates.py::_filter_step_1_through_7` — call it at its step. If it doesn't depend on state, also call it in `src/planning/phase6_candidates.py::_filter_hard_constraints_only` (FC-5 lookahead).
5. `src/planning/phase6_candidates.py::check_slot_statically` — if it doesn't depend on state, add it to `blocking` so FM-1 names it.
6. `src/planning/phase1_state.py::validate_pinned_assignments` — pins are checked inline here, not through phase2. Add the rule and its `failed_hc` value (→ FM-3).
7. `src/planning/phase9_carb_scaling.py::generate_scaled_variants` — re-runs every HC on scaled variants.
8. `src/planning/failure_attribution.py::daily_validation` / `_enumerate_day` — these re-implement HC-5/HC-8 for attribution. Mirror a state-dependent HC here.
9. `src/api/failure_explanations.py::_TABLE` — add an `("FM-1", "HC-n")` plain-language row if the constraint can empty a slot.
10. Tests: `tests/test_phase2_constraints.py`, `tests/test_phase6_candidates.py`, `tests/test_phase1_state.py`, `tests/test_failure_attribution.py`.
11. `evaluation/benchmark/oracle.py::Oracle.evaluate` and `evaluation/harness/compare.py::verify` — the oracle doesn't import `src/`, so implement the rule separately in both. Then add a scenario (see the benchmark recipe below).
Checks: `python3 scripts/run_pytest.py`, `python3 evaluation/benchmark/build.py --check`, benchmark-audit skill Mode 1, `python3 scripts/gen_architecture_map.py --check`
Watch out:
- Never edit oracle labels or scenarios to make a result pass. The oracle changes only after a spec change the user approved, in its own commit (like `7b1f24f`).
- `.claude/hooks/check_determinism.py` flags new unsorted dict/set iteration in `src/planning/`. Sort before you iterate.

## Add a field to the plan API end-to-end
Example: `90c5afe` Carry max_daily_calories through /api/v1/plan and Flutter · `d0a7968` + `88245eb` BE-17 demographic (backend, then Flutter) · response side: `567eb28` (`meal_type_match`) + `fe29b2a` Show meal-type match on meal cards
1. `src/api/server.py::PlanRequest` — add it as optional with a safe default and a `Field(description=...)`. Add it to `src/api/server.py::PlanFromTextRequest` too if the text route should take it.
2. `src/api/server.py::_build_user_profile` — copy it onto the profile. `src/api/server.py::plan_from_text_endpoint` sets profile fields separately.
3. `src/data_layer/models.py::UserProfile` — add the attribute. If it's stored in the profile YAML, also update `src/data_layer/user_profile.py`.
4. `src/planning/converters.py::convert_profile` → `src/planning/phase0_models.py::PlanningUserProfile` — the planner reads it here.
5. `src/planning/orchestrator.py::build_plan_request_from_profile` (CLI/HTTP parity payload) and `src/cli.py`.
6. `src/mcp_server/models.py::Targets` and `src/mcp_server/tools.py::plan_meals` — the MCP server builds its own `PlanRequest`.
7. For a response field: emit it in `src/output/formatters.py::format_result_json` and declare it on `src/api/server.py::PlannedMeal` / `src/api/server.py::PlanResponse`.
8. Run `python3 scripts/run_export_openapi.py` → `openapi/openapi.json`.
9. `frontend/lib/models/models.dart::PlanRequest` — add the field and update `fromJson`, `toJson` (omit null) and `withPlanningMode`. Response fields go on `frontend/lib/models/models.dart::Meal` / `MealPlan`.
10. Where the value comes from: `frontend/lib/models/user_profile.dart::UserProfile`, `frontend/lib/screens/profile_screen.dart`, `frontend/lib/screens/planner_config_screen.dart` (builds the request), `frontend/lib/features/agent/agent_pane_screen.dart::planFromTextBody`.
11. Tests: `tests/test_api_v1_and_openapi.py`, a `tests/api/` test that includes the field-omitted case, and Dart round-trip tests like `frontend/test/plan_request_demographic_test.dart`.
12. `docs/contracts/plan-response.md`.
Checks: `python3 scripts/run_pytest.py`, `python3 scripts/run_export_openapi.py --check`, `cd frontend && flutter analyze && flutter test`, benchmark-audit Mode 1 if the planner reads the field, `python3 scripts/gen_architecture_map.py --check`. Procedure: api-contract skill.
Watch out:
- Fields get dropped silently between layers. HC-5 never reached the planner over HTTP until `90c5afe`, and `9eddd3c` fixed `str(enum)` mangling `dietary_flags` in `_build_user_profile`. Assert that the value reaches `PlanningUserProfile`, not just that the request returns 200.
- `frontend/lib/providers/meal_plan_provider.dart::MealPlanProvider` re-runs a plan through `PlanRequest.withPlanningMode`, which drops any field you forget to copy there.

## Add a tag type or semantic class
Example: `567eb28` Prefer recipes tagged for the slot's meal type (§4.3) (`meal_role` slugs) · `a9d48b7` extend recipe_tags.json as single source of truth
1. `docs/tagging/tag-semantics-contract.md` — add the class row (capability flags, producers) first. This doc is the contract.
2. `src/llm/tag_repository.py::_SEMANTIC_CLASS_DEFAULTS` and `_DEFAULT_SEMANTIC_CLASS_BY_TAG_TYPE` hold the flags. Seed slugs go in `_SEED_TAGS`; a new tag type also goes in `_VALID_TAG_TYPES`.
3. The tag-type literal is repeated in `src/llm/schemas.py::TagType`, `src/api/tag_routes.py::TagCreateRequest` and `src/llm/recipe_tagger.py::_LLM_TAG_SCHEMA`. Update all three.
4. `data/recipes/recipe_tags.json` — registry plus `tags_by_id`. Writes go through `src/llm/tag_repository.py::upsert_recipe_tags` (it merges by default).
5. Hard filtering: `src/llm/tag_repository.py::is_planner_hard_eligible`, `src/planning/phase6_candidates.py::_matches_slot_required_tags`. Pool filters: `src/llm/tag_filter.py::filter_recipe_ids_by_preferences` via `src/llm/tag_filtering_service.py::apply_tag_filtering`.
6. Soft scoring: `src/planning/phase4_scoring.py::preferred_tag_bonus` / `meal_type_bonus` (spec §8).
7. `src/llm/recipe_tagger.py::tag_recipes` — the prompt lists registry slugs by type. LLM tags stay `proposed`.
8. API: `src/api/tag_routes.py::_to_payload`. Regenerate OpenAPI if a schema changed.
9. Flutter: `frontend/lib/models/tag.dart::TagMeta` (e.g. `mealRoleClass`), plus `frontend/lib/widgets/planner/tag_pool_filter_section.dart` if the tag is shown.
10. Benchmark: `evaluation/benchmark/library.py::TAG_VOCAB` / `HARD_ELIGIBLE_TAG_TYPES` and `evaluation/benchmark/recipe_tags.json` are separate copies.
11. Tests: `tests/test_tag_repository_dm6_metadata.py`, `tests/test_tag_filtering_service.py`, `tests/test_llm_recipe_tagger.py`, `frontend/test/tag_registry_dto_test.dart`.
Checks: `python3 scripts/run_pytest.py`, `python3 scripts/run_export_openapi.py --check`, `cd frontend && flutter test`, benchmark-audit Mode 1, `python3 scripts/gen_architecture_map.py --check`
Watch out:
- Hard eligibility is implemented twice: `is_planner_hard_eligible` and the raw-dict fallback `src/llm/tag_repository.py::_tag_meta_is_hard_eligible`. Keep them in sync. `hard_filter_allowed` never makes an LLM `proposed` tag binding.
- `Recipe.tags` in `data/recipes/recipes.json` is a legacy projection. Never decide from it or write to it, and never copy `_normalize_slug`.

## Change the LLM pipeline (validation gate or recovery outcome)
Example: `9a9f626` Overhaul LLM layer: typed recovery loop, validation gates, tagging safety · `7f48e05` BE-18: `to taste` only for seasonings; drop recipes that hide nutrients
1. `src/llm/recipe_validator.py::validate_recipe_draft` — insert the gate in its docstring's order (steps 1–8) and fail through `_validation_failure` with a new `error_code`. Bump `VALIDATION_VERSION` when what gets accepted changes; it is recorded in provenance.
2. `src/llm/schemas.py::RecipeDraft` / `ValidationFailure` — only if the draft shape changes.
3. `src/llm/pipeline.py::generate_validate_persist_recipes` and `src/planning/orchestrator.py::plan_with_llm_feedback` both call `validate_recipe_drafts`. Pass new arguments through both.
4. If user saves need the same rule: `src/api/recipe_sync.py::_check_line_is_plannable` plus an error code in `src/api/error_mapping.py` (as in `7f48e05`).
5. Recovery: add a terminal state to `src/llm/recovery_types.py::RecoveryState`, or a refusal code to `UnrecoverableReason`.
6. `src/llm/recovery_diagnosis.py::diagnose` — decide before any LLM call. `_NEVER_RECOVERABLE` lists the FM codes that new recipes can't fix.
7. `src/planning/orchestrator.py::plan_with_llm_feedback` — every exit goes through `_attach_outcome`, and exceptions map in `_classify_exception`.
8. Tests: `tests/test_llm_recipe_validator_gates.py`, `tests/test_llm_pipeline.py`, `tests/test_llm_recovery_diagnosis.py`, `tests/test_llm_recovery_outcome.py`, `tests/test_planning_orchestrator_feedback.py`.
9. `evaluation/llm_overhaul/harness/run_recovery.py` — uses a scripted LLM by default; `--live` needs keys. Record results under `evaluation/llm_overhaul/`.
10. `docs/llm/roadmap.md`, plus the AGENTS.md LLM section if the pipeline contract changes.
Checks: `python3 scripts/run_pytest.py`, `PYTHONPATH=. .venv/bin/python evaluation/llm_overhaul/harness/run_recovery.py`, `python3 scripts/run_export_openapi.py --check` if server models changed, `python3 scripts/gen_architecture_map.py --check`
Watch out:
- `.claude/hooks/check_llm_lane.py` blocks pydantic models in `src/llm/` that have nutrition-named fields. It already matches `PlannerConstraints.max_daily_calories` / `micronutrient_goals`, so any edit to `src/llm/schemas.py` trips it until those are added to its `CLASS_ALLOWLIST`. Dataclasses such as `GapSpec` aren't checked.
- `src/api/failure_explanations.py` runs `diagnose` on every failed deterministic plan (`report.failure_cause`; Flutter reads `cause == "EMPTY_POOL"`). Diagnosis changes therefore alter non-LLM responses too.

## Add a planner failure mode (FM-*)
Example: `07b0378` added additional failure codes to planner · `ce8c9d4` Fix C2a: post-search failure attribution
1. `docs/planner/mealplan-specification-v3.md` — add an entry under §11 Failure Modes (trigger and attribution order).
2. Raise it in `src/planning/phase7_search.py::run_meal_plan_search` through `src/planning/phase10_reporting.py::result_from_failure`. Pre-search failures go in `src/planning/planner.py::plan_meals`.
3. `src/planning/phase10_reporting.py::_FIX_HINTS` (stable hint), a `build_report_fm_*` builder and the default message in `build_failure`. Add it to `normalize_planner_report` if the code only arrives as `failure_mode`.
4. `src/planning/failure_attribution.py::diagnose_exhausted_search` — needed if the cause is only known after search.
5. `src/api/server.py::PlanFailure` — extend the `code` Literal. This changes OpenAPI.
6. `src/api/error_mapping.py::map_exception_to_api_error` — add a constant and the `ApiContractError` 422 entry, but only if the code can surface as an HTTP error.
7. `src/api/failure_explanations.py::_TABLE` — explanation and fix rows (plus `_CODE_ALIASES` if needed).
8. `src/llm/recovery_diagnosis.py::diagnose` — can a new recipe fix it? If not, add the code to `_NEVER_RECOVERABLE`.
9. Run `python3 scripts/run_export_openapi.py`.
10. Flutter: `frontend/lib/widgets/failure_view_model.dart::FailureViewModel` doesn't care which code it gets (chip, then `explanation`/`fix`), so edit it only for a new action. Add a fixture in `frontend/test/fixtures/` and a case in `frontend/test/plan_failure_dto_test.dart`.
11. `docs/frontend/failure-handling.md`, `docs/contracts/plan-response.md` (`PlanFailure` shape).
12. Benchmark: `evaluation/benchmark/oracle.py::Oracle.evaluate` produces the expected codes; `evaluation/benchmark/build.py::acceptable_codes` lists the tolerated alternatives.
13. Tests: `tests/test_phase10_reporting.py`, `tests/test_phase7_search.py`, `tests/test_failure_explanations.py`, `tests/test_api_error_mapping.py`, `tests/test_api_v1_and_openapi.py`.
Checks: `python3 scripts/run_pytest.py`, `python3 scripts/run_export_openapi.py --check`, `cd frontend && flutter test`, benchmark-audit Mode 1, `python3 scripts/gen_architecture_map.py --check`. Debugging: verify-stack skill.
Watch out:
- `FM-2` (`failure_mode`) and `FM-MACRO-INFEASIBLE` (the `failures[]` code) are one failure under two names. Don't add a third, and never branch Flutter on `termination_code`.
- A success with caveats is a `report.warnings` entry (e.g. `src/planning/phase10_reporting.py::build_sodium_warning`), not a failure mode.

## Add a benchmark scenario
Example: `2c62010` Benchmark: D9 oracle fallback, add MB-152, refresh baseline · `8009699` Benchmark: MB-153 pins a lying gluten-free recipe; oracle reads dietary_flags.
1. `evaluation/benchmark/library.py::RECIPES` — only if a new recipe is needed.
2. `evaluation/benchmark/scenarios.py::S` — append a call (helpers `P`, `day`, `std3`, `B`) with `intended` and `spec_notes`.
3. Run `python3 evaluation/benchmark/build.py`. It regenerates `evaluation/benchmark/scenarios.json`, `evaluation/benchmark/scenarios_index.md` and `evaluation/benchmark/recipes.json`.
4. `evaluation/benchmark/README.md` — update the counts and the outcome mix.
5. `evaluation/reports/benchmark_failure_analysis.md` — map any new disagreement to a cluster's `**Scenarios:**` line.
6. Run the harness. Ask before committing `evaluation/harness/results/results.json` / `evaluation/harness/results/compare.json`.
Checks: `python3 evaluation/benchmark/build.py --check`, benchmark-audit Mode 1 (expect `NEW` rows)
Watch out:
- IDs are positional (`MB-{len(SCENARIOS)+1}`). Only append; inserting renumbers every later scenario and breaks the cluster mappings.
- `evaluation/benchmark/build.py` reads the gitignored ingredient cache (.cache/ingredients), so it fails in a fresh worktree. If `--check` disagrees, fix your label or the planner, never `evaluation/benchmark/oracle.py`.

## Add a user-writable data store
Example: `e363ca3` BE-22: user data folder, empty starting pool, starter-pack import
1. `src/data_layer/user_data.py` — add `DEFAULT_*_PATH` / `*_FILE` constants and a resolver like `src/data_layer/user_data.py::meal_prep_batches_path`. Seed the store in `setup_user_data` if it shouldn't start empty.
2. Write one repository that owns reads and writes, resolving the path when it's constructed (pattern: `src/data_layer/meal_prep.py::MealPrepBatchRepository`).
3. Callers (API routers, `src/cli.py`, `src/planning/orchestrator.py`) get the path from the resolver, never from a literal.
4. `scripts/setup_user_data.py` and `.gitignore` for the repo-default path.
5. `tests/conftest.py::GUARDED_DATA_FILES` — add the committed default so tests fail if they write to it. Cover the resolver in `tests/test_user_data.py`.
6. AGENTS.md, "Data and Persistence Rules".
Checks: `python3 scripts/run_pytest.py`, `python3 scripts/run_export_openapi.py --check` if routes changed, `python3 scripts/gen_architecture_map.py --check`
Watch out:
- Module-level constants (`src/api/server.py::DEFAULT_TAG_PATH`, `src/api/tag_routes.py::DEFAULT_TAG_PATH`) capture `MACROVA_DATA_DIR` at import time. Tests must patch them.
- Reference data (`data/reference/`) and the MCP sample path are not user data. Don't route them through `src/data_layer/user_data.py`.
