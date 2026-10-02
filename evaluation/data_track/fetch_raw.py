#!/usr/bin/env python3
"""Fetch raw USDA FoodData Central records by FDC ID into ``raw/``.

Needs network and ``USDA_API_KEY`` (loaded from repo-root ``.env``).
IDs come from:
  - every entry under ``.cache/ingredients/``
  - ``panel.json`` correct_fdc_id / cached_fdc_id when present
  - optional ``--ids`` / ``--ids-file``

Skips IDs that already have ``raw/<fdc_id>.json`` unless ``--force``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

# Load .env the same way the API/CLI do.
try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

from evaluation.data_track.common import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    RAW_DIR,
    DATA_TRACK,
)


def _collect_ids_from_cache(cache_dir: Path) -> set[int]:
    ids: set[int] = set()
    if not cache_dir.exists():
        return ids
    for path in cache_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        fdc = data.get("fdc_id")
        if isinstance(fdc, int) and fdc > 0:
            ids.add(fdc)
    return ids


def _collect_ids_from_panel(panel_path: Path) -> set[int]:
    ids: set[int] = set()
    if not panel_path.exists():
        return ids
    panel = json.loads(panel_path.read_text(encoding="utf-8"))
    for entry in panel.get("ingredients", []):
        for key in ("correct_fdc_id", "cached_fdc_id"):
            fdc = entry.get(key)
            if isinstance(fdc, int) and fdc > 0:
                ids.add(fdc)
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Refetch even if raw file exists")
    parser.add_argument("--ids", type=int, nargs="*", default=[], help="Extra FDC IDs")
    parser.add_argument("--ids-file", type=Path, help="JSON list of FDC IDs")
    parser.add_argument("--sleep", type=float, default=0.35, help="Delay between requests")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--panel", type=Path, default=DATA_TRACK / "panel.json")
    args = parser.parse_args()

    ids: set[int] = set()
    ids |= _collect_ids_from_cache(args.cache_dir)
    ids |= _collect_ids_from_panel(args.panel)
    ids |= set(args.ids or [])
    if args.ids_file and args.ids_file.exists():
        extra = json.loads(args.ids_file.read_text(encoding="utf-8"))
        ids |= {int(x) for x in extra}

    if not ids:
        print("No FDC IDs to fetch.", file=sys.stderr)
        return 1

    from src.ingestion.usda_client import USDAClient

    client = USDAClient.from_env()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    ordered = sorted(ids)
    print(f"Fetching up to {len(ordered)} FDC IDs into {RAW_DIR}")
    fetched = 0
    skipped = 0
    failed: list[dict] = []

    for fdc_id in ordered:
        out = RAW_DIR / f"{fdc_id}.json"
        if out.exists() and not args.force:
            skipped += 1
            continue
        details = client.get_food_details(fdc_id)
        if not details.success:
            failed.append(
                {
                    "fdc_id": fdc_id,
                    "error_code": details.error_code,
                    "error_message": details.error_message,
                }
            )
            print(f"FAIL {fdc_id}: {details.error_message}")
            time.sleep(args.sleep)
            continue
        payload = {
            "fdc_id": fdc_id,
            "description": details.raw_payload.get("description"),
            "dataType": details.raw_payload.get("dataType"),
            "raw_payload": details.raw_payload,
        }
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        fetched += 1
        print(f"OK   {fdc_id} {payload.get('description')}")
        time.sleep(args.sleep)

    summary = {
        "requested": len(ordered),
        "fetched": fetched,
        "skipped_existing": skipped,
        "failed": failed,
    }
    summary_path = RAW_DIR / "_fetch_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
