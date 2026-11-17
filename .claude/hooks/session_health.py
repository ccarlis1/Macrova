"""SessionStart environment report.

Catches two environment problems before they cost a debugging cycle:

* a broken venv -- if imports are broken, say so up
  front with the one-line repair, so a wall of collection errors is never read
  as a code failure;
* missing local data files -- confirm the profile, recipe pool and legacy
  ingredient file exist (repo commands resolve these from the repo root).

Never blocks. Worst case it prints nothing useful.
"""

from __future__ import annotations

from pathlib import Path

import _common as common

RUNTIME_IMPORTS = ("fastapi", "pydantic", "httpx", "yaml", "requests", "pytest")

#: Local data files with a shipped ``.example``. ``config/user_profile.yaml`` is the
#: untracked CLI ``--profile`` default; ``recipes.json`` is committed (CLI/server
#: default recipe pool); ``custom_ingredients.json`` is gitignored and legacy -- the
#: CLI/server ingredient default is ``data/reference/ingredient_nutrition.json``.
#: tests/conftest.py restores the two data/ files if absent, never the profile.
RUNTIME_DATA = (
    ("config/user_profile.yaml", "config/user_profile.yaml.example"),
    ("data/recipes/recipes.json", "data/recipes/recipes.json.example"),
    (
        "data/ingredients/custom_ingredients.json",
        "data/ingredients/custom_ingredients.json.example",
    ),
)


def _python_line(python: str) -> str:
    rc, out = common.run([python, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"], timeout=30)
    if rc != 0:
        return f"- interpreter: UNUSABLE ({python}) -- {out.strip()[:120]}"
    version = out.strip()
    where = "repo .venv" if ".venv" in python else python
    if not version.startswith(common.CI_PYTHON + "."):
        return (
            f"- interpreter: {version} ({where}) -- CI pins {common.CI_PYTHON}; "
            "version-specific failures here may not reproduce in CI, and vice versa"
        )
    return f"- interpreter: {version} ({where}), matches CI"


def _imports_line(python: str) -> str:
    script = (
        "import importlib.util\n"
        f"missing = [m for m in {RUNTIME_IMPORTS!r} if importlib.util.find_spec(m) is None]\n"
        "print(','.join(missing))"
    )
    rc, out = common.run([python, "-c", script], timeout=60)
    missing = out.strip()
    if rc != 0:
        return f"- imports: could not check ({out.strip()[:120]})"
    if missing:
        return (
            f"- imports: MISSING {missing} -- the venv is broken. Mass pytest collection "
            "errors are the venv, not the code. Repair first: "
            "`pip install -r requirements.txt`, then rerun before touching any source file."
        )
    return "- imports: all runtime deps present"


def _data_lines(root: Path) -> list[str]:
    missing = [
        (rel, example)
        for rel, example in RUNTIME_DATA
        if not (root / rel).is_file() and (root / example).is_file()
    ]
    if not missing:
        return []
    lines = [
        "- data: local data files are absent (tests/conftest.py restores the data/ ones, "
        "the CLI and server do NOT):"
    ]
    lines += [f"    cp -n {example} {rel}" for rel, example in missing]
    return lines


def _git_lines(root: Path) -> list[str]:
    rc, branch = common.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=20)
    lines = [f"- branch: {branch.strip()}"] if rc == 0 else []

    dirty_data = [
        path
        for path in common.dirty_paths()
        if common.under(path, "data", "config") and not path.endswith(".example")
    ]
    if dirty_data:
        lines.append(
            "- user data with uncommitted changes (do not `git add` these by hand; "
            "AGENTS.md invariant \"User data paths\"): "
            + ", ".join(sorted(dirty_data)[:6])
        )
    return lines


def _openapi_line(python: str, root: Path) -> str | None:
    if not (root / "openapi" / "openapi.json").is_file():
        return None
    rc, _ = common.run([python, "scripts/export_openapi.py", "--check"], timeout=60)
    if rc != 0:
        return (
            "- openapi: snapshot ALREADY drifts from the code before you changed anything -- "
            "CI is red on main. Run `python3 scripts/run_export_openapi.py` and commit it."
        )
    return None


def main() -> None:
    root = common.project_dir()
    python = common.project_python()

    lines = ["Macrova environment check (hook: session_health.py):", _python_line(python)]
    lines.append(_imports_line(python))
    lines += _data_lines(root)
    lines += _git_lines(root)

    openapi = _openapi_line(python, root)
    if openapi:
        lines.append(openapi)

    common.session_context("\n".join(lines))


if __name__ == "__main__":
    main()
