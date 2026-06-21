# Agent Strategy

How AI coding agents should work in this repository.

## Canonical instruction file

**[AGENTS.md](../../AGENTS.md)** at the repo root is the single source of truth for agent behavior: canonical commands, environment rules, source-of-truth hierarchy, planner/LLM/tagging invariants, and a "When to Read Deeper Docs" map.

Optional thin pointer: **[CLAUDE.md](../../CLAUDE.md)** → AGENTS.md (no duplicated rules).

## Cursor rules

Operational rules live in [`.cursor/rules/`](../../.cursor/rules/):

- `testing.mdc` — pytest runner, `.venv/` only
- `backend.mdc` — deterministic planner, LLM validation, OpenAPI
- `frontend.mdc` — providers/DTOs, honest UI states

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

## Subagents (future)

`.claude/agents/` subagent definitions (backend-contract-auditor, flutter-wiring-agent, planner-reviewer, docs-maintainer) are not yet in the repo. When added, they complement — not replace — AGENTS.md.
