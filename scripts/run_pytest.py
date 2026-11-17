#!/usr/bin/env python3
"""Run pytest in a project-local virtual environment.

This script ensures `.venv` exists and has project dependencies installed,
then runs pytest via `python -m pytest` inside that environment. It is the
canonical backend test command (`make test` delegates here).

When changing it, keep these properties: safe to run from the repo root; uses
the intended `.venv`; fails clearly when dependencies are missing; never
silently falls back to another interpreter; verifies the project requirements,
not just that pytest is importable.
"""

from __future__ import annotations

import subprocess
import sys

from _venv import REPO_ROOT, ensure_requirements_installed, ensure_venv


def main() -> int:
    vpy = ensure_requirements_installed(ensure_venv())
    cmd = [str(vpy), "-m", "pytest", *sys.argv[1:]]
    completed = subprocess.run(cmd, cwd=REPO_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
