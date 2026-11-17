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

- [AGENTS.md](../../AGENTS.md) — invariants and what must pass
- [docs/architecture/map/README.md](../../docs/architecture/map/README.md) — areas, the "Area → checks and reviewers" routing table, and change recipes

## Output

- Task domain(s) and scope
- Specialists to invoke (if any)
- Docs and source areas to read first
- Likely tests and doc updates
- Recommended next step (implement vs. audit vs. review)

## Avoid

- Duplicating the routing table — link to the map README
- Making code changes during classification
