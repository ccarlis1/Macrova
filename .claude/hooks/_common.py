"""Shared plumbing for the Macrova Claude Code hooks.

Contract for every hook in this directory:

* stdin carries exactly one JSON event object; :func:`read_event` never raises.
* Only the Python standard library may be imported, because a hook runs in
  whatever shell Claude Code happens to hand it -- no activated venv, no
  ``PYTHONPATH``, no network.
* A hook never mutates a tracked file. The only writes permitted are under
  ``.claude/.hook-state/`` (gitignored scratch state).
* Exit codes: ``0`` allows/stays quiet, ``2`` blocks and feeds stderr back to
  Claude as the reason. Any other code is a hook bug and Claude Code treats it
  as non-blocking -- so hooks fail open, never closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

# CI pins Python 3.11 (.github/workflows/ci.yml); anything else locally is drift
# worth surfacing, not worth failing on.
CI_PYTHON = "3.11"


# --------------------------------------------------------------------- event input


def read_event() -> dict[str, Any]:
    """Return the hook event object, or ``{}`` when stdin is empty or unparseable."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def tool_input(event: dict[str, Any]) -> dict[str, Any]:
    """Return the event's ``tool_input`` mapping, or ``{}``."""
    value = event.get("tool_input")
    return value if isinstance(value, dict) else {}


_PATH_KEYS = ("file_path", "notebook_path", "path")


def edited_paths(event: dict[str, Any]) -> list[str]:
    """Repo-relative paths a Write/Edit/NotebookEdit event would touch, in order."""
    data = tool_input(event)
    out: list[str] = []
    for key in _PATH_KEYS:
        rel = repo_relative(data.get(key))
        if rel and rel not in out:
            out.append(rel)
    return out


# ------------------------------------------------------------------------- paths


def project_dir() -> Path:
    """Repo root: ``$CLAUDE_PROJECT_DIR`` when set, else two levels above this file."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        try:
            return Path(env).resolve()
        except OSError:
            pass
    return Path(__file__).resolve().parents[2]


def repo_relative(path: Any) -> str | None:
    """POSIX path relative to the repo root, or ``None`` if empty or outside it."""
    if not path or not isinstance(path, (str, os.PathLike)):
        return None
    root = project_dir()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return None


def under(path: str, *prefixes: str) -> bool:
    """True when *path* is, or sits inside, any of *prefixes* (directory-aware)."""
    normalized = path.rstrip("/")
    for prefix in prefixes:
        base = prefix.rstrip("/")
        if normalized == base or normalized.startswith(base + "/"):
            return True
    return False


# --------------------------------------------------------------------- decisions


def _emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def pre_tool_decision(decision: str, reason: str) -> None:
    """Emit a PreToolUse permission decision (``deny``/``ask``/``allow``) and exit."""
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        }
    )
    sys.exit(0)


def deny(reason: str) -> None:
    """Refuse the tool call outright."""
    pre_tool_decision("deny", reason)


def ask(reason: str) -> None:
    """Escalate the tool call to the user, even under auto-approve permissions."""
    pre_tool_decision("ask", reason)


def block(reason: str) -> None:
    """Block a PostToolUse call; stderr becomes the reason Claude sees."""
    sys.stderr.write(reason.rstrip() + "\n")
    sys.exit(2)


def stop_block(reason: str) -> None:
    """Refuse to let the turn end; Claude must keep working on *reason*."""
    _emit({"decision": "block", "reason": reason.rstrip()})
    sys.exit(0)


def session_context(text: str) -> None:
    """Inject *text* into the session's context at SessionStart."""
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": text.rstrip(),
            }
        }
    )
    sys.exit(0)


def ok(message: str = "") -> None:
    """Allow, optionally leaving *message* in the transcript."""
    if message:
        sys.stdout.write(message.rstrip() + "\n")
    sys.exit(0)


# ------------------------------------------------------------------------- state


def state_dir() -> Path:
    """The gitignored scratch directory, created on demand."""
    directory = project_dir() / ".claude" / ".hook-state"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_state(name: str) -> dict[str, Any]:
    """Load a JSON state file, returning ``{}`` when absent or corrupt."""
    try:
        data = json.loads((state_dir() / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_state(name: str, data: dict[str, Any]) -> None:
    """Persist a JSON state file; failures are swallowed so hooks never break work."""
    try:
        (state_dir() / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (OSError, TypeError):
        pass


# --------------------------------------------------------------------- subprocess


def project_python() -> str:
    """Prefer the repo venv interpreter -- a hook must not assume an activated venv."""
    candidate = project_dir() / ".venv" / "bin" / "python"
    if candidate.is_file():
        return str(candidate)
    return sys.executable or "python3"


def run(
    cmd: Sequence[str],
    timeout: int = 120,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run *cmd* from the repo root; return ``(returncode, stdout + stderr)``.

    Guarantees a placeholder ``USDA_API_KEY`` (as CI does) so contract and test
    commands never depend on a real credential, and never raises.
    """
    env = os.environ.copy()
    env.setdefault("USDA_API_KEY", "hook-local-check-key")
    if extra_env:
        env.update(extra_env)
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(cwd or project_dir()),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s: {' '.join(cmd)}"
    except OSError as exc:
        return 127, f"could not run {' '.join(cmd)}: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ----------------------------------------------------------------------- git view


def dirty_paths() -> list[str]:
    """Repo-relative paths with uncommitted changes, tracked or untracked.

    Untracked directories are reported by git with a trailing slash; callers
    should treat entries as prefixes rather than files.
    """
    rc, out = run(["git", "status", "--porcelain", "-z"], timeout=20)
    if rc != 0:
        return []
    paths: list[str] = []
    fields = out.split("\0")
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if status[0] in ("R", "C"):
            index += 1  # rename/copy source follows as its own NUL-terminated field
        paths.append(path)
    return paths


def git_show(revision_path: str) -> str | None:
    """Return blob contents at ``HEAD:path``-style *revision_path*, or ``None``."""
    rc, out = run(["git", "show", revision_path], timeout=20)
    return out if rc == 0 else None


# ---------------------------------------------------------------------- hashing


def hash_paths(paths: Iterable[str]) -> str:
    """Stable digest of the given repo-relative paths and their current contents."""
    digest = hashlib.sha256()
    root = project_dir()
    for rel in sorted(paths):
        digest.update(rel.encode("utf-8"))
        target = root / rel
        try:
            if target.is_dir():
                for child in sorted(p for p in target.rglob("*") if p.is_file()):
                    digest.update(str(child).encode("utf-8"))
                    digest.update(hashlib.sha256(child.read_bytes()).digest())
            else:
                digest.update(hashlib.sha256(target.read_bytes()).digest())
        except OSError:
            digest.update(b"<unreadable>")
    return digest.hexdigest()
