# API — FastAPI HTTP surface over the planner, recipe store, tags and meal prep

Status: implemented · Code: `src/api/`, `openapi/openapi.json`, `scripts/export_openapi.py`, `scripts/run_export_openapi.py`, `.claude/hooks/check_contract.py` · Facts: [generated/api.md](generated/api.md), [generated/routes.md](generated/routes.md)

## Purpose
The HTTP backend the Flutter app talks to. It validates requests, loads server-side state (recipe pool, tag store, pins, meal-prep batches), hands the deterministic planner a fully resolved pool, and shapes the result into `PlanResponse` or a `{"error": {"code", "message"}}` envelope. The committed OpenAPI snapshot is the contract the Dart client is kept in lockstep with.

## Entry points
- `src/api/server.py::app` — served by `uvicorn src.api.server:app` or `python -m src.api.server` (port 8000, the Flutter default base URL).
- `src/api/server.py::plan_meals_endpoint` — Flutter `ApiService.plan` in `frontend/lib/services/api_service.dart`.
- `src/api/server.py::plan_from_text_endpoint` — Flutter agent pane via `frontend/lib/features/agent/agent_api.dart`.
- `src/api/server.py::build_plan_inputs`, `src/api/server.py::format_plan_response`, `src/api/server.py::PlanRequest` — also imported by `src/mcp_server/tools.py`, so changes here move MCP behavior too.
- `src/api/tag_routes.py::router`, `src/api/meal_prep_routes.py::router` — mounted under `/api/v1`.
- `scripts/run_export_openapi.py` — regenerate or `--check` the snapshot.

## How it works
Plan request (`POST /api/v1/plan`):
1. Pydantic validates `src/api/server.py::PlanRequest` (legacy-schedule merge, `schedule_days` length and `day_index` checks). Any validation error becomes 400 `INVALID_REQUEST` via `src/api/server.py::_request_validation_exception_handler`, never FastAPI's 422.
2. `src/planning/orchestrator.py::hydrate_parity_plan_context` loads persisted pins from the profile YAML (`src/data_layer/user_profile.py::DEFAULT_USER_PROFILE_PATH`) and active batches (`src/data_layer/meal_prep.py::MealPrepBatchRepository`). Client-sent `active_batches` is ignored.
3. `src/api/server.py::_build_user_profile` derives carbs (`src/data_layer/macro_targets.py::validate_macro_targets`; failure → 400 with `details.reason`) and migrates the schedule through `src/models/legacy_schedule_migration.py`.
4. Recipes load through `src/data_layer/recipe_db.py::RecipeDB` at `src/api/server.py::recipes_path`; `recipe_ids` narrows the pool. Tags load via `src/api/server.py::load_plan_tag_data` from `src/api/server.py::DEFAULT_TAG_PATH`.
5. `src/api/server.py::build_plan_inputs` applies pins, runs the tag pool filter (batch recipes protected), then calls `provider.resolve_all` on `src/planning/converters.py::extract_ingredient_names`. Every ingredient lookup, local table or USDA, happens here. Then `src/planning/converters.py::convert_recipes` (unresolved recipes dropped and logged) runs, canonical and hard-eligible tag slugs are attached, `src/planning/converters.py::convert_profile` builds the profile, and batch locks are set.
6. Omitted or `deterministic` `planning_mode` → `src/planning/planner.py::plan_meals`. Assisted modes require `src/config/llm_settings.py::load_llm_settings` to report enabled; otherwise `src/planning/orchestrator.py::LLMPlanningModeError` (`LLM_DISABLED`) → 422. When enabled, they run `src/planning/orchestrator.py::plan_with_llm_feedback`, then re-read the pool so the formatter sees persisted recipes.
7. `src/api/server.py::format_plan_response` → `src/output/formatters.py::format_result_json` (sets `plan_status`) → `src/api/failure_explanations.py::attach_failure_explanations` (`explanation`/`fix`/`cause`, `report.failure_cause`). It then merges `warnings.tag_filtering`, `warnings.exclusions` and `warnings.nutrition`; the endpoint adds `warnings.schedule_migration`.
8. Any other exception → `src/api/error_mapping.py::map_exception_to_api_error` → status + envelope.

`/plan-from-text` differs only at the front. Deterministic mode requires the prompt to be `src/llm/schemas.py::PlannerConfigJson` JSON and makes no LLM call; other modes parse NL with `src/llm/constraint_parser.py::parse_nl_config`. Cuisine or cost inferred from the prompt never becomes a hard filter. It adds `warnings.nl_interpretation`.

Composition and startup: `src/api/server.py` reads repo-root `.env` with setdefault before any import, resolves user-data paths at import time, includes the tag and meal-prep routers with prefix `/api/v1`, and adds permissive CORS. There is no lifespan or startup hook. Some `src/api/server.py` routes carry a second, unversioned `/api/...` decorator; the routers have none. `GET /api/v1/llm/status` returns only `enabled`, and Flutter gates assisted modes on it.

## Modules
| Module | Role | Status |
|---|---|---|
| `src/api/server.py` | App; plan, recipe, ingredient, nutrition and profile routes; models; shared plan-input builder | implemented |
| `src/api/recipe_sync.py` | Recipe save models; atomic upsert with save-time plannability check and tag writes | implemented |
| `src/api/tag_routes.py` | Tag registry list/create/rename/alias/merge | implemented |
| `src/api/meal_prep_routes.py` | Meal-prep batch CRUD with conflict validation | implemented |
| `src/api/error_mapping.py` | Exception → (status, envelope) table; error-code constants | implemented |
| `src/api/failure_explanations.py` | Plain-language text for `report.failures[]`; reporting only | implemented |

## Key types
- `src/api/server.py::PlanRequest` — plan input; `schedule_days` canonical, `schedule`/`legacy_schedule` deprecated.
- `src/api/server.py::PlanResponse` — plan output; `extra="allow"`, so untyped fields pass but are invisible in OpenAPI.
- `src/api/server.py::PlanFailure` — `code` is a `Literal` of FM codes; this is how FM codes reach OpenAPI.
- `src/api/server.py::PlanReport` — `failures` + `failure_cause`; extra allowed.
- `src/api/server.py::PlanInputs`, `src/api/server.py::PlanTagData` — the in-memory planning bundle shared with MCP.
- `src/api/server.py::ApiErrorResponse` — documented error shape.
- `src/api/error_mapping.py::ApiContractError` — typed, code-carrying API-layer error.
- `src/api/recipe_sync.py::RecipeSyncItem` — one client recipe.

## Invariants
1. **Additive-only contract.** New fields are optional with old-behavior defaults; nothing is removed, renamed or retyped. Guard: `.claude/hooks/check_contract.py::_breaking_changes` diffs the fresh schema against the `HEAD` copy of `openapi/openapi.json` after edits under `src/api/`, `src/models/`, `src/llm/schemas.py` or `src/planning/phase10_reporting.py`.
2. **Snapshot committed and current.** Regenerate with `python3 scripts/run_export_openapi.py`. `.github/workflows/ci.yml` and `tests/test_api_v1_and_openapi.py::test_openapi_export_check_passes_when_snapshot_current` run `--check`.
3. **Error envelope.** Handlers catch exceptions and route them through `src/api/error_mapping.py::map_exception_to_api_error`. New exception types and codes are registered there with a fixed status. Guard: `tests/test_api_error_mapping.py`, `tests/test_api_plan_error_mapping.py`.
4. **Planner FM codes are HTTP 200.** They arrive in `report.failures[]`. A new FM code must be added to `PlanFailure.code`, or response validation turns the plan into a 500. The `FM_*` constants in `src/api/error_mapping.py` map an `ApiContractError` to 422, but nothing raises one today. Contract: `docs/contracts/plan-response.md`. Guard: `tests/api/test_plan_contract.py`, `tests/test_failure_explanations.py`.
5. **Success-with-warnings is not failure.** Clients branch on `plan_status`, never on `termination_code`. `success` means `result.success`, no failures and no incomplete reason; `partial` means some day has meals; anything else is `failed`. `warnings` never change `plan_status`. Enforced in `src/output/formatters.py::format_result_json`; guard: `tests/test_formatters.py`.
6. **No network during planning.** All resolution happens in `build_plan_inputs` before `plan_meals`. Guard: `tests/test_ingredient_provider_integration.py::TestNoAPICallsAfterResolveAll`.
7. **Deterministic by default; the LLM is never the authority.** Omitted `planning_mode` is deterministic regardless of env. Guard: `tests/test_planner_feature_flag_routing.py::test_api_plan_feature_flag_routes`.
8. **User-data paths go through `src/data_layer/user_data.py`.** Recipes, the tag store and batches honor `MACROVA_DATA_DIR`. Reference data (`data/reference/ingredient_nutrition.json`) and starter files are fixed paths. Pins and schedule are not covered: they live in the profile YAML at `src/data_layer/user_profile.py::DEFAULT_USER_PROFILE_PATH` (CWD-relative config/user_profile.yaml).
9. **Flutter uses `/api/v1` only.** Every path in `frontend/lib/services/api_service.dart` and `frontend/lib/features/agent/agent_api.dart` is versioned. This is convention only, with no automated guard.

## Depends on / used by
Depends on `src/planning`, `src/data_layer`, `src/providers`, `src/nutrition`, `src/ingestion`, `src/llm`, `src/models`, `src/output` and `src/config`. Used by the Flutter app over HTTP and by `src/mcp_server` in-process. See [generated/index.md](generated/index.md).

## Known gaps and traps
- Unversioned `/api/...` aliases stay for compatibility. Only tests call them. Don't add new ones.
- No in-repo client: `/api/v1/profile/schedule`, tag create/rename/alias/merge, single-recipe POST/PUT/DELETE, and `POST /api/v1/recipes/tags/generate`. The last one merges and does not wipe `tags_by_id`, but it replaces the whole entry of every recipe it tags with LLM `proposed` tags, curated slugs included. Its `llm_enabled=false` rejection raises `HTTPException`, so it returns FastAPI's `detail` body, not the envelope.
- Some request bodies accept file paths that bypass `user_data`: `PlanRequest.recipe_tags_path` and `RecipeTagGenerationRequest.recipes_path`/`recipe_tags_path`.
- Paths in `src/api/server.py`, `src/api/tag_routes.py` and `src/api/meal_prep_routes.py` resolve at import. Set `MACROVA_DATA_DIR` before importing; tests monkeypatch the module attributes. Pins and schedule resolve relative to CWD, so run from the repo root.
- OpenAPI still documents FastAPI's 422 `HTTPValidationError` on every operation, but schema errors return 400 `INVALID_REQUEST`.
- `PlanRequest.legacy_schedule` and `schedule` are deprecated and set `warnings.schedule_migration.deprecated`. Varying `schedule_days` also adds a stale "planner uses day 1 meal template only" message, even though `convert_profile` honors per-day schedules.
