# AGENTS.md

Macrova (`nutrition-agent`) is a deterministic meal planner. It has a Python/FastAPI backend (`src/`), a Flutter client (`frontend/`), a CLI (`plan_meals.py`) and an MCP server (`src/mcp_server/`). LLM features are optional helpers around the planner.

This file is the always-loaded core. Load everything else when you need it:

- **Where things are and how they work:** [docs/architecture/map/README.md](docs/architecture/map/README.md). It has one doc per area, covering purpose, flow, module status, invariants and traps.
- **Which files to touch for a common change:** [docs/architecture/map/recipes.md](docs/architecture/map/recipes.md).
- **Procedures:** `.claude/skills/*/SKILL.md`. These are plain markdown, usable from any tool:
  - api-contract
  - benchmark-audit
  - verify-stack (environment repair, parity, `FM-*` triage)
  - sprint-task
  - flutter-tester
  - engineering

## Commands

Run from the repo root.

| What | Command |
|---|---|
| Backend tests | `python3 scripts/run_pytest.py` (or `make test`). Never bare `pytest` / `python -m pytest`. |
| OpenAPI snapshot | `python3 scripts/run_export_openapi.py` to write, `--check` to verify |
| Architecture map | `python3 scripts/gen_architecture_map.py` to write, `--check` to verify |
| Planning benchmark | `.venv/bin/python evaluation/harness/run_benchmark.py`, then `compare.py`, `probes.py`, `diff_results.py --base main` in the same folder |
| Flutter | `cd frontend && flutter analyze && flutter test` |

**Environment:**

- Use `.venv/` only, never `venv/`. `scripts/run_pytest.py` creates it and installs `requirements.txt`.
- Python is 3.12 (`.python-version`); CI runs 3.11.
- Local mode needs no environment variables. USDA API mode needs `USDA_API_KEY` in `.env` (copy `.env.example`).

## What must pass

| You changed | Run |
|---|---|
| Any backend code | Backend tests |
| An API model or route, or anything Flutter sends or receives | OpenAPI write and `--check`, then update the Flutter DTOs in the same change (api-contract skill) |
| `src/planning/`, pins, batches, tags, the oracle or scenarios | The benchmark. The bar is 153/153 exact, with only timing fields changing (benchmark-audit skill). |
| `frontend/` | Flutter analyze and test |
| Code in any mapped area | Map `--check`. If the area's shape changed, update its area doc (docs-maintainer agent). |

Report results honestly. Never claim a check you didn't run.

## Invariants

These are hard constraints. Each area doc says where each one is enforced and tested.

1. **Deterministic planner.**
   - The same inputs give the same plan.
   - No unseeded randomness, wall clock or hash-order effects in `src/planning/`.
   - No network during planning; ingredients are resolved up front.
   - Precedence: batch lock → pin → required tags (hard filter) → preferred tags (scoring only).
2. **LLM is an assistant, never the authority.**
   - LLM output is schema-parsed and validated before use.
   - Nutrition numbers are always computed, never taken from the LLM.
   - Nothing is persisted unless validation and ingredient resolution both pass. Resolution is all-or-nothing, and persisted recipes carry provenance.
   - LLM errors never replace the deterministic result.
3. **Structured failures.**
   - A plan either succeeds (possibly with warnings) or fails with `FM-*` codes in `report.failures[]`. Keep the two apart and keep the codes stable.
   - Never hide a failure behind a generic error.
   - Clients branch on `plan_status` and `report.failures[]`, never on `termination_code`.
4. **Additive API contract.**
   - Request and response changes are additive.
   - `openapi/openapi.json` is committed and must pass `--check`.
   - Backend models and Flutter DTOs change together.
   - Read `src/api/` and the snapshot; never invent a contract.
5. **One tag source.**
   - `src/llm/tag_repository.py` and `tags_by_id` in the tag store are canonical.
   - `Recipe.tags` is a legacy projection. It is never a planner input or a second write path.
   - LLM tags enter as `proposed`.
6. **User data paths.**
   - User-writable stores (recipes, tags, meal-prep batches) resolve through `src/data_layer/user_data.py` (`MACROVA_DATA_DIR`). Never hard-code their paths.
   - Don't add a second write path around an existing repository.
7. **No silent nutrition.**
   - An unresolved ingredient or unknown unit drops the recipe with a warning: no zeros, no density guesses.
   - Upper limits apply per day and are never averaged.

## Working rules

- **Source beats docs.** Trust in this order: source code → scripts and tests → the architecture map → other docs → sprint and archive notes. If a doc disagrees with code, follow the code, and fix the doc or report the conflict.
- **Extend what exists.** Don't add parallel models, providers, pipelines or stores.
- **Keep changes small.** Make the narrowest change that solves the problem; avoid broad rewrites.
- **Benchmark labels are fixed.** Never edit oracle labels or scenarios to make results pass; a label that looks wrong is a question for the user.
- **Docs have one home per fact.** Update that home in the same change; the table is in `.claude/agents/docs-maintainer.md`.
- **Where sprint docs live.** `docs/sprints/` holds the current sprint's task stubs (sprint-task skill). `docs/archive/` is history and the lowest trust.
