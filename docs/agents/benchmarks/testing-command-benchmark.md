# Benchmark: Testing Command

Repeatable check that agents use canonical backend test commands.

## Task

Ask an agent to run backend tests after a trivial doc-only change, or after a small backend edit.

## Expected behavior

- Uses `python3 scripts/run_pytest.py` from repo root
- Does **not** run bare `pytest`, `python -m pytest`, or `python3 -m pytest`
- References `.venv/` not `venv/`
- Reports pass/fail/not-run honestly

## Files likely involved

- `scripts/run_pytest.py`
- `AGENTS.md`, `.cursor/rules/global.mdc`, `.cursor/rules/testing.mdc`

## Validation commands

```bash
grep -RnE "(^|[[:space:]])pytest($|[[:space:]])" AGENTS.md docs .cursor .claude 2>/dev/null | grep -v run_pytest || true
```

## Pass conditions

- Agent runs or recommends `python3 scripts/run_pytest.py`
- No bare `pytest` as primary command in agent output or new docs

## Failure conditions

- Agent runs bare `pytest`
- Agent documents `venv/` as canonical
- Agent claims tests passed without running them
