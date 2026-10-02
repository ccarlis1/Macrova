#!/usr/bin/env python3
"""E0 — reproduce nutrition the way /api/v1/plan computes it.

Runs the matrix of recipe libraries × source configurations and writes
``results/e0.json``. No network access.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Allow running as ``python evaluation/data_track/reproduce.py`` from repo root.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evaluation.data_track.common import RESULTS_DIR, compute_library  # noqa: E402

CONFIGS = ("local-machine", "local-clean", "api-cache", "api-clean")
LIBRARIES = ("benchmark", "data_recipes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=RESULTS_DIR / "e0.json",
        help="Output path (default: evaluation/data_track/results/e0.json)",
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cells = []
    summaries = []

    with tempfile.TemporaryDirectory(prefix="data_track_api_clean_") as tmp:
        empty_cache = Path(tmp)
        for library in LIBRARIES:
            for config in CONFIGS:
                cache_dir = empty_cache if config == "api-clean" else None
                try:
                    cell = compute_library(library, config, cache_dir=cache_dir)
                except FileNotFoundError as exc:
                    cell = {
                        "summary": {
                            "library": library,
                            "config": config,
                            "error": str(exc),
                        },
                        "recipes": [],
                    }
                cells.append(cell)
                summaries.append(cell["summary"])
                s = cell["summary"]
                print(
                    f"{library:14} {config:14} "
                    f"recipes={s.get('n_recipes', 0):3} "
                    f"skips={s.get('recipes_with_any_skip', 'n/a')} "
                    f"kcal_med={s.get('kcal_abs_delta', {}).get('median')} "
                    f"resolve_err={bool(s.get('library_resolve_error'))}"
                )

    payload = {
        "experiment": "E0",
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "configs": list(CONFIGS),
        "libraries": list(LIBRARIES),
        "summaries": summaries,
        "cells": cells,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
