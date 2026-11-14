# Macrova Documentation

Navigation hub for the Macrova (`nutrition-agent`) repository. For quick setup, see root [QUICK_START.md](../QUICK_START.md) and [USAGE.md](../USAGE.md).

## Start Here

- [Getting started](../QUICK_START.md) — short run-through
- [Usage guide](../USAGE.md) — CLI options, API mode, REST API
- [Flutter setup](usage/flutter-setup.md)
- [Architecture overview](architecture/overview.md)
- [Meal planner testing guide](testing/meal-planner-testing-guide.md)
- [Current roadmap](roadmap/next-steps.md)

## For Developers

### Architecture

- [Overview](architecture/overview.md)
- [Technical design](architecture/technical-design.md)
- [Directory structure](architecture/directory-structure.md) — module map (refresh against `src/` when in doubt)

### Planner

- [Meal plan specification](planner/mealplan-specification.md) — authoritative planner spec (v3)
- [Planner rules](planner/planner-rules.md) — normative product rules and hard constraints
- [Reasoning logic](planner/reasoning-logic.md)
- [Parity debugging](planner/parity-debugging.md) — CLI vs Flutter debug artifacts

### Tagging

- [Tag semantics contract](tagging/tag-semantics-contract.md)

### Contracts

- [PlanResponse](contracts/plan-response.md) — `/plan` and `/plan-from-text` field paths, `plan_status`, `PlanFailure`, meal metadata, pool filters

### Frontend

- [Failure handling](frontend/failure-handling.md) — `plan_status`, `report.failures[]`, `FailureViewModel`
- [State invariants](frontend/state-invariants.md) — provider errors, nutrition authority, agent pool filters

### LLM

- [Roadmap](llm/roadmap.md) — integration plan and implementation status

### Testing

- [Meal planner testing guide](testing/meal-planner-testing-guide.md)
- [Plan fixtures](testing/plan-fixtures.md) — `TC-*` vs `FM-*` fixture rules for Flutter tests

## For AI Coding Agents

- [AGENTS.md](../AGENTS.md) — canonical agent instructions (repo root)
- [Agent strategy](agents/README.md)
- [Task router](agents/task-router.md) — classify tasks before implementation
- [Subagent guide](agents/subagent-guide.md) — specialist roles and when to use them
- [Evaluation log](agents/evaluation-log.md) — agent-rule change log
- [Benchmarks](agents/benchmarks/) — repeatable agent behavior checks
- [Cursor rules](../.cursor/rules/) — operational rules derived from AGENTS.md
- Machine-readable map: [`.cursor/architecture.json`](../.cursor/architecture.json)

## Product and Roadmap

- [Nutrition knowledge](product/nutrition-knowledge.md) — product-level nutrition reasoning
- [Product vision](product/product-vision.md)
- [Tinyfish use case](product/tinyfish-usecase.md)
- [Next steps](roadmap/next-steps.md)
- [Backlog](roadmap/backlog.md)
- [Open questions](roadmap/open-questions.md)

## Sprints

- [Sprint 1 task index](sprints/sprint1/README.md) — per-ticket stubs (plan: [archive/sprint-notes/sprint-1.md](archive/sprint-notes/sprint-1.md))

## Historical / Archived

See [archive/README.md](archive/README.md). Archived sprint plans, implementation plans, and derived summaries live there — **do not trust over current source code, scripts, or canonical docs above**.
