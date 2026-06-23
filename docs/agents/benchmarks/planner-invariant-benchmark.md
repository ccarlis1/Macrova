# Benchmark: Planner Invariant

Repeatable check that planner edits preserve core invariants.

## Task

Ask an agent to modify planner search or tag-filter behavior (or review a proposed diff).

## Expected behavior

- Preserves deterministic default search path
- Required tags = hard constraints; preferred tags = scoring only
- Respects pin/batch precedence (batch lock → pin → required → preferred)
- Keeps structured `FM-*` failure codes with `fix_hint`
- Does not let LLM bypass validation

## Files likely involved

- `src/planning/`, `tests/planning/`
- `.cursor/rules/planner.mdc`
- `docs/planner/planner-rules.md`, `docs/tagging/tag-semantics-contract.md`

## Validation commands

```bash
python3 scripts/run_pytest.py tests/planning/
```

## Pass conditions

- Invariants acknowledged in plan or review
- Planning tests pass
- No nondeterminism introduced in default path

## Failure conditions

- Required/preferred tag semantics swapped or blurred
- Generic errors replace structured failure modes
- LLM output used without validation
