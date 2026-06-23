# Agent Strategy

How AI coding agents should work in this repository.

## Canonical instruction file

**[AGENTS.md](../../AGENTS.md)** at the repo root is the single source of truth for agent behavior: canonical commands, environment rules, source-of-truth hierarchy, planner/LLM/tagging invariants, and a "When to Read Deeper Docs" map.

Optional thin pointer: **[CLAUDE.md](../../CLAUDE.md)** → AGENTS.md (no duplicated rules).

## Cursor rules

Operational rules live in [`.cursor/rules/`](../../.cursor/rules/):

- `global.mdc` — always-on: `.venv/`, canonical test/OpenAPI commands, AGENTS.md pointer
- `testing.mdc` — pytest runner, `.venv/` only
- `planner.mdc` — deterministic planner, tag/pin/batch invariants, failure modes
- `backend.mdc` — LLM validation, tag source, OpenAPI
- `frontend.mdc` — providers/DTOs, honest UI states
- `docs-maintenance.mdc` — when to update docs, final Docs note

## Specialized subagents

Short definitions in [`.claude/agents/`](../../.claude/agents/):

| Agent | Role |
|-------|------|
| `task-router` | Classify tasks before implementation |
| `backend-contract-auditor` | Verify real API/DTO/OpenAPI contracts |
| `planner-invariant-reviewer` | Guard planner determinism and failure reporting |
| `flutter-wiring-agent` | Safe Flutter-to-backend wiring |
| `docs-maintainer` | Nearest-canonical doc updates |
| `test-coverage-agent` | Canonical tests, honest reporting |

Detail: [subagent-guide.md](subagent-guide.md). Routing: [task-router.md](task-router.md).

## Agent workflow docs

- [Task router](task-router.md) — domain → specialists, docs, validation
- [Subagent guide](subagent-guide.md) — when to call each specialist
- [Evaluation log](evaluation-log.md) — log of agent-rule changes
- [Benchmarks](benchmarks/) — repeatable behavior checks

## Machine-readable map

[`.cursor/architecture.json`](../../.cursor/architecture.json) lists entities, features, APIs, and UI components. Treat it as **below source code** in the hierarchy; some `unknowns` notes may be stale.

## Deeper docs by domain

| Domain | Canonical doc |
|--------|---------------|
| Planner algorithm | [mealplan-specification.md](../planner/mealplan-specification.md) |
| Planner rules | [planner-rules.md](../planner/planner-rules.md) |
| Tagging | [tag-semantics-contract.md](../tagging/tag-semantics-contract.md) |
| Nutrition/product logic | [nutrition-knowledge.md](../product/nutrition-knowledge.md) |
| LLM status | [roadmap.md](../llm/roadmap.md) + `src/llm/` |

Subagents complement — not replace — AGENTS.md.
