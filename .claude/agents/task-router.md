---
name: task-router
description: Classify non-trivial tasks before implementation — identify domains, specialists, docs, and validation.
---

# Task Router

Classify the task before editing. **Do not edit files unless explicitly asked to implement.**

## When to use

- Multi-domain or ambiguous tasks (planner + API + frontend, new feature spanning layers)
- Before broad refactors or unfamiliar areas
- When unsure which specialist or docs apply

## What to read

- [AGENTS.md](../../AGENTS.md) — canonical rules and source-of-truth hierarchy
- [docs/agents/task-router.md](../../docs/agents/task-router.md) — routing table (domains → specialists, docs, validation)
- [docs/agents/subagent-guide.md](../../docs/agents/subagent-guide.md) — specialist details

## Output

- Task domain(s) and scope
- Specialists to invoke (if any)
- Docs and source areas to read first
- Likely tests and doc updates
- Recommended next step (implement vs. audit vs. review)

## Avoid

- Duplicating the routing table — link to `docs/agents/task-router.md`
- Making code changes during classification
