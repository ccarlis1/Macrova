"""PreToolUse guard for shell commands.

Covers the failure modes that reach the working tree through Bash rather than
through an editor:

* destructive operations and ``git add`` against the user's gitignored data
  (CLAUDE.md §2 table, trap 4);
* running a repo command from the wrong directory (trap 12) -- default data
  paths are relative and ``pytest.ini`` sets ``pythonpath = .``;
* adding a dependency, which §8 makes the user's decision;
* backing up ``config/user_profile.yaml`` before pytest, because
  ``tests/conftest.py`` rewrites it from the example when the YAML has no
  usable schedule.

Filtered pytest runs are only advised against, never blocked: iterating with
``-k`` is legitimate, and ``verify_stop.py`` enforces the unfiltered suite
before the turn can end.
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

import _common as common

#: Gitignored, user-owned data. Matching a ``.example`` sibling is never a hit.
PROTECTED_RE = re.compile(
    r"(?P<path>"
    r"config/(?:user_profile|nutrition_goals|model_config)\.yaml"
    r"|data/recipes/(?:recipes|recipe_tags)\.json"
    r"|data/ingredients/(?:custom_ingredients|usda_ingredients)\.json"
    r"|data/nutrition/nutrition_db\.json"
    r"|data/llm/feedback_cache\.json"
    r")(?!\.example)(?![\w./-])"
)

#: Commands whose relative default paths only resolve from the repo root.
REPO_ROOTED = (
    (re.compile(r"(?<![\w./-])pytest(?![\w-])"), "pytest (pytest.ini sets pythonpath = .)"),
    (re.compile(r"plan_meals\.py"), "the CLI planner (default data paths are relative)"),
    (re.compile(r"scripts/\w+\.py"), "a repo script (it resolves paths from the repo root)"),
    (re.compile(r"uvicorn\s+src\.api\.server"), "the API server"),
)

DESTRUCTIVE = (
    (re.compile(r"(?<![\w-])rm(?![\w-])"), "rm"),
    (re.compile(r"(?<![\w-])mv(?![\w-])"), "mv"),
    (re.compile(r"(?<![\w-])truncate(?![\w-])"), "truncate"),
    (re.compile(r"(?<![\w-])(?:tee|dd)(?![\w-])"), "a stream writer"),
    (re.compile(r"git\s+checkout\s"), "git checkout"),
    (re.compile(r"git\s+restore\s"), "git restore"),
    (re.compile(r"(?<!>)>\s*\S*(?:config|data)/"), "a truncating redirect"),
)


def _segments(command: str) -> list[str]:
    """Split a compound command on shell separators so each clause is judged alone."""
    return [part for part in re.split(r"&&|\|\||;|\|", command) if part.strip()]


def _protected_hits(text: str) -> list[str]:
    return [match.group("path") for match in PROTECTED_RE.finditer(text)]


def _check_data_writes(command: str) -> None:
    for segment in _segments(command):
        hits = _protected_hits(segment)

        if re.search(r"git\s+clean\s+-\w*[fdx]", segment):
            common.deny(
                "BLOCKED: `git clean` would delete the user's gitignored data files "
                "(recipes.json, custom_ingredients.json, user_profile.yaml).\n\n"
                "CLAUDE.md trap 4: 'never delete or truncate them either -- they are the "
                "user's data.'"
            )

        if not hits:
            continue

        if re.search(r"git\s+add(?![\w-])", segment):
            common.deny(
                f"BLOCKED: `git add` of {', '.join(sorted(set(hits)))}.\n\n"
                "These files are gitignored on purpose. CLAUDE.md trap 4: 'never `git add` "
                "the gitignored real data files' -- committing them publishes the user's "
                "personal data. Schema changes go in the .example file instead."
            )

        for pattern, label in DESTRUCTIVE:
            if pattern.search(segment):
                common.deny(
                    f"BLOCKED: {label} targeting {', '.join(sorted(set(hits)))}.\n\n"
                    "CLAUDE.md §8 makes deleting or overwriting anything under data/ or "
                    "config/ that isn't a .example file the user's decision. If they asked "
                    "for it, have them confirm."
                )


def _check_cwd(command: str, cwd: str | None) -> None:
    root = common.project_dir()

    # A `cd` inside the command wins over the session cwd, so judge the clause
    # that actually runs the repo command.
    landing = Path(cwd).resolve() if cwd else root
    for segment in _segments(command):
        moved = re.search(r"(?<![\w-])cd\s+(?P<dest>[^\s;&|]+)", segment)
        if moved:
            dest = moved.group("dest").strip("\"'")
            landing = (landing / dest).resolve() if not dest.startswith("/") else Path(dest)
            continue
        for pattern, label in REPO_ROOTED:
            if pattern.search(segment) and landing != root:
                common.deny(
                    f"BLOCKED: running {label} from {landing}, not the repo root.\n\n"
                    "CLAUDE.md trap 12 (The Wrong-CWD Failure): 'run everything from the "
                    "repo root; never fix this by hardcoding absolute paths.'\n\n"
                    f"Rerun as:  cd {root} && <your command>"
                )


def _check_dependency_installs(command: str) -> None:
    if re.search(r"(?<![\w-])pip3?\s+install(?![\w-])", command) and not re.search(
        r"-r\s+\S*requirements\.txt", command
    ):
        common.ask(
            "This installs a Python package outside requirements.txt.\n\n"
            "CLAUDE.md §8 lists 'adding a dependency to requirements.txt or pubspec.yaml' as "
            "a decision to stop and ask about. (Repairing the venv with "
            "`pip install -r requirements.txt` is always fine and is not blocked.)"
        )
    if re.search(r"(?:flutter|dart)\s+pub\s+add(?![\w-])", command):
        common.ask(
            "This adds a Flutter/Dart dependency.\n\n"
            "CLAUDE.md §8: adding a dependency to pubspec.yaml is the user's decision. Note "
            "the repo deliberately avoids Riverpod, Mockito and GetIt (trap 10)."
        )


def _backup_profile(command: str) -> str | None:
    """Snapshot the real profile before pytest; return an advisory line if taken.

    ``tests/conftest.py`` copies ``user_profile.yaml.example`` over the real file
    whenever the YAML fails to parse or carries no usable schedule. That is a
    data-loss path inside the suite itself, and only a snapshot can undo it.
    """
    if not re.search(r"(?<![\w./-])pytest(?![\w-])", command):
        return None
    profile = common.project_dir() / "config" / "user_profile.yaml"
    if not profile.is_file():
        return None
    backups = common.state_dir() / "profile-backups"
    try:
        backups.mkdir(parents=True, exist_ok=True)
        target = backups / f"user_profile.{time.strftime('%Y%m%dT%H%M%S')}.yaml"
        shutil.copyfile(profile, target)
        for stale in sorted(backups.glob("user_profile.*.yaml"))[:-5]:
            stale.unlink()
    except OSError:
        return None
    return (
        f"[hook] backed up config/user_profile.yaml -> {target.relative_to(common.project_dir())} "
        "(tests/conftest.py can overwrite it from the .example)"
    )


def _pytest_filter_advice(command: str) -> str | None:
    if not re.search(r"(?<![\w./-])pytest(?![\w-])", command):
        return None
    if not re.search(r"(?<![\w-])(-k(?![\w-])|--deselect|--lf|--ff|--last-failed)", command):
        return None
    return (
        "[hook] filtered pytest run: fine while iterating, but CLAUDE.md §5 wants the full "
        "suite (`python -m pytest tests/ -q`, ~2s for 1040 tests) before you call anything done."
    )


def main() -> None:
    event = common.read_event()
    command = common.tool_input(event).get("command") or ""
    if not isinstance(command, str) or not command.strip():
        common.ok()

    _check_data_writes(command)
    _check_cwd(command, event.get("cwd"))
    _check_dependency_installs(command)

    notes = [note for note in (_backup_profile(command), _pytest_filter_advice(command)) if note]
    common.ok("\n".join(notes))


if __name__ == "__main__":
    main()
