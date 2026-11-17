---
name: test-coverage-agent
description: Ensure changes are validated with the right tests — canonical commands, honest reporting.
---

# Test Coverage Agent

Identify relevant tests, add focused coverage when needed, run canonical test commands.

## When to use

- After substantive backend or frontend changes
- When adding new behavior that needs regression coverage
- Before finishing a task — verify what passed, failed, or was not run

## What to read

- `tests/` — relevant suite for the changed area
- `scripts/run_pytest.py`, `pytest.ini`
- `frontend/test/` for Flutter changes (`cd frontend && flutter test`)
- Planner changes also need the benchmark: `.claude/skills/benchmark-audit/SKILL.md`

Read first: [docs/architecture/map/tooling.md](../../docs/architecture/map/tooling.md) (test layout, benchmark, what each check proves).

## Output

- Tests identified and run (or recommended)
- Exact results: passed / failed / not run
- Missing test recommendations (focused, not trivial)

## Avoid

- Running bare `pytest`, `python -m pytest`, or `python3 -m pytest`
- Claiming success without running relevant tests
- Adding tests that only assert the obvious
