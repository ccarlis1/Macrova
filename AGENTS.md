# AGENTS.md

## Project: Macrova Nutrition Agent

Macrova is a deterministic nutrition and meal-planning app with optional LLM assistance. The backend is Python/FastAPI. The frontend is Flutter. The planner must remain deterministic by default, with LLM features used only for assistance such as recipe generation, ingredient matching, natural-language config parsing, tagging, and planner feedback.

This file is the canonical instruction source for coding agents working in this repository.

---

## Canonical Commands

Use these commands from the repository root.

### Python tests

Always run backend Python tests with:

```bash
python3 scripts/run_pytest.py
```

Do not run bare `pytest`.

Do not run:

```bash
pytest
python -m pytest
python3 -m pytest
```

unless the user explicitly asks for a one-off diagnostic comparison.

The test runner is responsible for selecting the correct virtual environment and test configuration.

### OpenAPI export / contract check

Export or verify the OpenAPI snapshot with:

```bash
python3 scripts/run_export_openapi.py
python3 scripts/run_export_openapi.py --check
```

Do not run bare `python3 scripts/export_openapi.py` on the system interpreter — it imports `src.api.server`, which requires `uvicorn` and other deps from `requirements.txt`.

### Flutter commands

Run Flutter commands from the Flutter app directory, not from the repo root unless the repo structure explicitly supports it.

Common commands:

```bash
flutter pub get
flutter analyze
flutter test
```

Before changing Flutter code, inspect the existing app structure, providers, DTOs, screens, and routing. Do not create parallel state-management patterns.

---

## Python Environment Rules

The canonical virtual environment directory is:

```text
.venv/
```

Do not use:

```text
venv/
```

If documentation, scripts, comments, or setup instructions mention `venv/`, update them to `.venv/`.

The project should pin Python with a root `.python-version` file. Prefer Python `3.12` unless the repository already clearly standardizes on another supported version.

Agents must avoid creating mismatched virtual environments with whatever system Python happens to be installed.

If `.venv/pyvenv.cfg` does not match the intended interpreter version, recommend recreating `.venv/` cleanly rather than patching it manually.

Recommended clean recreation flow:

```bash
rm -rf .venv
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

If the project uses additional requirements files, install those too after inspecting the repository.

---

## Testing Rules

The canonical Python test command is:

```bash
python3 scripts/run_pytest.py
```

All docs, setup guides, agent instructions, Cursor rules, and Makefile/justfile tasks should point to this command.

A root `Makefile` or `justfile` may expose a convenience alias, but it must delegate to the canonical runner.

Example:

```make
test:
	python3 scripts/run_pytest.py
```

The test runner should be treated as the single source of truth for backend test execution.

When modifying `scripts/run_pytest.py`, preserve these goals:

1. It should be safe to run from the repository root.
2. It should use the intended virtual environment.
3. It should fail clearly when dependencies are missing.
4. It should not silently use the wrong Python interpreter.
5. It should not only check for `pytest`; it should verify that project requirements are installed or provide a clear remediation message.

---

## Documentation Consistency Rules

When updating documentation, make terminology consistent across the repo.

Required replacements:

* Use `python3 scripts/run_pytest.py` instead of bare `pytest`.
* Use `.venv/` instead of `venv/`.
* Prefer `.venv/bin/python -m pytest` only as a lower-level explanation, not as the primary command.
* The primary command shown to users and agents should remain `python3 scripts/run_pytest.py`.

Files that likely need checking:

```text
docs/MEAL_PLANNER_TESTING_GUIDE.md
FLUTTER_SETUP_README.md
README.md
AGENTS.md
CLAUDE.md
.cursor/rules/*.mdc
```

Do not blindly replace text without reading surrounding context.

---

## Cursor / Agent Rule

If `.cursor/rules/` exists, add or update a testing rule.

Recommended file:

```text
.cursor/rules/testing.mdc
```

Recommended rule:

````md
---
description: Testing commands for Macrova
globs:
  - "**/*.py"
  - "requirements*.txt"
  - "scripts/*.py"
alwaysApply: true
---

Never run bare `pytest`.

Always run backend Python tests from the repository root with:

```bash
python3 scripts/run_pytest.py
````

Use `.venv/` as the Python virtual environment directory. Do not create or document `venv/`.

````

If `.cursor/rules/` does not exist, create it only if this repository uses Cursor rules or the user explicitly requested the optional Cursor rule.

---

## Backend Architecture Rules

Backend areas may include:

```text
src/planning
src/data_layer
src/nutrition
src/ingestion
src/llm
src/api
scripts
tests
````

Before editing backend code:

1. Inspect existing models, DTOs, routes, and tests.
2. Prefer extending existing patterns over adding new parallel abstractions.
3. Preserve deterministic planner behavior.
4. Do not let LLM outputs bypass validation.
5. Do not persist generated recipes unless nutrition validation and ingredient resolution pass.
6. Do not write planner constraints in UI-only logic if they belong in backend planner contracts.

Planner priorities:

1. Meal-prep batch lock
2. Pin
3. Required tags
4. Preferred scoring

Known planner failure concepts include:

```text
FM-TAG-EMPTY
FM-BATCH-CONFLICT
FM-MACRO-INFEASIBLE
```

Preserve or improve structured failure reporting when touching planner code.

---

## Frontend Architecture Rules

The frontend is Flutter.

Known active screens include:

```text
Profile
Ingredient Hub
Recipe Builder
Recipe Library
Planner Config
Meal Plan View
Agent Pane
```

Known providers include:

```text
ProfileProvider
MealPlanProvider
RecipeProvider
IngredientProvider
RecipeBuilderCoordinator
LlmConfigProvider
```

Backend-ready features include:

```text
Planner generation
Recipe sync/list/detail
Nutrition summary
Ingredient search/resolve
Agent plan-from-text/match/generate
```

Partial or mock-only areas may include:

```text
Planner calendar view
Planner tag constraints UI
Pinned meal assignment UI
Meal-prep batching UI
Rich planner failure explanation
Advanced recipe/tag filtering
```

Do not wire incomplete backend features as if they are production-ready. Surface honest placeholder states when backend support is missing.

When redesigning the frontend:

1. Preserve existing functionality before visual polish.
2. Reuse existing providers and DTOs.
3. Avoid mock data once real backend endpoints exist.
4. Keep UI state, API DTOs, and backend contracts aligned.
5. Add loading, empty, and error states for wired endpoints.

---

## Tagging System Rules

Canonical tag data should flow through the tag repository.

Recipe-level tags should be treated as a derived projection unless the current repository code explicitly says otherwise.

Do not create another tag source of truth.

When working with tags:

1. Inspect the canonical tag registry.
2. Preserve slug normalization rules.
3. Avoid duplicate slug normalization implementations.
4. Keep required tags and preferred tags separate.
5. Required slot tags are hard constraints.
6. Preferred tags affect scoring only.

---

## LLM Feature Rules

LLM features are optional assistants, not the authority for deterministic planning.

LLM outputs must be validated before use.

Recipe generation must follow this principle:

```text
generate draft -> parse strict schema -> resolve ingredients -> recompute nutrition -> persist only if validated
```

Ingredient matching should validate against the ingredient provider.

Planner feedback should explain why planning failed and suggest targeted changes, not silently change constraints.

Natural-language config parsing should map into explicit planner config objects before planning.

---

## File Editing Rules

Make small, focused changes.

Before editing:

1. Search for existing conventions.
2. Read the relevant files.
3. Identify the narrowest change that solves the issue.

After editing:

1. Run the canonical tests where relevant.
2. Report exactly what changed.
3. Mention any files that still need manual review.
4. Do not claim success if tests were not run.

---

## Dependency Rules

Do not add new dependencies unless necessary.

Before adding a dependency:

1. Check whether the project already has an equivalent utility.
2. Explain why the dependency is needed.
3. Add it to the correct requirements file.
4. Ensure `scripts/run_pytest.py` can detect/install/validate it appropriately.

---

## Expected Agent Behavior

Agents should be conservative and repository-aware.

Do:

* Use `python3 scripts/run_pytest.py`.
* Use `.venv/`.
* Read before editing.
* Prefer existing architecture.
* Keep deterministic planner logic intact.
* Update docs when commands or setup rules change.
* Explain test results honestly.

Do not:

* Run bare `pytest`.
* Create `venv/`.
* Invent backend API contracts.
* Add duplicate frontend models/providers.
* Hide planner failures behind generic UI errors.
* Treat LLM output as trusted data.
* Make broad rewrites when targeted fixes are enough.
