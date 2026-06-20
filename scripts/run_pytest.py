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


def _print_remediation() -> None:
    print(
        "Install project dependencies with:\n\n"
        "  .venv/bin/python -m pip install -r requirements.txt\n",
        file=sys.stderr,
    )


def _requirements_satisfied(vpy: Path) -> bool:
    if not REQS_FILE.is_file():
        return True
    completed = subprocess.run(
        [str(vpy), "-m", "pip", "install", "-r", str(REQS_FILE), "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return False
    output = f"{completed.stdout}\n{completed.stderr}"
    return "Would install" not in output and "Collecting " not in output


def _ensure_venv() -> None:
    if _venv_python().exists():
        return
    print("Creating .venv...")
    _run([sys.executable, "-m", "venv", str(VENV_DIR)])


def _ensure_requirements_installed() -> None:
    vpy = _venv_python()
    if _requirements_satisfied(vpy):
        return
    print("Installing dependencies from requirements.txt...")
    try:
        _run([str(vpy), "-m", "pip", "install", "--upgrade", "pip"])
        _run([str(vpy), "-m", "pip", "install", "-r", str(REQS_FILE)])
    except subprocess.CalledProcessError:
        _print_remediation()
        raise
    if not _requirements_satisfied(vpy):
        print("Project dependencies are still missing.", file=sys.stderr)
        _print_remediation()
        raise SystemExit(1)


def main() -> int:
    _ensure_venv()
    _ensure_requirements_installed()
    vpy = _venv_python()
    cmd = [str(vpy), "-m", "pytest", *sys.argv[1:]]
    completed = subprocess.run(cmd, cwd=REPO_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
