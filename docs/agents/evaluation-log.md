# Agent Evaluation Log

Lightweight log for agent-rule and subagent changes. Add a dated entry when modifying `AGENTS.md`, `.cursor/rules/`, `.claude/agents/`, or `docs/agents/`.

## Template

```markdown
### YYYY-MM-DD — Short title

- **Problem:** What was wrong or missing?
- **Change:** What was added or updated?
- **Test task:** Benchmark or sample task used to verify.
- **Result:** Pass / partial / fail — brief notes.
- **Follow-up:** Open items, if any.
```

---

## Entries

### 2026-06-23 — Initial specialized agent setup

- **Problem:** No `.claude/agents/` subagents; `docs-maintenance.mdc` was large, always-on, and had malformed frontmatter; planner invariants mixed into `backend.mdc`.
- **Change:** Added six subagents, `global.mdc` (only always-on rule), `planner.mdc`, slimmed `docs-maintenance.mdc` and `backend.mdc`, created `docs/agents/` task-router, subagent-guide, benchmarks, evaluation-log.
- **Test task:** Run benchmarks in [benchmarks/](benchmarks/) and conflict greps from AGENTS.md validation plan.
- **Result:** Pending first run after merge.
- **Follow-up:** Re-run benchmarks when agent rules change; add entries for each significant tweak.
