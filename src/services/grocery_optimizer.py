"""Spawn Node grocery-optimizer CLI (stdin JSON / stdout JSON)."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Sync with route expectations (5–30s typical; headroom for cold start).
_DEFAULT_TIMEOUT_SEC = 90

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GROCERY_RUN_JS = _REPO_ROOT / "packages" / "grocery-optimizer" / "dist" / "run.js"


def grocery_run_js_path() -> Path:
    """Resolved path to the Node entry script (for tests)."""

    return _GROCERY_RUN_JS


def run_grocery_optimizer(
    payload: Dict[str, Any],
    *,
    timeout_sec: int = _DEFAULT_TIMEOUT_SEC,
) -> Dict[str, Any]:
    """
    Run `node packages/grocery-optimizer/dist/run.js` with JSON on stdin.

    Returns a dict suitable for validating as ``GroceryOptimizeResponse``.
    On failure (missing binary, timeout, non-zero exit, invalid stdout JSON),
    returns ``{"schemaVersion": "1.0", "ok": False, "result": None, "error": {"message": ...}}``.
    """

    if not _GROCERY_RUN_JS.is_file():
        msg = f"Grocery optimizer CLI not built: missing {_GROCERY_RUN_JS}"
        logger.error("%s", msg)
        return {
            "schemaVersion": "1.0",
            "ok": False,
            "result": None,
            "error": {"message": msg},
        }

    stdin_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    logger.info(
        "grocery_optimizer: starting node (timeout=%ss, cwd=%s)",
        timeout_sec,
        _REPO_ROOT,
    )

    try:
        completed = subprocess.run(
            ["node", str(_GROCERY_RUN_JS)],
            input=stdin_bytes,
            capture_output=True,
            timeout=timeout_sec,
            cwd=str(_REPO_ROOT),
            check=False,
        )
    except subprocess.TimeoutExpired:
        msg = f"Grocery optimizer timed out after {timeout_sec}s"
        logger.error("%s", msg)
        return {
            "schemaVersion": "1.0",
            "ok": False,
            "result": None,
            "error": {"message": msg},
        }
    except OSError as exc:
        msg = f"Failed to spawn Node process: {exc}"
        logger.exception("grocery_optimizer: spawn failed")
        return {
            "schemaVersion": "1.0",
            "ok": False,
            "result": None,
            "error": {"message": msg},
        }

    stderr_text = (completed.stderr or b"").decode("utf-8", errors="replace").strip()
    if stderr_text:
        logger.warning("grocery_optimizer: stderr: %s", stderr_text)

    if completed.returncode != 0:
        msg = (
            f"Grocery optimizer exited with code {completed.returncode}"
            + (f": {stderr_text}" if stderr_text else "")
        )
        logger.error("%s", msg)
        return {
            "schemaVersion": "1.0",
            "ok": False,
            "result": None,
            "error": {"message": msg},
        }

    stdout_bytes = completed.stdout or b""
    try:
        text = stdout_bytes.decode("utf-8").strip()
        if not text:
            raise ValueError("empty stdout")
        out = json.loads(text)
        if not isinstance(out, dict):
            raise TypeError("stdout JSON must be an object")
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        msg = f"Invalid JSON from grocery optimizer: {exc}"
        logger.error("%s", msg)
        return {
            "schemaVersion": "1.0",
            "ok": False,
            "result": None,
            "error": {"message": msg},
        }

    logger.info("grocery_optimizer: node finished ok")
    return out
