#!/usr/bin/env python3
"""Run pytest in a project-local virtual environment.

This script ensures `.venv` exists and has project dependencies installed,
then runs pytest via `python -m pytest` inside that environment.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = REPO_ROOT / ".venv"
REQS_FILE = REPO_ROOT / "requirements.txt"


def _venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def _ensure_venv() -> None:
    if _venv_python().exists():
        return
    print("Creating .venv...")
    _run([sys.executable, "-m", "venv", str(VENV_DIR)])


def _ensure_requirements_installed() -> None:
    vpy = _venv_python()
    try:
        _run([str(vpy), "-c", "import pytest"])
        return
    except subprocess.CalledProcessError:
        print("Installing dependencies from requirements.txt...")
        _run([str(vpy), "-m", "pip", "install", "--upgrade", "pip"])
        _run([str(vpy), "-m", "pip", "install", "-r", str(REQS_FILE)])


def main() -> int:
    _ensure_venv()
    _ensure_requirements_installed()
    vpy = _venv_python()
    cmd = [str(vpy), "-m", "pytest", *sys.argv[1:]]
    completed = subprocess.run(cmd, cwd=REPO_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
