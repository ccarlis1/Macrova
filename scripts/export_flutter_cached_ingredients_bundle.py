#!/usr/bin/env python3
"""Merge `.cache/ingredients/*.json` into `frontend/assets/dev/cached_ingredients.json`.

Run from repo root after USDA lookups have populated the cache:
  python3 scripts/export_flutter_cached_ingredients_bundle.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".cache" / "ingredients"
OUT = ROOT / "frontend" / "assets" / "dev" / "cached_ingredients.json"


def main() -> None:
    if not CACHE_DIR.is_dir():
        print(f"No cache dir: {CACHE_DIR}", file=sys.stderr)
        sys.exit(1)

    items: list[dict] = []
    seen_fdc: set[int] = set()
    for path in sorted(CACHE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"Skip {path}: {e}", file=sys.stderr)
            continue
        fdc = data.get("fdc_id")
        if isinstance(fdc, int):
            if fdc in seen_fdc:
                continue
            seen_fdc.add(fdc)
        items.append(data)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"ingredients": items}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(items)} entries -> {OUT}")


if __name__ == "__main__":
    main()
