# Macrova Documentation

The index for the Macrova (`nutrition-agent`) docs. For setup and running, start with [QUICK_START.md](../QUICK_START.md) and [USAGE.md](../USAGE.md) in the repo root.

## Start here

- [Getting started](../QUICK_START.md): a short run-through.
- [Usage guide](../USAGE.md): CLI options, API mode and the REST API.
- [Flutter setup](usage/flutter-setup.md)
- [Architecture map](architecture/map/README.md): the system by area, with intent, invariants, status, change recipes and generated facts. Its contents are checked against source.
- [Architecture overview](architecture/overview.md): an introduction for people new to the project.

## Reference

### Architecture

- [Architecture map](architecture/map/README.md). This is the canonical home for module structure and flow.
- [Overview](architecture/overview.md)
- [Technical design](architecture/technical-design.md)

### Planner

- [Meal plan specification v3](planner/mealplan-specification-v3.md): the authoritative planner spec.
- [Planner rules](planner/planner-rules.md): normative product rules and hard constraints.
- [Reasoning logic](planner/reasoning-logic.md)
- [Parity debugging](planner/parity-debugging.md): CLI vs Flutter debug artifacts.

### Contracts and tagging

- [PlanResponse](contracts/plan-response.md): field paths for `/plan` and `/plan-from-text`, plus `plan_status`, `PlanFailure`, meal metadata and pool filters.
- [Tag semantics contract](tagging/tag-semantics-contract.md)

### Frontend

- [Failure handling](frontend/failure-handling.md): `plan_status`, `report.failures[]` and `FailureViewModel`.
- [State invariants](frontend/state-invariants.md): provider errors, nutrition authority and agent pool filters.

### LLM

- [Roadmap](llm/roadmap.md): the integration plan and implementation status.

### Testing

- [Meal planner testing guide](testing/meal-planner-testing-guide.md)
- [Plan fixtures](testing/plan-fixtures.md): rules for `TC-*` vs `FM-*` fixtures in Flutter tests.

## For AI coding agents

- [AGENTS.md](../AGENTS.md): the always-loaded core, with commands, invariants and what must pass. `CLAUDE.md` imports it, and Cursor and Codex load it directly.
- [Architecture map](architecture/map/README.md): load the one area doc your task touches.
- Procedures: `.claude/skills/*/SKILL.md`.
- Specialist agents: `.claude/agents/*.md`.
- Cursor rules: `.cursor/rules/*.mdc`. These are one-line pointers from file globs to the matching area doc.

## Product and roadmap

- [Execution roadmap](EXECUTION_ROADMAP.md)
- [Future plans](roadmap/future-plans.md)
- [Backlog](roadmap/backlog.md)
- [Nutrition knowledge](product/nutrition-knowledge.md): product-level nutrition reasoning.
- [Product vision](product/product-vision.md)

## Sprints

- [Sprint 2](sprints/sprint2/README.md) (current): per-ticket stubs, run with the sprint-task skill.

## History

[archive/](archive/README.md) holds closed sprints (including Sprint 1), past plans and earlier agent-workflow docs. Don't trust anything there over current source, scripts or the docs above.
