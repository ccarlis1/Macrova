---
name: sprint-task
description: Execute a sprint task stub (DM-*/BE-*/AI-*/FE-* in docs/sprint1/ or later sprint folders) end-to-end with contract enforcement. Use whenever the user names a task ID, says "do the next sprint task", or asks to implement anything tracked in a sprint doc. Enforces pre-implementation analysis, extend-don't-fork, acceptance-criteria proof, and stub bookkeeping.
---

# Sprint Task Executor

Sprint stubs in this repo are written as **agent-safe execution contracts**. This skill is the
process for honoring one. The stub is the authority on scope; CLAUDE.md §3 (ownership map) is
the authority on where code goes; code itself is the authority on signatures.

## Phase 0 — Select and gate

1. Locate the stub: `docs/sprint1/<ID>-*.md` (adjust folder for later sprints). If the user
   said "next task", pick the first `Status: todo` whose **Depends on** tasks are all `done`
   (dependency graph is in `docs/sprint1/README.md`).
2. Read, in order: the stub in full → the sections of `docs/SPRINT_1.md` it references
   (especially §2 entities, §3.5 precedence) → the stubs of its dependencies (what they
   actually built may differ slightly from what this stub assumes).
3. Gate: if any dependency is not `done`, stop and tell the user which one blocks you. Do not
   partially implement around a missing dependency.
4. Set the stub's `Status:` to `in-progress` before writing code.

## Phase 1 — Pre-implementation analysis (mandatory, in this order)

Stubs contain three binding sections. Treat them exactly as follows:

- **🔒 IMPLEMENTATION CONTRACT** — "Files to inspect" means *read every listed file before
  writing any code*. "Do NOT create" is a hard prohibition. "Entities to reuse" means those
  types are extended in place, never replaced or wrapped in a parallel type.
- **🧠 PRE-IMPLEMENTATION ANALYSIS** — execute each numbered step literally and record what
  you found (actual function signatures, actual field names, actual file paths). Where the
  stub or SPRINT_1.md says `REQUIRES_VERIFICATION`, the spec author explicitly did not check
  the code — verifying it is your job, and your findings override the spec's guess.
- **Out of scope** — binding. If you notice adjacent improvements, list them in your final
  summary; do not implement them.

End Phase 1 by stating (to the user, briefly): the files you will modify, the files you will
create (should usually be zero or one plus tests), and any place where code reality diverged
from the stub's assumptions.

**Divergence rule:** if the acceptance criteria are impossible or wrong against the real code,
stop and report — do not creatively reinterpret the criteria and do not check boxes you
redefined.

## Phase 2 — Implement

- Extend the owning modules from CLAUDE.md §3. Grep for existing helpers before writing new
  ones — the most common failure on this codebase is duplicating logic that already exists
  under a different name.
- All contract-crossing models: pydantic v2, `ConfigDict(extra="forbid")`, described fields.
- All new API/DTO/persisted-JSON fields: optional-additive.
- Planner-adjacent code: deterministic (sorted iteration, seed threaded through, no wall
  clock).
- Write tests alongside: every acceptance-criteria checkbox needs a test that fails without
  your change. Name tests after the module (`tests/test_<module>.py`) and use `tmp_path` for
  any file I/O. No network, no real API keys.

## Phase 3 — Validate and close out

1. Run the full backend suite and contract check (from repo root, venv active):
   ```bash
   python -m pytest tests/ -q
   python scripts/export_openapi.py --check   # regen without --check if you changed src/api/
   ```
   For FE-* tasks: `cd frontend && flutter analyze && flutter test`.
2. Execute the stub's **✅ POST-IMPLEMENTATION VALIDATION** checklist item by item. Each item
   gets verified by actually doing the thing (running the test, grepping for forbidden files),
   not by recalling that you intended it.
3. Update the stub file:
   - Check `[x]` only the acceptance criteria you can point to a passing test for.
   - Leave unchecked anything not delivered, with a one-line reason under it.
   - Update `Status:` (`done`, or `blocked` + why).
4. Final summary to the user must include: what changed and where, which tests prove each
   acceptance criterion, any stub-vs-code divergences found, and any out-of-scope items noticed.

## Anti-patterns this skill exists to prevent

| Anti-pattern | Instead |
|---|---|
| Implementing from the stub's description without reading the listed files | Phase 1 is mandatory and comes first |
| Creating a sibling module because the owning one "is getting big" | Extend it; module size is the user's call |
| Checking acceptance boxes optimistically | Box checked ⇔ proving test exists and passes |
| "Fixing" existing tests whose expectations your change broke | That's a product behavior change — stop and show the user the before/after |
| Doing FE and BE halves of two different tasks because they're adjacent | One task ID per execution; note the adjacency instead |
