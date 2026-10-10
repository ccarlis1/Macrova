#!/usr/bin/env python3
"""Run pytest in a project-local virtual environment.

This script ensures `.venv` exists and has project dependencies installed,
then runs pytest via `python -m pytest` inside that environment.
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
