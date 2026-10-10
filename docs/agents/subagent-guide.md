# Subagent Guide

Detailed reference for Macrova specialized agents. Short executable definitions live in [`.claude/agents/`](../../.claude/agents/); this doc holds the detail they link to.

Canonical rules remain in [AGENTS.md](../../AGENTS.md).

---

## task-router

**When to call:** Multi-domain tasks, unfamiliar areas, before broad refactors.

**Read:** [task-router.md](task-router.md), [AGENTS.md](../../AGENTS.md).

**Output:** Domain classification, specialists to invoke, docs/source to read, validation commands, recommended next step.

**Do not:** Edit code during classification; duplicate the routing table in responses.

---

## backend-contract-auditor

**When to call:** API changes, frontend wiring, OpenAPI updates, endpoint work (recipes, planner, profile, pins, meal-prep).

**Read:**

- `src/api/server.py`, `recipe_sync.py`, `tag_routes.py`, `meal_prep_routes.py`
- `src/api/error_mapping.py`
- `openapi/openapi.json`
- `tests/api/`

**Output:** Actual request/response shapes, error codes, contract gaps, contract-test recommendations.

**Do not:** Invent routes or DTO fields; trust prose over source/OpenAPI.

---

## planner-invariant-reviewer

**When to call:** Planner, schedule, tag-filter, pin, meal-prep batch, or failure-reporting changes.

**Read:**

- `src/planning/` (`planner.py`, phase modules)
- `src/llm/tag_filtering_service.py`
- `docs/planner/*`, `docs/tagging/tag-semantics-contract.md`

**Output:** Invariant checklist (determinism, required vs preferred tags, pin/batch precedence, `FM-*` + `fix_hint`), risks, test/doc recommendations.

**Do not:** Add nondeterminism; let LLM bypass validation; hide structured failures.

---

## flutter-wiring-agent

**When to call:** Replacing mocks, wiring screens to backend, aligning DTOs, adding UI states.

**Read:**

- `frontend/lib/` (providers, models, services, screens)
- `docs/usage/flutter-setup.md`
- Backend shapes via **backend-contract-auditor**

**Output:** Wiring plan reusing existing providers/DTOs, loading/empty/error states, contract references, honest partial-feature notes.

**Do not:** Duplicate models/providers; present mocks as complete.

---

## docs-maintainer

**When to call:** Behavior, commands, API, planner, LLM, tagging, architecture, or agent-rule changes.

**Read:** [AGENTS.md](../../AGENTS.md), [`.cursor/rules/docs-maintenance.mdc`](../../.cursor/rules/docs-maintenance.mdc), nearest canonical doc.

**Output:** Which docs to update, proposed/completed edits, final `Docs updated:` / `Docs checked, no update needed:` / `Docs not checked:` note.

**Do not:** Broad rewrites; duplicate AGENTS.md; create redundant docs.

---

## test-coverage-agent

**When to call:** After substantive changes; before task completion.

**Read:** Relevant `tests/` subtree, `scripts/run_pytest.py`, `frontend/test/` for Flutter.

**Output:** Tests run or recommended, honest pass/fail/not-run report, focused missing-test suggestions.

**Do not:** Run bare `pytest`; claim success without running relevant tests; add trivial tests.

**Commands:**

- Backend: `python3 scripts/run_pytest.py`
- Frontend: `cd frontend && flutter test`

---

## Invoking specialists

1. **task-router** classifies the task (read-only).
2. Domain specialists audit or review before/during implementation.
3. **test-coverage-agent** validates changes.
4. **docs-maintainer** ensures docs stay current.

Not every task needs every specialist. Use [task-router.md](task-router.md) to pick the minimum set.

Benchmarks in [benchmarks/](benchmarks/) provide repeatable checks when agent rules change.
