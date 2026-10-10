#!/usr/bin/env python3
"""Fill panel.json description + per_100g from remapped raw/<correct_fdc_id>.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.ingestion.nutrient_mapper import NutrientMapper  # noqa: E402

from evaluation.data_track.common import (  # noqa: E402
    DATA_TRACK,
    RAW_DIR,
    mapped_nutrition_to_per_100g,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=DATA_TRACK / "panel.json")
    args = parser.parse_args()

    panel = json.loads(args.panel.read_text(encoding="utf-8"))
    mapper = NutrientMapper()
    filled = 0
    missing = []

    for entry in panel["ingredients"]:
        fdc = entry.get("correct_fdc_id")
        if not fdc:
            missing.append(entry["name"])
            continue
        raw_path = RAW_DIR / f"{fdc}.json"
        if not raw_path.exists():
            missing.append(f"{entry['name']} (fdc {fdc})")
            continue
        blob = json.loads(raw_path.read_text(encoding="utf-8"))
        raw_payload = blob.get("raw_payload") or blob
        mapped = mapper.map_nutrients(raw_payload)
        entry["description"] = blob.get("description") or raw_payload.get("description")
        entry["data_type"] = blob.get("dataType") or raw_payload.get("dataType")
        entry["per_100g"] = mapped_nutrition_to_per_100g(mapped)
        filled += 1

    args.panel.write_text(json.dumps(panel, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Filled {filled}/{len(panel['ingredients'])}; missing={len(missing)}")
    if missing:
        print("Missing raw for:", ", ".join(missing[:20]))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
