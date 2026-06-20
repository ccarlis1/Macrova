#!/usr/bin/env python3
"""Run OpenAPI export/check in a project-local virtual environment.

Ensures `.venv` exists with dependencies from requirements.txt, then runs
``scripts/export_openapi.py`` with the venv interpreter.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from _venv import REPO_ROOT, ensure_requirements_installed, ensure_venv

_EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export_openapi.py"


def main() -> int:
    vpy = ensure_requirements_installed(ensure_venv())
    cmd = [str(vpy), str(_EXPORT_SCRIPT), *sys.argv[1:]]
    completed = subprocess.run(cmd, cwd=REPO_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
