# AGENTS.md

Canonical instruction source for AI coding agents working in the **Macrova** (`nutrition-agent`) repository. Read this before making changes. It is intended to be useful every session, not a sprint log.

---

## Project Overview

Macrova is a deterministic nutrition and meal-planning system with optional LLM assistance.

- **Backend:** Python / FastAPI (`src/`). Core is a deterministic, phase-based meal planner with backtracking search, rule-based recipe scoring, and structured macro + micronutrient nutrition calculations.
- **Frontend:** Flutter app (`frontend/`) using `provider` for state management.
- **Interfaces:** CLI (`plan_meals.py` / `python3 -m src.cli`) and an optional REST API (`src/api/server.py`).
- **Core principle:** The planner is deterministic by default. LLM features are optional assistants (recipe generation, ingredient matching, natural-language config parsing, tagging, planner feedback) and must never bypass validation or become the authority for planning.

Ingredient nutrition comes from a provider abstraction: a local JSON database (default) or the USDA FoodData Central API (`--ingredient-source api`, requires `USDA_API_KEY`). No network/API calls happen during planning — ingredient resolution is completed up front.

---

## How to Use This File

1. Read this file first.
2. Before editing a system (backend, planner, LLM, tagging, frontend), read the relevant source and the deeper docs noted in **When to Read Deeper Docs**.
3. Prefer extending existing patterns over adding parallel abstractions.
4. Run the canonical tests after substantive backend changes and report results honestly.
5. If a doc conflicts with current code/scripts, trust code/scripts and report the conflict — do not guess.

---

## Source of Truth Hierarchy

When information conflicts, prefer sources in this order:

1. **Current source code** (`src/`, `frontend/lib/`)
2. **Current scripts and tests** (`scripts/`, `tests/`, `Makefile`, `pytest.ini`)
3. **`.cursor/architecture.json`** (machine-readable map of entities, features, APIs, UI, and known unknowns)
4. **Current docs** (`docs/`, `README.md`, `USAGE.md`, `QUICK_START.md`)
5. **Existing agent instructions** (this file)
6. **Historical notes / sprint docs / code comments** (`docs/sprints/`, `docs/archive/sprint-notes/`, older prose)

If docs conflict with code/scripts, do not invent behavior. Preserve working behavior, follow the source/scripts, and report the conflict in your summary. Several older docs are known to be stale (see **Documentation Rules**).

---

## Canonical Commands

Run all commands from the repository root unless noted.

### Backend Tests

```bash
python3 scripts/run_pytest.py
```

Do **not** run bare `pytest`, `python -m pytest`, or `python3 -m pytest` (except for an explicit one-off diagnostic the user requests). `scripts/run_pytest.py` ensures `.venv` exists, installs/validates `requirements.txt`, and runs `python -m pytest` inside that venv. `pytest.ini` sets `pythonpath = .` and `testpaths = tests`.

`make test` is a convenience alias and must delegate to `python3 scripts/run_pytest.py`.

### OpenAPI Export

The snapshot lives at `openapi/openapi.json`. `scripts/export_openapi.py` imports `src.api.server.app`, which requires FastAPI/uvicorn and other deps from `requirements.txt`.

Use the wrapper (canonical), which runs the export inside `.venv`:

```bash
python3 scripts/run_export_openapi.py            # export/write openapi/openapi.json
python3 scripts/run_export_openapi.py --check    # fail if the snapshot is stale
```

`make openapi` and `make openapi-check` delegate to the wrapper.

Do **not** run bare `python3 scripts/export_openapi.py` on the system interpreter unless it already has all deps installed. If you must call the export script directly, use `.venv/bin/python scripts/export_openapi.py`. The script itself prints this remediation when deps are missing.

### Frontend Commands

Run from the Flutter app directory (`frontend/`), not the repo root:

```bash
cd frontend
flutter pub get
flutter analyze
flutter test
```

Inspect existing providers, DTOs, screens, and routing before changing Flutter code. Do not create parallel state-management patterns.

---

## Python Environment Rules

- Canonical virtualenv directory: **`.venv/`**. Do not use or document `venv/`.
- Python is pinned by `.python-version` to **3.12**. Prefer 3.12.
- If `.venv/pyvenv.cfg` does not match the intended interpreter, recommend recreating `.venv/` cleanly rather than patching it.

Clean recreation flow:

```bash
rm -rf .venv
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

`scripts/_venv.py` is the shared helper for the script runners; it auto-creates `.venv` and installs `requirements.txt` on demand. Treat `scripts/run_pytest.py` as the single source of truth for backend test execution.

---

## Repository Map

### Backend (`src/`)

- `src/api/` — FastAPI app. `server.py` is the main app (routes, request/response models). `recipe_sync.py`, `tag_routes.py`, `meal_prep_routes.py` are routers included under `/api/v1`. `error_mapping.py` maps exceptions to structured API errors.
- `src/planning/` — Deterministic planner. Phase-based pipeline `phase0_models.py` … `phase7_search.py` plus `phase9_carb_scaling.py` and `phase10_reporting.py`. Public API is `planner.py` (`plan_meals`). `orchestrator.py` wraps planning with optional LLM feedback (`plan_with_llm_feedback`). `converters.py` bridges data-layer models into planning models.
- `src/data_layer/` — Domain models (`models.py`), recipe/ingredient/nutrition DBs, `user_profile.py`, `meal_prep.py` (meal-prep batch repository), `upper_limits.py`.
- `src/nutrition/` — `calculator.py`, `aggregator.py` (macro/micro computation and aggregation).
- `src/scoring/` — Rule-based `recipe_scorer.py`.
- `src/ingestion/` — Ingredient parsing/normalization, USDA client, ingredient cache, nutrient mapping, nutrition profile building.
- `src/providers/` — Ingredient data providers: `local_provider.py`, `api_provider.py`, `summary_hybrid_provider.py` (behind `ingredient_provider.py` abstraction).
- `src/llm/` — Optional LLM assistance: `client.py`, `pipeline.py` (generate → validate → persist), `recipe_generator.py`, `recipe_validator.py`, `recipe_tagger.py`, `tag_repository.py`, `tag_filter.py`, `tag_filtering_service.py`, `ingredient_matcher.py`, `constraint_parser.py` (NL config), `schemas.py`.
- `src/models/` — Schedule models and legacy schedule migration.
- `src/output/` — `formatters.py` (Markdown/JSON output, `format_result_json`).
- `src/config/` — `llm_settings.py`.

### Frontend (`frontend/lib/`)

- `main.dart` — Boot/wiring. `widgets/app_shell.dart` — sidebar nav + `IndexedStack` of screens.
- `screens/` — Profile, Ingredient Hub, Recipe Builder, Recipe Library, Planner Config, Meal Plan View.
- `features/agent/` — Agent pane, setup, API, models, and `LlmConfigProvider`.
- `providers/` — `ProfileProvider`, `MealPlanProvider`, `RecipeProvider`, `IngredientProvider`, `RecipeBuilderCoordinator` (`LlmConfigProvider` lives under `features/agent/`).
- `models/`, `services/` (`api_service.dart`, `storage_service.dart`), `widgets/`.

### Tests (`tests/`)

Pytest suite, no network required (USDA-dependent tests use mocks). Includes per-phase planner tests, API/contract tests (`tests/api/`, `tests/test_api_v1_and_openapi.py`), integration tests (`tests/integration/`), and `tests/conftest.py`.

### Scripts (`scripts/`)

`run_pytest.py`, `run_export_openapi.py`, `export_openapi.py`, `_venv.py`, plus migration/benchmark/export utilities (`migrate_recipes_tags.py`, `migrate_recipes_time_tags.py`, `benchmark_meal_plan_search.py`, `export_planner_debug_artifacts.py`, `load_ingredients_by_id.py`, `export_flutter_cached_ingredients_bundle.py`).

### Documentation (`docs/`)

See `docs/README.md` for the full index. Key areas: `docs/architecture/`, `docs/planner/`, `docs/tagging/`, `docs/llm/`, `docs/testing/`, `docs/product/`, `docs/roadmap/`, `docs/sprints/` (per-sprint task stubs), and `docs/archive/sprint-notes/` (historical sprint plans).

---

## Backend Architecture Rules

Before editing backend code:

1. Inspect existing models, DTOs, routes, and tests.
2. Prefer extending existing patterns over adding parallel abstractions.
3. Preserve deterministic planner behavior.
4. Do not let LLM outputs bypass validation.
5. Do not persist generated recipes unless nutrition validation and ingredient resolution pass.
6. Keep planner constraints in backend planner contracts, not in UI-only logic.
7. Keep API request/response models, the OpenAPI snapshot, and frontend DTOs aligned. After changing API shapes, re-run `python3 scripts/run_export_openapi.py` and the contract tests.

---

## Planner Rules and Invariants

- The planner is **deterministic by default**: deterministic backtracking search over `(day, slot)` assignments, with stable ordering and tie-breaking. Do not introduce nondeterminism into the default path.
- No API/network calls occur during planning. Ingredient resolution (`extract_ingredient_names` → `provider.resolve_all`) happens up front, then `convert_profile` / `convert_recipes` build planning models.
- Single result type: `MealPlanResult` (in `phase10_reporting.py`) carries `success`, `termination_code`, `plan`, trackers, warnings, and `report`. Success-with-warnings (`termination_code="OK"` + `report.warnings`) is distinct from a failure the user must act on — keep these separate.
- Constraint precedence (highest first): **meal-prep batch lock → pin → required tags → preferred scoring**. `planner.py` normalizes batch locks into pinned assignments before search.
- Preserve structured failure reporting. Known failure codes include `FM-1`…`FM-5` and the user-actionable modes `FM-TAG-EMPTY`, `FM-BATCH-CONFLICT`, `FM-MACRO-INFEASIBLE`, each with a stable `fix_hint`. Codes are registered in `src/api/error_mapping.py` and surfaced in OpenAPI schemas. Do not hide planner failures behind generic UI errors.
- Multi-day horizon is 1–7 days; weekly trackers and micronutrient deficit carryover apply when days > 1. Daily upper limits (ULs) are enforced per-day, never averaged.

When touching planner code, read `docs/planner/mealplan-specification.md`, `docs/planner/parity-debugging.md`, and the relevant `phaseN_*.py` file(s).

---

## LLM Feature Rules

LLM features are optional assistants, not the authority for deterministic planning. LLM outputs must be validated before use.

Recipe generation must follow:

```text
generate draft -> parse strict schema -> resolve ingredients -> recompute nutrition -> persist only if validated
```

This is implemented by `src/llm/pipeline.py` (`generate_validate_persist_recipes`): it asserts a USDA-capable provider, generates drafts, validates against provider-backed checks, and only persists accepted recipes.

- Ingredient matching validates against the ingredient provider.
- Natural-language config parsing (`constraint_parser.py`) must map text into explicit planner config objects before planning.
- Planner feedback should explain why planning failed and suggest targeted changes, not silently mutate constraints.
- The frontend gates LLM/assisted planning modes behind an LLM-ready check; assisted modes fall back to deterministic when the gate is not ready.

---

## Tagging Rules

There is one canonical tag source of truth. Do not create another.

- `src/llm/tag_repository.py` is the runtime source for tag storage, slug normalization, alias resolution, and merge behavior.
- `recipe_tags.json` (default path `data/recipes/recipe_tags.json`, referenced by `DEFAULT_TAG_PATH` in `server.py`) is the canonical seed/registry shape; `tags_by_id` is the canonical per-recipe planner/filtering tag source.
- `Recipe.tags` in `recipes.json` is a **legacy compatibility projection only** — never use it for hard-filter/planner decisions, and do not turn it into a second write path.
- Keep required tags (hard constraints) and preferred tags (scoring only) separate. Preserve slug normalization rules; do not duplicate slug-normalization logic.
- All LLM-produced tags enter as `proposed`, pass strict schema validation first, then semantic eligibility gating; only `approved` (or non-LLM user/system) tags may act as hard constraints. See `docs/tagging/tag-semantics-contract.md` for the canonical semantic-class table and lifecycle.

---

## Data and Persistence Rules

- Recipe/ingredient data are not committed; copy from `*.example` files (`config/user_profile.yaml.example`, `data/recipes/recipes.json.example`, `data/ingredients/custom_ingredients.json.example`).
- Ingredient nutrition flows through the provider abstraction into internal `NutritionProfile` / `MicronutrientProfile` objects.
- Upper-limit reference data lives under `data/reference/` and is enforced per-day.
- Do not persist generated recipes unless nutrition validation and ingredient resolution pass.
- Treat the recipe/tag/meal-prep file stores as backed by their repositories (`recipe_db.py`, `tag_repository.py`, `meal_prep.py`); do not add duplicate write paths around them.
- Environment: none required for local mode. For USDA API mode, copy `.env.example` to `.env` and set `USDA_API_KEY`. The CLI and `server.py` both load repo-root `.env`.

---

## API and OpenAPI Rules

- The FastAPI app is `src/api/server.py`; routes are served under `/api/v1` (plan, plan-from-text, recipes CRUD/sync, recipe generation/tagging, ingredient search/resolve/match, nutrition summary, LLM status), plus tag and meal-prep routers.
- `openapi/openapi.json` is a committed snapshot. After changing any API model or route, regenerate it with `python3 scripts/run_export_openapi.py` and verify with `--check`; keep contract tests passing.
- Do not invent API contracts. Confirm request/response shapes from `server.py` and the corresponding Pydantic models / `recipe_sync.py`.

---

## Frontend Architecture Rules

Screens: Profile, Ingredient Hub, Recipe Builder, Recipe Library, Planner Config, Meal Plan View, Agent Pane (+ Agent Setup). Providers: `ProfileProvider`, `MealPlanProvider`, `RecipeProvider`, `IngredientProvider`, `RecipeBuilderCoordinator`, `LlmConfigProvider`.

When working on the frontend:

1. Preserve existing functionality before visual polish.
2. Reuse existing providers and DTOs; do not add duplicate models/providers.
3. Avoid mock data once real backend endpoints exist; surface honest placeholder/loading/empty/error states where backend support is missing.
4. Keep UI state, API DTOs, and backend contracts aligned.
5. Do not wire incomplete backend features as production-ready (see **Known Partial or Mock Areas**).

---

## Testing Rules

- Canonical command: `python3 scripts/run_pytest.py` (from repo root). Never run bare `pytest`.
- The runner selects the correct `.venv` and validates dependencies; fail clearly if deps are missing.
- Tests require no network; USDA-dependent paths use mocks.
- For frontend, use `flutter test` from `frontend/`.
- Report test results honestly. Do not claim success if tests were not run.

When modifying `scripts/run_pytest.py`, preserve: safe to run from repo root; uses the intended `.venv`; fails clearly when deps are missing; never silently uses the wrong interpreter; verifies project requirements (not just that `pytest` exists).

---

## Documentation Rules

When updating docs, keep terminology consistent across the repo:

- Use `python3 scripts/run_pytest.py` instead of bare `pytest`.
- Use `.venv/` instead of `venv/`.
- `.venv/bin/python -m pytest` is a lower-level explanation only, not the primary command.

Read surrounding context before replacing text. Some archived docs may be stale relative to source:

- `docs/architecture/directory-structure.md` is refreshed against `src/` but may drift; trust source when in doubt.
- Historical sprint stubs under `docs/sprints/` and plans under `docs/archive/sprint-notes/` may reference old paths or completed work.

There is a thin root `CLAUDE.md` that points to this file; do not duplicate rules there.

---

## Cursor / Agent Rules

- `.cursor/architecture.json` is the machine-readable architecture map (entities, features, APIs, UI components, and an `unknowns` list). Inspect it before broad backend/frontend/planner/API changes, but treat it as **below source code** in the hierarchy — parts of its `unknowns`/`missing` notes are now stale (see **Known Partial or Mock Areas**).
- `.cursor/rules/` holds operational rules (`testing.mdc`, `backend.mdc`, `frontend.mdc`) derived from this file.

---

## Safe Editing Workflow

Before editing:

1. Search for existing conventions and read the relevant files.
2. Consult `.cursor/architecture.json` and the deeper doc(s) for the system you are touching.
3. Identify the narrowest change that solves the problem.

After editing:

1. Run the canonical tests where relevant (`python3 scripts/run_pytest.py`; `flutter test` for frontend).
2. If you changed API shapes, regenerate/check OpenAPI.
3. Check linter/analyzer output and fix issues you introduced.
4. Report exactly what changed, what you ran, and any files needing manual review.
5. Make small, focused changes. Avoid broad rewrites when targeted fixes suffice.

---

## Known Partial or Mock Areas

Verify current status against source before treating any of these as production-ready:

- **Meal-plan calendar view** — UI has a calendar toggle that renders a placeholder (`meal_plan_view_screen.dart`).
- **Ingredient Hub "add to recipe"** — currently shows a snackbar instructing the user to use Recipe Builder (`ingredient_hub_screen.dart`).
- **Frontend `PlanRequest` tag fields** — `frontend/lib/models/models.dart` may not carry all backend tag-filter fields present in `server.py`'s `PlanRequest`; confirm before relying on end-to-end tag filtering from the UI.
- **`MealPrepReference` / meal-prep batching** — marked `partial` in architecture.json. NOTE: meal-prep is further along in source than the architecture.json `unknowns` claim — `src/data_layer/meal_prep.py` and `src/api/meal_prep_routes.py` now exist and the router is wired into `server.py`. Trust the source; treat the architecture.json "missing meal-prep" notes as stale and verify behavior directly.

---

## When to Read Deeper Docs

- **Planner / search / failure modes:** `docs/planner/mealplan-specification.md`, `docs/planner/parity-debugging.md`, `docs/planner/planner-rules.md`, `src/planning/phaseN_*.py`, `src/planning/planner.py`.
- **Overall architecture / data flow:** `docs/architecture/overview.md`, `docs/architecture/technical-design.md`, `docs/planner/planner-rules.md`, and `.cursor/architecture.json`.
- **Tagging:** `docs/tagging/tag-semantics-contract.md`, `src/llm/tag_repository.py`, `src/llm/tag_filtering_service.py`.
- **LLM features / roadmap:** `docs/llm/roadmap.md`, `src/llm/pipeline.py`.
- **API contracts:** `src/api/server.py`, `openapi/openapi.json`, `tests/api/`.
- **Frontend:** `frontend/lib/main.dart`, `frontend/lib/widgets/app_shell.dart`, `docs/usage/flutter-setup.md`.
- **Per-feature history (use cautiously, lowest priority):** `docs/sprints/`, `docs/archive/sprint-notes/`.

Always inspect the relevant `architecture.json` entries and the deeper doc before broad changes; reconcile any conflict in favor of current source and report it.

---

## Agent Do / Do Not Checklist

**Do**

- Use `python3 scripts/run_pytest.py` and `.venv/`.
- Read source and the relevant deeper docs before editing.
- Preserve deterministic planner behavior and structured failure reporting.
- Validate LLM output before persistence; keep one canonical tag source.
- Reuse existing providers, DTOs, screens, models.
- Regenerate/check OpenAPI after API changes.
- Update docs when commands or setup rules change; report stale docs.
- Report test results and conflicts honestly.

**Do Not**

- Run bare `pytest`, `python -m pytest`, or `python3 -m pytest` (except an explicit one-off diagnostic).
- Create or document `venv/`.
- Run `python3 scripts/export_openapi.py` on the bare system interpreter.
- Invent backend API contracts or planner behavior.
- Add duplicate frontend models/providers or a second tag/recipe write path.
- Let LLM output bypass validation or drive deterministic planning.
- Hide planner failures behind generic UI errors.
- Make broad rewrites when targeted fixes are enough.
