---
name: planner-invariant-reviewer
description: Protect deterministic planner correctness — tags, pins, batches, failure modes, LLM boundaries.
---

# Planner Invariant Reviewer

Verify planner changes preserve deterministic behavior and structured failure reporting.

## When to use

- Changes to `src/planning/`, schedule models, tag filtering, pins, or meal-prep batch locks
- Planner UI or failure-reporting changes
- Tag hard-filter vs. scoring semantics

## What to read

- `src/planning/` (especially `planner.py`, phase modules)
- `src/llm/tag_filtering_service.py`
- `docs/planner/mealplan-specification-v3.md`, `docs/tagging/tag-semantics-contract.md`

Read first: [docs/architecture/map/planning.md](../../docs/architecture/map/planning.md) (invariants with where each is enforced, known gaps).

## Output

- Invariant checklist (determinism, tag semantics, pin/batch precedence, `FM-*` codes)
- Risks or violations found
- Recommended tests or doc updates

## Avoid

- Introducing nondeterminism in the default search path
- Letting LLM outputs bypass validation or drive planning
- Hiding planner failures behind generic errors
