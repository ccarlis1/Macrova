# Architecture map

The map of the Macrova codebase, written for an agent arriving with a task. Read this page, open the one area doc your task touches, and drill into `generated/` only for exact facts. Source code wins over anything here. If you find a conflict, fix the map in the same change.

## How the system fits together

1. **Clients:** the Flutter app (`frontend/lib/`), the CLI (`plan_meals.py`) and the MCP server (`src/mcp_server/`). Flutter only talks to `/api/v1` on the FastAPI app in `src/api/server.py`.
2. **Inputs, before planning:** load the profile and the recipe pool, apply pool tag filters, then resolve every ingredient through a provider: local JSON, or USDA in API mode. Recipes that can't be resolved are dropped with a warning. After this step there are no network calls.
3. **Plan:** `src/planning/planner.py::plan_meals` runs a deterministic, phase-based backtracking search. It returns `src/planning/phase10_reporting.py::MealPlanResult`, which is either a plan or a structured `FM-*` failure.
4. **Optional LLM:** `src/planning/orchestrator.py::plan_with_llm_feedback` diagnoses a failure, asks for recipes that fill the gap, validates them, and plans again. The LLM is never the authority, and nothing is persisted unless the retried plan succeeds.
5. **Output:** `src/output/formatters.py::format_result_json` builds `PlanResponse`, whose `plan_status` and `report.failures[]` the clients branch on.

## Areas

| Area | Covers | Status | Read | Facts |
|---|---|---|---|---|
| Planning | `src/planning/` | implemented. Tie-break cascade is partial; carb scaling is dormant | [planning.md](planning.md) | [generated](generated/planning.md) |
| API | `src/api/`, the OpenAPI snapshot | implemented | [api.md](api.md) | [generated](generated/api.md), [routes](generated/routes.md) |
| Data | `src/data_layer/`, `src/nutrition/`, `src/ingestion/`, `src/providers/`, `data/` | implemented | [data.md](data.md) | [generated](generated/data.md) |
| LLM and tags | `src/llm/`, `src/config/` | implemented. Assisted FDC disambiguation is experimental and unwired | [llm.md](llm.md) | [generated](generated/llm.md) |
| Interfaces | CLI, MCP server, `src/models/`, `src/output/` | implemented | [interfaces.md](interfaces.md) | [generated](generated/interfaces.md) |
| Frontend | `frontend/lib/` | implemented, with the partial areas listed in its doc | [frontend.md](frontend.md) | [generated](generated/frontend.md) |
| Tooling | `tests/`, `evaluation/`, `scripts/`, `.claude/hooks/`, CI | implemented | [tooling.md](tooling.md) | [generated](generated/tooling.md) |

Also in `generated/`: [index](generated/index.md) (areas and the package dependency graph) and [entities](generated/entities.md) (dataclasses, pydantic models, enums, with field names).

Every area doc has the same sections: Purpose, Entry points, How it works, Modules (with status), Key types, Invariants (each with where it's enforced and what guards it), Depends on / used by, and Known gaps and traps.

## To change X

[recipes.md](recipes.md) lists the files to touch, in order, and the checks to run for:

- adding a planner hard constraint
- adding a plan API field end to end
- adding a tag type
- changing the LLM pipeline
- adding an `FM-*` failure mode
- adding a benchmark scenario
- adding a user-writable data store

Procedures (how to run and judge the checks) live in the skills under `.claude/skills/`: api-contract, benchmark-audit, verify-stack and sprint-task.

## Area → checks and reviewers

| Task touches | Must pass | Specialist agent (`.claude/agents/`) |
|---|---|---|
| `src/planning/`, pins, batches, tags, oracle, scenarios | `python3 scripts/run_pytest.py`, then the benchmark (benchmark-audit skill) | planner-invariant-reviewer |
| `src/api/`, any field Flutter sends or receives | `python3 scripts/run_pytest.py`, `python3 scripts/run_export_openapi.py --check` | backend-contract-auditor |
| `src/llm/`, tagging | `python3 scripts/run_pytest.py` | planner-invariant-reviewer if planning or tags are affected |
| `src/data_layer/`, `src/nutrition/`, `src/ingestion/`, `src/providers/` | `python3 scripts/run_pytest.py`, plus the benchmark if planning inputs change | test-coverage-agent |
| `frontend/` | `cd frontend && flutter analyze && flutter test` | flutter-wiring-agent |
| anything mapped (all of the above) | `python3 scripts/gen_architecture_map.py --check` | docs-maintainer |

For multi-area work, the task-router agent picks the minimum set.

## Keeping the map current

- **`generated/` is never edited by hand.**
  - Run `python3 scripts/gen_architecture_map.py` (or `make map`) after changing code. It uses only the standard library and takes under a second.
  - `--check` fails when the generated files are stale, when a `src/` or `frontend/lib/` file belongs to no area, or when a backticked reference in these hand-written docs doesn't resolve to a real file or symbol.
  - CI and the Claude Code Stop hook both run `--check`.
- **Write references so the checker can verify them.** In the hand-written docs, refer to code as `path` or `path::symbol` (or `path::Class.method`). Renaming or deleting code then breaks the check instead of leaving a stale doc.
- **Review the area doc when the shape of an area changes.** That means a file added or removed, or a route, entity or public name changed.
  - `python3 scripts/gen_architecture_map.py --stale-intent --base main` lists the area docs to review.
  - It is advisory: it runs on pull requests in CI and is printed by the Stop hook.
  - Update the doc when intent, flow, invariants or status changed. Otherwise leave it.
- **Where the content goes.**
  - Area docs hold intent and invariants only. File lists and imports belong to the generator.
  - Keep each area doc under about 1,400 words.
  - The docs-maintainer agent owns upkeep (`.claude/agents/docs-maintainer.md`).
