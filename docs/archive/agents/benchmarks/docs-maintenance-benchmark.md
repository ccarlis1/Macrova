# Benchmark: Docs Maintenance

Repeatable check that behavior changes trigger doc updates and a final Docs note.

## Task

Make a small behavior change (e.g. add a CLI flag, change a canonical command) and ask the agent to complete the task.

## Expected behavior

- Identifies nearest canonical doc to update
- Does not duplicate long AGENTS.md prose in multiple files
- Final response includes `Docs updated:` or `Docs checked, no update needed:`

## Files likely involved

- `.cursor/rules/docs-maintenance.mdc`
- `AGENTS.md`, `docs/README.md`, domain docs

## Validation commands

Manual review of agent final response and changed doc files.

## Pass conditions

- Relevant doc updated or explicitly checked with reason
- Final Docs note present

## Failure conditions

- Behavior/command change with no doc check
- Broad doc rewrite without request
- Missing final Docs note
