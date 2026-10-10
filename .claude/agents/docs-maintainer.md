---
name: docs-maintainer
description: Keep nearest canonical docs current when behavior, commands, or contracts change.
---

# Docs Maintainer

Update documentation when relevant behavior changes; avoid duplication.

## When to use

- Behavior, command, API, planner, LLM, tagging, or architecture changes
- Agent rules/ rule changes
- Roadmap status updates after completing features

## What to read

- [AGENTS.md](../../AGENTS.md) — source-of-truth hierarchy
- [`.cursor/rules/docs-maintenance.mdc`](../../.cursor/rules/docs-maintenance.mdc) — update triggers
- `docs/README.md` and the nearest canonical doc for the domain

Details: [docs/agents/subagent-guide.md](../../docs/agents/subagent-guide.md#docs-maintainer)

## Output

- Which docs to update (nearest canonical only)
- Proposed edits or completed updates
- Final response note: `Docs updated:` / `Docs checked, no update needed:` / `Docs not checked:`

## Avoid

- Duplicating long prose from `AGENTS.md`
- Broad doc rewrites unless requested
- Creating new docs when a canonical doc already exists
