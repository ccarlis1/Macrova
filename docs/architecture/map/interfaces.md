# Interfaces — CLI, MCP server, shared schedule contract and plan formatters

Status: implemented · Code: `src/cli.py`, `plan_meals.py`, `src/mcp_server/`, `src/models/`, `src/output/`, `src/__version__.py` · Facts: [generated/interfaces.md](generated/interfaces.md)

## Purpose
The non-HTTP ways into the deterministic planner. The CLI plans from a profile YAML plus the server-side stores; the MCP server exposes stateless, read-only planning tools to AI clients. Both share the canonical schedule contract (`src/models/`) and the plan formatters (`src/output/`) with the HTTP API, so all three report `plan_status` the same way.

## Entry points
- `plan_meals.py` → `src/cli.py::main`. Called by users from the repo root and by `tests/integration/test_cli_flutter_parity.py`.
- `src/mcp_server/__main__.py` → `src/mcp_server/server.py::main` → `src/mcp_server/server.py::build_server`. Run as `python -m src.mcp_server` (stdio for Claude clients, or `--transport http`).
- `src/mcp_server/tools.py::plan_meals`, `src/mcp_server/tools.py::analyze_recipe`: SDK-free tool logic.
- `src/models/schedule.py::DaySchedule`: imported by `src/api/server.py`, `src/data_layer/models.py`, `src/data_layer/user_profile.py`, `src/llm/schemas.py` and `src/planning/converters.py`.
- `src/output/formatters.py::format_result_json`: the API and MCP reach it through `src/api/server.py::format_plan_response`; the CLI reaches it through `src/output/formatters.py::format_result_json_string`.

## How it works
CLI (`src/cli.py::main`):
1. Reads repo-root `.env`, parses flags. Three modes: `--tag-recipes` (requires `--allow-llm-tagging`), `--llm-generate-validated` (needs `--count` and `--context-json`; `--llm-generate-and-plan` continues into planning), and planning (the default).
2. The profile loads via `src/data_layer/user_profile.py::UserProfileLoader` from `--profile`. A legacy `schedule` map is converted with a stderr notice. Pins (same YAML) and active batches come from `src/planning/orchestrator.py::hydrate_parity_plan_context`.
3. Recipes load from `--recipes` (default `src/data_layer/user_data.py::recipes_path`). `--cuisine`, `--cost-level`, `--prep-time-bucket` and `--dietary-flags` filter the pool against `--recipe-tags-path`.
4. `--ingredient-source local|api` picks the provider. `resolve_all` runs up front; a resolution failure exits with code 3.
5. Convert and plan (`--days` 1–7). `--planning-mode` follows the API: omitted means deterministic; assisted modes need the LLM enabled. ULs come from the YAML `demographic`.
6. `--output markdown|json|both`, optionally `--output-file`. Other errors exit 1.

MCP server (`src/mcp_server/server.py::build_server`):
1. **Stateless contract** (`src/mcp_server/server.py::INSTRUCTIONS`): every call carries its own targets, schedule, recipes, pins and meal prep. It never reads or writes recipes, pins, batches or the profile, builds no LLM client, and plans deterministically. An infeasible plan is a normal result with `status: "failed"`; only bad input (`src/mcp_server/tools.py::InputError`) becomes `isError`.
2. **Tools:** `macrova_plan_meals`, `macrova_analyze_recipe`, `macrova_get_sample_recipes`, `macrova_list_tags`. All annotated read-only.
3. **Plan flow:** MCP models → `schedule_days` dicts → an API `PlanRequest` (`planning_mode="deterministic"`) → `src/api/server.py::_build_user_profile` → pins and batches converted to 0-based in `src/mcp_server/indexing.py` → `src/api/server.py::build_plan_inputs`, using an in-memory `PlanTagData` built from the caller's recipe tags (registry tags only, never proposed or rejected) → the planner → `format_plan_response` → `src/mcp_server/models.py::PlanResult` plus a Markdown rendering.
4. **Ingredients** (`src/mcp_server/tools.py::build_provider`): bundled table, then `.cache/ingredients`, then USDA only when `USDA_API_KEY` is set.
5. `main` changes directory to the repo root. HTTP mode runs streamable HTTP with `stateless_http=True` on 127.0.0.1:8000 at `/mcp`.

Shared schedule: `DaySchedule` is the canonical per-day shape (1-based `day_index` and meal `index`, up to two workouts between meals). The API takes `schedule_days` or a legacy `HH:MM → int` dict; the YAML loader converts a legacy `schedule`; MCP always builds `schedule_days`. `src/models/legacy_schedule_migration.py` converts both ways and writes `warnings.schedule_migration`. `src/planning/converters.py::convert_profile` prefers `schedule_days` over the day-1 legacy dict.

## Modules
| Module | Role | Status |
|---|---|---|
| `src/cli.py` | CLI: plan, LLM tagging, LLM recipe generation | implemented |
| `plan_meals.py` | Thin script wrapper over `src/cli.py::main` | implemented |
| `src/mcp_server/server.py` | Tool registration, descriptions, transports | implemented |
| `src/mcp_server/tools.py` | Tool logic over API helpers | implemented |
| `src/mcp_server/models.py` | Tool input/output models (`extra="forbid"` inputs) | implemented |
| `src/mcp_server/indexing.py` | The only 1-based ↔ 0-based conversion | implemented |
| `src/mcp_server/nutrients.py` | Plain nutrient names; RDI/UL re-exports | implemented |
| `src/models/schedule.py` | Canonical `DaySchedule`/`MealSlot`/`WorkoutSlot` | implemented |
| `src/models/legacy_schedule_migration.py` | Legacy dict ↔ canonical; deprecation warnings | implemented |
| `src/output/formatters.py` | Plan result → JSON / Markdown; derives `plan_status` | implemented |
| `src/__version__.py` | Package version string | implemented |

## Key types
- `src/models/schedule.py::DaySchedule`: one day's meals and workouts.
- `src/models/schedule.py::MealSlot`: busyness 1–4, optional `required_tag_slugs` and `preferred_tag_slugs`.
- `src/models/schedule.py::WorkoutSlot`: `after_meal_index` gap, type, intensity.
- `src/mcp_server/models.py::Targets`: calories, macros, demographic, micronutrient goals.
- `src/mcp_server/models.py::Schedule`: shorthand or full per-day schedule.
- `src/mcp_server/models.py::PlanResult`: the `structuredContent` of `macrova_plan_meals`.
- `src/mcp_server/tools.py::InputError`: bad tool input, surfaced as `isError`.

## Invariants
1. **MCP is stateless, read-only and deterministic.** Enforced in `src/mcp_server/tools.py::plan_meals`. Guarded by `tests/mcp_server/test_server.py::test_no_llm_client_is_built` and `tests/mcp_server/test_server.py::test_lists_four_read_only_tools_with_output_schemas`.
2. **Only `src/mcp_server/indexing.py` adds or subtracts 1.** Guarded by `tests/mcp_server/test_indexing.py`.
3. **Schedule shape** (meals 1..N, ≤ 2 workouts in valid, unique gaps). Enforced by `src/models/schedule.py::validate_day_schedule`. Guarded by `tests/test_schedule_contract.py` and `tests/test_legacy_schedule_migration.py`.
4. **The CLI defaults to deterministic planning.** Guarded by `tests/test_planner_feature_flag_routing.py::test_cli_feature_flag_routes_to_plan_meals_when_disabled`.
5. **One `plan_status` derivation**, `src/output/formatters.py::format_result_json`, for all three interfaces. Guarded by `tests/test_formatters.py`.

## Depends on / used by
CLI and MCP depend on `src/planning`, `src/data_layer`, `src/providers`, `src/output`; MCP also imports `src/api/server.py`. `src/models` is used by `src/api`, `src/data_layer`, `src/llm`, `src/planning`, and itself reads `src/data_layer/user_data.py` and `src/llm/tag_repository.py`. See [generated/index.md](generated/index.md).

## Known gaps and traps
- The CLI is not the API. It never attaches canonical or hard-eligible tag slugs to the pool, so YAML `required_tag_slugs` and `preferred_tag_slugs` have nothing to match. Its JSON also lacks failure explanations, filter/exclusion/nutrition warnings and meal `source` metadata; the parity test does not cover tags.
- `src/cli.py::DEFAULT_TAG_PATH` is computed before `.env` is read. If `MACROVA_DATA_DIR` is set only in `.env`, the CLI reads recipes from the data folder but tags from the repo path.
- Importing `src/api/server.py` loads `.env`, so a `USDA_API_KEY` there enables live USDA lookups in MCP. MCP's HTTP port 8000 collides with the API's.
- MCP does read one user file: `MealSlot` slug validation resolves against `NUTRITION_TAG_REPO_PATH` or `src/data_layer/user_data.py::recipe_tags_path`.
- `src/__version__.py` feeds neither the FastAPI app nor packaging; only `tests/test_version.py` reads it.
