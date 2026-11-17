"""PreToolUse guard for shell commands.

Covers the failure modes that reach the working tree through Bash rather than
through an editor:

* destructive operations and ``git add`` against the user's data and the
  committed recipe/tag stores (AGENTS.md invariant "User data paths");
* running a repo command from the wrong directory -- default data
  paths are relative and ``pytest.ini`` sets ``pythonpath = .``;
* adding a dependency, which is the user's decision;
* backing up ``config/user_profile.yaml`` before pytest, as a safety net in
  case a test writes to it (``tests/conftest.py`` fails the session if one does,
  but cannot restore the file).

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

#: User-owned data and committed stores. Matching a ``.example`` sibling is never a hit.
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
                "Never delete or truncate them -- they are the user's data "
                "(AGENTS.md invariant \"User data paths\")."
            )

        if not hits:
            continue

        if re.search(r"git\s+add(?![\w-])", segment):
            common.deny(
                f"BLOCKED: `git add` of {', '.join(sorted(set(hits)))}.\n\n"
                "Never `git add` the user's real data files by hand -- committing them "
                "publishes the user's personal data (AGENTS.md invariant \"User data paths\"). "
                "Schema changes go in the .example file instead."
            )

        for pattern, label in DESTRUCTIVE:
            if pattern.search(segment):
                common.deny(
                    f"BLOCKED: {label} targeting {', '.join(sorted(set(hits)))}.\n\n"
                    "Deleting or overwriting anything under data/ or config/ that isn't a "
                    ".example file is the user's decision. If they asked "
                    "for it, have them confirm."
                )


def _is_checkout_root(path: Path, root: Path) -> bool:
    """The project root, or the root of a git worktree of this repo.

    A worktree's top level has its own ``.git`` file and ``pytest.ini``, so
    relative data paths and ``pythonpath = .`` resolve there just as they do
    at the main checkout's root.
    """
    if path == root:
        return True
    return (path / ".git").exists() and (path / "pytest.ini").is_file()


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
            if pattern.search(segment) and not _is_checkout_root(landing, root):
                common.deny(
                    f"BLOCKED: running {label} from {landing}, not the repo root.\n\n"
                    "Repo commands resolve paths from the repo root: run everything from the "
                    "repo root; never fix this by hardcoding absolute paths.\n\n"
                    f"Rerun as:  cd {root} && <your command>"
                )


def _check_dependency_installs(command: str) -> None:
    if re.search(r"(?<![\w-])pip3?\s+install(?![\w-])", command) and not re.search(
        r"-r\s+\S*requirements\.txt", command
    ):
        common.ask(
            "This installs a Python package outside requirements.txt.\n\n"
            "Adding a dependency to requirements.txt or pubspec.yaml is a decision to stop "
            "and ask the user about. (Repairing the venv with "
            "`pip install -r requirements.txt` is always fine and is not blocked.)"
        )
    if re.search(r"(?:flutter|dart)\s+pub\s+add(?![\w-])", command):
        common.ask(
            "This adds a Flutter/Dart dependency.\n\n"
            "Adding a dependency to pubspec.yaml is the user's decision. Note "
            "the repo deliberately avoids Riverpod, Mockito and GetIt."
        )


def _backup_profile(command: str) -> str | None:
    """Snapshot the real profile before pytest; return an advisory line if taken.

    ``tests/conftest.py`` never reads or writes the real file: it points tests at a
    per-test ``NUTRITION_USER_PROFILE_PATH`` and fails the session if the real file
    was created, changed or deleted. It cannot restore it, so a snapshot can.
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
        "(tests/conftest.py fails the session if a test changes it, but cannot restore it)"
    )


def _pytest_filter_advice(command: str) -> str | None:
    if not re.search(r"(?<![\w./-])pytest(?![\w-])", command):
        return None
    if not re.search(r"(?<![\w-])(-k(?![\w-])|--deselect|--lf|--ff|--last-failed)", command):
        return None
    return (
        "[hook] filtered pytest run: fine while iterating, but run the full "
        "suite (`python3 scripts/run_pytest.py`, ~12s for the full suite) before you call "
        "anything done."
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
