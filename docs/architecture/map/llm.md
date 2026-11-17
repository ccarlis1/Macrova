# LLM — optional assistants, validation gates, recovery loop and the tag system

Status: implemented · Code: `src/llm/`, `src/config/` · Facts: [generated/llm.md](generated/llm.md)

## Purpose
Optional LLM help around a deterministic planner: generating recipes, recovering from planner failures, parsing natural-language config, matching ingredient names and proposing tags. The LLM is never the authority. Output is schema-parsed, numbers are recomputed from ingredient data, and nothing persists until deterministic gates pass. The package also holds the canonical tag store and the deterministic tag filter, which need no LLM.

## Entry points
- `src/api/server.py::generate_validated_recipes_endpoint` and `src/cli.py::main` → `src/llm/pipeline.py::generate_validate_persist_recipes`.
- `src/api/server.py::plan_meals_endpoint` and `src/api/server.py::plan_from_text_endpoint` (planning_mode assisted, assisted_cached or assisted_live), plus the CLI → `src/planning/orchestrator.py::plan_with_llm_feedback`.
- `src/api/server.py::plan_from_text_endpoint` → `src/llm/constraint_parser.py::parse_nl_config`.
- `src/api/server.py::ingredient_match_endpoint` → `src/llm/ingredient_matcher.py::match_ingredient_queries`, then `src/llm/ingredient_matcher.py::validate_matches`.
- `src/api/server.py::generate_recipe_tags_endpoint` (needs llm_enabled=true in the request) → `src/llm/recipe_tagger.py::tag_recipes` → `src/llm/tag_repository.py::upsert_recipe_tags`.
- `src/api/tag_routes.py` (list, create, rename, alias, merge) and `src/api/recipe_sync.py` → `src/llm/tag_repository.py`.
- `src/api/server.py::build_plan_inputs` → `src/llm/tag_filtering_service.py::apply_tag_filtering`.

## How it works
1. **Client and settings.** `src/config/llm_settings.py::load_llm_settings` reads LLM_API_KEY, LLM_MODEL and LLM_ENABLED (inferred from the key when unset), plus timeout, retry and QPS. `src/llm/client.py::LLMClient.generate_json` posts to an OpenAI-compatible endpoint (LLM_BASE_URL) at temperature 0, rate-limits requests, retries on 429 and 5xx, and returns a JSON object or a typed `src/llm/client.py::LLMClientError`.
2. **Recipe generation.** `src/llm/recipe_generator.py::generate_recipe_drafts` sends the RecipeDraft contract and the context. It requires a drafts envelope with exactly the requested count, normalizes known aliases, and parses each draft with `src/llm/schemas.py::parse_llm_json`; a malformed draft is dropped alone. `src/llm/recipe_validator.py::validate_recipe_draft` then applies its gates in order: USDA-capable provider, exclusions (class-aware tokens), unit and quantity (`src/ingestion/ingredient_validator.py::IngredientValidator`), "to taste" only for seasonings, all-or-nothing resolve_all, an identity check of the name against the USDA description, allergen-table coverage, nutrition recomputation with plausibility limits (0 < kcal ≤ 2500, fat ≤ 85% of kcal above 400 kcal), cook time (a claimed time is checked against the cap; the heuristic applies only when no cap is set), dietary-flag consistency, fitness against the GapSpec, a required meal-role slug, and near-duplicates. `src/llm/repository.py::append_validated_recipes` dedupes by fingerprint, assigns deterministic ids and writes atomically with provenance.
3. **Recovery loop** (`src/planning/orchestrator.py::plan_with_llm_feedback`): plan → on failure `src/llm/recovery_diagnosis.py::diagnose` returns a GapSpec (candidate, uniqueness, nutrient or macro gap) or an UnrecoverableReason, without calling the LLM → drafts come from the feedback cache or the LLM via `src/llm/planner_assistant.py::suggest_targeted_recipe_drafts`, which sees only the GapSpec and the earlier rejections → validation against the GapSpec → accepted drafts join an in-memory candidate pool → `src/llm/recovery_diagnosis.py::feasibility_signal` must improve or the loop stops → replan, up to 3 attempts. On success, only recipes the plan uses are persisted. Every exit attaches a RecoveryOutcome to report["llm_recovery"].
4. **Feedback cache.** `src/llm/feedback_cache.py::build_feedback_cache_key` hashes the failure signature, GapSpec context, count, model and schema version. assisted replays cached drafts and fills misses live; assisted_cached raises `src/llm/feedback_cache.py::DeterministicCacheMissError` on a miss; assisted_live bypasses the cache. The default file is `data/llm/feedback_cache.json`.
5. **NL config.** `src/llm/constraint_parser.py::parse_nl_config` embeds the PlannerConfigJson JSON schema in the prompt and accepts a valid `src/llm/schemas.py::PlannerConfigJson` or raises `src/llm/constraint_parser.py::PlannerConfigParsingError`; partial configs are never returned. `src/data_layer/user_profile.py::user_profile_from_planner_config` maps it to a profile and drops schedule_days the user did not state. The endpoint keeps cuisine and budget soft, while dietary_flags become the hard pool filter.
6. **Ingredient matching.** LLM-proposed names below 0.7 confidence are rejected; the rest must resolve through the USDA provider, and canonical_name is the USDA description.
7. **Tagging lifecycle.** The store is one JSON file at `src/data_layer/user_data.py::recipe_tags_path`. It holds tag_registry, tag_aliases and tags_by_id, and seed tags are merged in on every load. Slugs are typed slugs (tag_slugs_by_type) with tag types context, time, nutrition and constraint. `src/llm/tag_repository.py::enrich_tag_meta` fills in the semantic class from the tag type, the class booleans, and eligibility=proposed for LLM tags. Users and the system write through recipe sync and the tag routes. `src/llm/recipe_tagger.py::tag_recipes` limits the LLM to registry slugs and a closed cuisine list, derives prep_time_bucket and time-* slugs from the cook time, drops dietary flags that contradict the ingredients, and records the remaining slugs as llm/proposed. Planner use splits two ways: `src/llm/tag_repository.py::load_canonical_recipe_tag_slugs` feeds scoring and preferred tags, and `src/llm/tag_repository.py::load_hard_eligible_recipe_tag_slugs` (via `src/llm/tag_repository.py::is_planner_hard_eligible`) feeds required slot tags.
8. **Pool filtering.** Before conversion, `src/llm/tag_filter.py::filter_recipe_ids_by_preferences` matches the request's cuisine (OR across a list), cost_level, prep_time_bucket and dietary_flags against the tags_by_id fields. Untagged recipes fail any active filter.

## Modules
| Module | Role | Status |
|---|---|---|
| `src/config/llm_settings.py` | Env settings | implemented |
| `src/llm/client.py` | JSON-only HTTP client | implemented |
| `src/llm/schemas.py` | Strict pydantic contracts and the parse gate | implemented |
| `src/llm/recipe_generator.py` / `src/llm/planner_assistant.py` | Draft generation | implemented |
| `src/llm/recipe_validator.py` | Deterministic gates | implemented |
| `src/llm/repository.py` / `src/llm/types.py` | Validated-only persistence | implemented |
| `src/llm/pipeline.py` | Generate → validate → persist | implemented |
| `src/llm/recovery_diagnosis.py` / `src/llm/recovery_types.py` | Diagnosis, GapSpec, outcomes | implemented |
| `src/llm/feedback_cache.py` | Draft replay cache | implemented |
| `src/llm/constraint_parser.py` | NL → PlannerConfigJson | implemented |
| `src/llm/ingredient_matcher.py` | Name matching | implemented |
| `src/llm/ingredient_disambiguator.py` | LLM tie-break among USDA candidates | experimental, unwired |
| `src/llm/tag_repository.py` | Canonical tag store | implemented |
| `src/llm/tag_filter.py` / `src/llm/tag_filtering_service.py` | Pool filter | implemented |
| `src/llm/recipe_tagger.py` / `src/llm/time_bucket.py` | LLM tagging; cook-time buckets | implemented |
| `src/llm/usda_contract.py` | USDA-capable provider marker | implemented |

## Key types
- `src/llm/schemas.py::RecipeDraft` — untrusted recipe shape; units must come from a closed list.
- `src/llm/types.py::ValidatedRecipeForPersistence` — the only input the persistence layer accepts.
- `src/llm/recovery_types.py::GapSpec` — the only thing the recovery LLM sees; drafts are validated against it.
- `src/llm/recovery_types.py::UnrecoverableReason` — the refusal produced before any LLM call.
- `src/llm/recovery_types.py::RecoveryOutcome` / `src/llm/recovery_types.py::RecoveryState` — the typed terminal state of a recovery run (eight values).
- `src/llm/schemas.py::PlannerConfigJson` — NL config with typed constraints and stated_fields.
- `src/llm/schemas.py::RecipeTagsJson` — per-recipe tags: pool fields plus typed slugs.
- `src/llm/schemas.py::TagMetaJson` — registry record: tag type, source, eligibility, semantic class, booleans.
- `src/config/llm_settings.py::LLMSettings` — runtime config.

## Invariants
1. Strict schema before use: every LLM response goes through `src/llm/schemas.py::parse_llm_json` (extra keys are forbidden). Guard: `tests/test_llm_schemas.py`.
2. Only validated recipes are persisted: `src/llm/repository.py::append_validated_recipes` type-checks its input, and only `src/llm/recipe_validator.py::validate_recipe_drafts` builds the wrapper. Guards: `tests/test_llm_recipe_repository.py`, `tests/test_llm_types.py`.
3. An unresolved ingredient rejects the draft (no demotion to "to taste"). Guards: `tests/test_llm_recipe_validator_gates.py`, `tests/test_llm_pipeline.py`.
4. Nutrition comes from ingredient data, never from the LLM: the validator recomputes it. `.claude/hooks/check_llm_lane.py` blocks nutrition-named fields on pydantic models under `src/llm/`; PlannerTargets and PlannerConstraints are exempt because they hold user targets and limits.
5. Validation needs a USDA-capable provider: `src/llm/usda_contract.py::assert_usda_capable_provider`, called in the pipeline, the validator and the orchestrator. Guard: `tests/test_usda_contract.py`.
6. Recovery shows the LLM only a GapSpec, persists nothing unless the retried plan succeeds, contains LLM and USDA errors (DATA_SOURCE_FAILURE), and never rebuilds the pool from disk. Guards: `tests/test_planning_orchestrator_feedback.py`, `tests/test_llm_recovery_outcome.py`, `tests/test_llm_recovery_diagnosis.py`.
7. Deterministic by default: an omitted planning_mode means no LLM. Guard: `tests/test_planner_regression_with_llm_disabled.py`.
8. LLM slugs are never hard-eligible while proposed or rejected: `src/llm/tag_repository.py::is_planner_hard_eligible`. Guards: `tests/test_tag_repository_dm6_metadata.py`, `tests/planning/test_slot_constraints.py`, `tests/test_llm_recipe_tagger_gates.py`.
9. Tag upserts merge unless replace=True. The legacy tags projection on `src/data_layer/models.py::Recipe` is never written. Guards: `tests/test_llm_recipe_tagger_gates.py`, `tests/test_llm_recipe_repository.py`.
10. NL cuisine and budget never become hard filters, and an unstated schedule is dropped. Guards: `tests/test_api_plan_from_text.py`, `tests/test_nl_config_to_profile.py`.

## Depends on / used by
Depends on `src/providers/`, `src/ingestion/`, `src/nutrition/calculator.py`, `src/planning/allergens.py` and the planner (diagnosis reads phase models). Used by `src/api/`, `src/cli.py`, `src/planning/orchestrator.py`, `src/data_layer/recipe_db.py` and `src/mcp_server/`. Import graph: [generated/index.md](generated/index.md).

## Known gaps and traps
- No code moves a tag from proposed to approved; curation means editing the JSON by hand. Pool fields are not lifecycle-gated: LLM-written dietary_flags and cuisine act as hard filters right away.
- Generated and recovered recipes are saved without a tags_by_id entry; the draft's meal-role slug is checked and then discarded. They drop out of any tag-filtered request and never satisfy required tags. Diagnosis refuses FM-TAG-EMPTY for this reason.
- `src/ingestion/ingredient_validator.py::IngredientValidator` converts cup/tsp/tbsp to ml. USDA records have no gram weights, so drafts using volume units fail with NUTRITION_COMPUTATION_FAILED even though the prompt allows those units.
- FM-TAG-EMPTY and FM-5 are in the orchestrator's eligible set, but diagnose always refuses them; only FM-1, FM-2 and FM-4 reach the LLM.
- The feedback cache writes drafts into the tracked `data/llm/feedback_cache.json` even when the request fails. That file is outside MACROVA_DATA_DIR and the test guard. After assisted planning, the API re-resolves the whole on-disk pool through USDA to format the response.
- Slug normalization is duplicated: `src/llm/tag_filter.py` has its own token normalizer, and `src/llm/time_bucket.py::TagRegistry` honours NUTRITION_TAG_REPO_PATH. `src/llm/tag_repository.py::resolve` re-reads the file on every call. Experimental: `src/llm/ingredient_disambiguator.py` and resolution_mode="assisted" in `src/ingestion/ingredient_cache.py::CachedIngredientLookup` are exercised only by tests.
