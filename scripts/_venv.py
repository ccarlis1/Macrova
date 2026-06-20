"""Shared virtualenv helpers for project script runners."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = REPO_ROOT / ".venv"
REQS_FILE = REPO_ROOT / "requirements.txt"


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def print_remediation() -> None:
    print(
        "Install project dependencies with:\n\n"
        "  .venv/bin/python -m pip install -r requirements.txt\n",
        file=sys.stderr,
    )


def requirements_satisfied(vpy: Path) -> bool:
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


def ensure_venv() -> Path:
    vpy = venv_python()
    if vpy.exists():
        return vpy
    print("Creating .venv...")
    _run([sys.executable, "-m", "venv", str(VENV_DIR)])
    return vpy


def ensure_requirements_installed(vpy: Path | None = None) -> Path:
    vpy = vpy or ensure_venv()
    if requirements_satisfied(vpy):
        return vpy
    print("Installing dependencies from requirements.txt...")
    try:
        _run([str(vpy), "-m", "pip", "install", "--upgrade", "pip"])
        _run([str(vpy), "-m", "pip", "install", "-r", str(REQS_FILE)])
    except subprocess.CalledProcessError:
        print_remediation()
        raise
    if not requirements_satisfied(vpy):
        print("Project dependencies are still missing.", file=sys.stderr)
        print_remediation()
        raise SystemExit(1)
    return vpy
