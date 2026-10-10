---
name: benchmark-audit
description: Run Macrova's planning benchmark and audit the results. Use to verify a planner fix (regression check against the committed baseline, mapped to the root-cause clusters in evaluation/reports/benchmark_failure_analysis.md), or to refresh the failure analysis after large changes. Use for any change to src/planning/, pins/batches/tags, the oracle, or benchmark scenarios.
---

# Benchmark audit

The benchmark (`evaluation/benchmark/`, 150+ scenarios with oracle labels) runs the real
planner through the same path as `/api/v1/plan`. The failure analysis groups every
disagreement into root-cause clusters (C1, C2a, …). This skill keeps both honest.

All commands run from the repo root with the project venv (`.venv/bin/python`), never the
system interpreter.

## Mode 1: Regression check (verifying a fix)

1. **Pick the baseline.** The committed `evaluation/harness/results/compare.json` is the
   baseline. Rebase onto `main` first, then use `--base main`. Without rebasing, use
   `--base $(git merge-base HEAD main)`, or other merged PRs' changes will show up as yours.
   Run on the **final commit** of the change, from a clean tree. If the working tree already
   has modified results files, stop and ask. Don't overwrite someone's uncommitted run.
2. **Run the harness** (about 40 s total):
   ```bash
   .venv/bin/python evaluation/harness/run_benchmark.py
   .venv/bin/python evaluation/harness/compare.py
   .venv/bin/python evaluation/harness/probes.py
   ```
3. **Diff against the baseline:**
   ```bash
   .venv/bin/python evaluation/harness/diff_results.py --base <ref>
   ```
   It prints the scorecard, the fixed/regressed/changed scenarios, the open disagreements per
   cluster, anything unmapped, and any disagreement left in a cluster marked fixed.
   **Exit code 1 means stop:** investigate before reporting success.
4. **Explain every change.** Each fixed, regressed or changed scenario must be explained by
   the change under test:
   - A targeted cluster's scenarios should move to MATCH/ACCEPTABLE.
   - `ACCEPTABLE → MATCH` after an oracle label was tightened is not a fix. Say so.
   - `NEW` scenarios come from `scenarios.json` changes. Confirm they were intended.
   - The planner is deterministic, so nothing is "flaky". An unexplained change is a finding.
5. **Check the probes.** Probes cover cases the scorecard can't (for example, a fully pinned
   day inside a longer plan). Report each probe's outcome and whether the independent
   re-check says `valid`.
6. **Report** in this format (for the PR description and the project notes):
   ```text
   Benchmark (<base> -> <branch>): exact A -> B, acceptable C -> D, disagreements E -> F (N scenarios)
   Fixed: MB-… (cluster) · Regressed: none · Other: …
   Open by cluster: C1 11 · C2a 20 · …   Unmapped: 0
   Probes: P1 … · P2 … · P3 …
   ```
7. **Close the loop:**
   - When a cluster is resolved, add `**Status:** fixed. <one line on how>` under its
     `### C<n>.` heading in the failure analysis. `diff_results.py` uses that marker.
   - Add a benchmark scenario for any case only a probe covered, so the scorecard catches it next time.
   - **Ask before committing** the refreshed `results.json`/`compare.json` as the new baseline.

## Mode 2: Full audit (refresh the failure analysis)

Use after large planner changes, a new batch of scenarios, or when unmapped disagreements pile up.

1. Run Mode 1 steps 2–3.
2. Run the counterfactuals, each with its own output file:
   ```bash
   ALL_BATCHES=1 OUT=evaluation/harness/results/results_all_batches.json .venv/bin/python evaluation/harness/run_benchmark.py
   LIMIT=200000 OUT=/tmp/results_limit.json .venv/bin/python evaluation/harness/run_benchmark.py
   ```
   `ALL_BATCHES` isolates batch-status problems. `LIMIT` separates "attempt limit too low"
   from "search order wrong".
3. For each unmapped disagreement, find the root cause in `src/` and cite `file:line`.
   Group by cause, not by symptom: 39 disagreements were 7 causes last time.
4. Update the failure analysis. Keep each cluster's `### C<n>. <title>` heading and a
   `**Scenarios:**` line listing IDs as `MB-123`, bare `123`, or ranges `050–057`, so
   `diff_results.py` can map them. Update the classification (§5) and the suggested order (§7).

## Rules

- **Never edit the oracle or scenarios to make a result pass.** If a label looks wrong, it's
  a specification question for the user. Flag it and don't change it.
- **Never trust a success without the independent re-check.** `compare.py` re-verifies every
  returned plan (`INVALID_PLAN`, `MISMATCH+INVALID`). A success that breaks a hard constraint
  is the worst outcome.
- **Report outcome and failure code separately.** A right outcome with the wrong code still
  sends the user to the wrong fix hint.
- **Every disagreement belongs to a cluster, or it's new.** Don't hand-wave unmapped rows.
- **Don't commit or push results files without asking.** They're the baseline for the next check.

## Best practices

- **Confirm the cause before coding.** Use a counterfactual or the oracle's `details` to show
  what the defect is before planning a fix. (`ALL_BATCHES=1` proved C1 was one status rule.)
  Put the expected score in the spec, e.g. "123 → 125", so a fix that does more or less than
  intended stands out.
- **Results only count from the code being merged.** Refreshed `results.json`/`compare.json`
  in a PR must come from running the PR's final commit, not an earlier session.
- **Ignore `secs`.** Timing is the only field that varies between runs. Any other difference is
  real, because the planner is deterministic.
- **Keep oracle and scenario changes visible.** Put label or scenario changes in their own
  commit and call them out in the PR, so `ACCEPTABLE → MATCH` from a stricter label isn't
  mistaken for a fix.
- **Mark the cluster fixed in the fix PR** (`**Status:** fixed`). From then on,
  `diff_results.py` fails if any of that cluster's scenarios start failing again.
- **The reviewer re-runs it, isolated.** The implementer runs the check before opening the PR. The
  reviewer re-runs it on the merged code in a separate worktree, so in-progress work in the
  main checkout is never touched:
  ```bash
  git worktree add --detach /tmp/macrova-verify origin/main
  cd /tmp/macrova-verify && <repo>/.venv/bin/python evaluation/harness/run_benchmark.py   # then compare, probes, diff
  git worktree remove --force /tmp/macrova-verify
  ```
- **Record the scorecard line** in the PR description and the project notes, so the score
  history lives outside git too.
- **Switch to Mode 2** when unmapped disagreements appear, after a design change (e.g. search
  order), or when the failure analysis's summary sections (§5–7) no longer match the open clusters.

## What a passing run doesn't cover

- **The ingredient and data layer.** The harness supplies stored per-serving nutrition (§4.4).
- **Situations no scenario covers.** C3 stayed hidden until a scenario had a fully pinned day inside a
  longer plan. A clean score covers the scenarios in the benchmark, not every case.
