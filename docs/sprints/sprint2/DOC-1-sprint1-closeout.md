# DOC-1 — Close out Sprint 1 stubs

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** —

## Summary

Apply the Sprint 2 README's dispositions to every Sprint 1 stub that isn't finished, so no Sprint 1 stub stays `todo`.

## Context

Roadmap Part 3 (Stop 1) says: never start a new sprint while a stub from the previous batch is still `todo`. Sixteen Sprint 1 stubs are `todo`: FE-1 to FE-10, BE-15 and AI-1 to AI-5. Sprint 2 planning was not allowed to edit `docs/sprints/sprint1/`, so the dispositions are recorded in `docs/sprints/sprint2/README.md` and applied here.

Unblocks: the start of Sprint 2 (prerequisite 2).

## Acceptance criteria

- [ ] Each of FE-1 to FE-10 has a new `Status:` (`superseded`, `merged` or `deferred`) and a line `Superseded by: <Sprint 2 ID>` or `Deferred: <reason>`, matching the README's "Sprint 1 FE stubs: dispositions" table.
- [ ] AI-1 to AI-5 are `Status: parked` with the one-line reason from the README. AI-5's stub-vs-roadmap disagreement (the roadmap calls it done; the stub says `todo`) is resolved. Check `git log -- src/llm/` for duplicate detection and set `implemented` or `parked` to match the code.
- [ ] BE-15: each of its 5 bullets is checked against `tests/api/` and `tests/test_api_v1_and_openapi.py`. A bullet gets `[x]` only with a named, passing test. The stub ends `implemented` if all 5 are covered; otherwise `parked`, with the uncovered bullets listed for Sprint 3.
- [ ] `docs/sprints/sprint1/README.md` gets a short "Status vocabulary" note: `implemented` and `done` both mean finished; `superseded`, `merged`, `deferred` and `parked` are the Sprint 2 close-out states.
- [ ] Test: `grep -l "Status:\*\* todo" docs/sprints/sprint1/*.md` returns nothing. This is a doc task, so the grep is the check.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `docs/sprints/sprint2/README.md` (the disposition tables), every `docs/sprints/sprint1/*.md` with `Status:** todo`.
- Files to modify: only `docs/sprints/sprint1/*.md`.
- Do NOT: change acceptance criteria text in the Sprint 1 stubs, delete stubs, or edit code.

### 🧠 Pre-implementation analysis
1. List the `todo` stubs: `grep -l "Status:\*\* todo" docs/sprints/sprint1/*.md`. On 2026-11-14 there were 16.
2. For BE-15, grep the test tree for each bullet's behavior (`FM-TAG-EMPTY`, `batch_id`, `alias`, `merge`, `default_servings`, `RECIPE_NOT_FOUND` on pins). `REQUIRES_VERIFICATION`: whether `tests/api/test_recipe_routes.py` and the pin route tests already cover bullets 4 and 5.

### ✅ Post-implementation validation
- The grep above returns nothing.
- `python3 scripts/run_pytest.py` still passes (no code touched; this confirms it).

## Out of scope

- Rewriting any Sprint 1 stub's content.
- Writing the BE-15 tests that are missing. List them; Sprint 3 decides.
- Updating `docs/EXECUTION_ROADMAP.md`.
