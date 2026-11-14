# Claude / AI agent instructions

Canonical agent instructions for this repository live in **[AGENTS.md](AGENTS.md)**.

Read AGENTS.md before making changes. It covers commands, environment rules, source-of-truth hierarchy, planner/LLM/tagging invariants, and deeper-doc pointers.

Documentation index: [docs/README.md](docs/README.md).

## Orchestrator mode (Fable lead, Opus subagents)

When this session runs on Fable, act as the orchestrator and do the heavy work through Opus subagents:

- **Plan and route yourself.** Read AGENTS.md, classify the task (use the `task-router` approach for multi-domain work), and split it into self-contained pieces with clear file scopes and "done" criteria.
- **Delegate execution.** Send implementation, broad searches, test runs, and specialist reviews (`.claude/agents/*`) to subagents with `model: "opus"`. `.claude/settings.local.json` also sets `CLAUDE_CODE_SUBAGENT_MODEL=opus` as the default.
- **Give full briefs.** Subagents start cold: name the files, the relevant AGENTS.md invariants, the canonical test command, and what to report back.
- **Keep writers apart.** Parallel subagents must not edit the same files; use `isolation: "worktree"` when scopes might overlap.
- **Verify before reporting.** Check each subagent's diff and test output yourself. A subagent's summary is not proof.
- **Do small things directly.** A one-line fix or a single file read doesn't need a subagent.
