"""Stop gate -- the turn does not end on a red suite.

CLAUDE.md §7 defines "done" as a list of commands that pass. This hook runs
them, so the definition holds mechanically instead of aspirationally. Which
gates run is decided by what is actually dirty in the working tree, and the
whole backend set costs about three seconds.

Two design choices worth knowing:

* **Signal is ``git status``, not session bookkeeping.** State files desync
  across compaction and resumed sessions; the working tree cannot.
* **Results are cached by content hash.** A Stop with nothing changed since the
  last green run is free, so this can safely fire on every turn.

Loop safety: after ``MAX_BLOCKS`` consecutive blocks the gate downgrades to a
loud warning, so a genuinely stuck failure can never spin forever.
"""

from __future__ import annotations

import shutil

import _common as common

MAX_BLOCKS = 3

#: Fixed so the gate itself is reproducible; varying it would make Stop flaky.
ALT_HASH_SEED = "524287"


def _tail(text: str, limit: int = 1800) -> str:
    stripped = text.strip()
    return stripped if len(stripped) <= limit else "...\n" + stripped[-limit:]


def _failures(output: str) -> str:
    """Failing test ids if pytest named any, else the tail of the raw output."""
    named = [line for line in output.splitlines() if line.startswith(("FAILED ", "ERROR "))]
    if named:
        return "\n".join(named[:25])
    return _tail(output)


def _run_backend_gates(dirty: list[str]) -> list[str]:
    """Run every gate the dirty set implies; return human-readable failures."""
    problems: list[str] = []
    python = common.project_python()

    backend_dirty = any(common.under(path, "src", "tests") for path in dirty)
    api_dirty = any(common.under(path, "src/api", "src/models") for path in dirty)
    planning_dirty = any(common.under(path, "src/planning") for path in dirty)

    if backend_dirty:
        rc, out = common.run([python, "-m", "pytest", "tests/", "-q"], timeout=300)
        if rc != 0:
            problems.append(
                "`python -m pytest tests/ -q` FAILED (CLAUDE.md §7: the full suite must pass, "
                "no deselection, no -k):\n\n" + _failures(out)
            )
        elif planning_dirty:
            # Law 3: hash order must not reach plan output. One alternate seed,
            # fixed for reproducibility.
            rc, out = common.run(
                [python, "-m", "pytest", "tests/", "-q"],
                timeout=300,
                extra_env={"PYTHONHASHSEED": ALT_HASH_SEED},
            )
            if rc != 0:
                problems.append(
                    f"The suite passes normally but FAILS under PYTHONHASHSEED={ALT_HASH_SEED}.\n\n"
                    "That is nondeterminism: something in src/planning/ depends on dict/set "
                    "iteration order (CLAUDE.md law 3, trap 6). Sort before iterating.\n\n"
                    + _failures(out)
                )

    if api_dirty:
        rc, out = common.run([python, "scripts/export_openapi.py", "--check"], timeout=60)
        if rc != 0:
            problems.append(
                "`python scripts/export_openapi.py --check` FAILED -- CI fails on this.\n"
                "Run `python scripts/export_openapi.py` and commit openapi/openapi.json.\n\n"
                + _tail(out, 400)
            )

    return problems


def _run_flutter_gates(dirty: list[str]) -> list[str]:
    """Flutter is not in CI, so this hook is the only thing checking it."""
    if not any(common.under(path, "frontend") for path in dirty):
        return []
    if not shutil.which("flutter"):
        return []

    problems: list[str] = []
    frontend = common.project_dir() / "frontend"

    rc, out = common.run(["flutter", "analyze"], timeout=300, cwd=frontend)
    if rc != 0:
        problems.append("`flutter analyze` FAILED (not covered by CI):\n\n" + _tail(out))

    rc, out = common.run(["flutter", "test"], timeout=600, cwd=frontend)
    if rc != 0:
        problems.append("`flutter test` FAILED (not covered by CI):\n\n" + _tail(out))

    return problems


def main() -> None:
    event = common.read_event()
    session = str(event.get("session_id") or "unknown")
    state_name = f"stop-{session}.json"

    dirty = [
        path
        for path in common.dirty_paths()
        if common.under(path, "src", "tests", "frontend", "scripts", "openapi")
    ]
    if not dirty:
        common.ok()

    key = common.hash_paths(dirty)
    state = common.read_state(state_name)
    if state.get("passed_key") == key:
        common.ok()

    problems = _run_backend_gates(dirty) + _run_flutter_gates(dirty)

    if not problems:
        common.write_state(state_name, {"passed_key": key, "blocks": 0})
        common.ok()

    blocks = int(state.get("blocks") or 0) + 1
    common.write_state(state_name, {"passed_key": None, "blocks": blocks})

    report = "\n\n".join(problems)
    if blocks > MAX_BLOCKS:
        common.ok(
            f"[hook] verification still failing after {MAX_BLOCKS} blocks; not blocking again "
            f"so you can hand back to the user. UNRESOLVED:\n{report}"
        )

    common.stop_block(
        f"Verification failed ({blocks}/{MAX_BLOCKS}) -- do not finish yet.\n\n"
        f"{report}\n\n"
        "Fix these, then stop again. If a failing expectation is a deliberate product change, "
        "CLAUDE.md §8 says that is the user's decision: stop and show them the before/after."
    )


if __name__ == "__main__":
    main()
