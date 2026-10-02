#!/usr/bin/env python3
"""E1b — audit ``.cache/ingredients`` against the current NutrientMapper.

For each cache entry, remaps ``raw/<fdc_id>.json`` and classifies the entry as
``consistent`` or ``superseded``. Also flags quarantined and 0-kcal entries.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.ingestion.nutrient_mapper import MAPPER_VERSION, NutrientMapper  # noqa: E402

from evaluation.data_track.common import (  # noqa: E402
    BENCH_RECIPES_PATH,
    DEFAULT_CACHE_DIR,
    MICRO_FIELDS,
    RAW_DIR,
    RESULTS_DIR,
    mapped_nutrition_to_per_100g,
    nutrition_close,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "e1b.json")
    args = parser.parse_args()

    quarantine = {}
    if BENCH_RECIPES_PATH.exists():
        bench = json.loads(BENCH_RECIPES_PATH.read_text(encoding="utf-8"))
        quarantine = dict(bench.get("quarantined_cache_entries") or {})

    mapper = NutrientMapper()
    entries = []
    n_consistent = 0
    n_superseded = 0
    n_missing_raw = 0
    zero_kcal = []

    for path in sorted(args.cache_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        key = path.stem
        fdc_id = data.get("fdc_id")
        cached_nut = {
            "calories": float(data["nutrition"]["calories"]),
            "protein_g": float(data["nutrition"]["protein_g"]),
            "fat_g": float(data["nutrition"]["fat_g"]),
            "carbs_g": float(data["nutrition"]["carbs_g"]),
        }
        micros = data["nutrition"].get("micronutrients") or {}
        for mf in MICRO_FIELDS:
            cached_nut[mf] = float(micros.get(mf, 0.0))

        if cached_nut["calories"] == 0.0 and cached_nut["carbs_g"] > 0.1:
            zero_kcal.append(key)

        raw_path = RAW_DIR / f"{fdc_id}.json"
        if not raw_path.exists():
            n_missing_raw += 1
            entries.append(
                {
                    "cache_key": key,
                    "fdc_id": fdc_id,
                    "description": data.get("description"),
                    "status": "missing_raw",
                    "quarantined": key in quarantine,
                    "quarantine_note": quarantine.get(key),
                }
            )
            continue

        blob = json.loads(raw_path.read_text(encoding="utf-8"))
        raw_payload = blob.get("raw_payload") or blob
        remapped = mapped_nutrition_to_per_100g(mapper.map_nutrients(raw_payload))
        ok, diffs = nutrition_close(cached_nut, remapped)
        status = "consistent" if ok else "superseded"
        if ok:
            n_consistent += 1
        else:
            n_superseded += 1
        entries.append(
            {
                "cache_key": key,
                "fdc_id": fdc_id,
                "description": data.get("description"),
                "data_type": data.get("data_type"),
                "status": status,
                "diffs": diffs,
                "quarantined": key in quarantine,
                "quarantine_note": quarantine.get(key),
                "zero_kcal_with_carbs": key in zero_kcal,
                "mapper_version_current": MAPPER_VERSION,
                "provenance_mapper_version": (data.get("provenance") or {}).get(
                    "mapper_version"
                ),
            }
        )

    # Focus notes for salmon / egg yolk
    focus = {
        e["cache_key"]: e
        for e in entries
        if e["cache_key"] in ("salmon_canned", "egg_yolk")
    }

    n_total = len(entries)
    fraction_superseded = (n_superseded / n_total) if n_total else None
    recommendation = (
        "rebuild"
        if (fraction_superseded or 0) > 0.25
        else ("patch" if n_superseded > 0 else "keep")
    )

    payload = {
        "experiment": "E1b",
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "mapper_version": MAPPER_VERSION,
        "cache_dir": str(args.cache_dir),
        "summary": {
            "n_entries": n_total,
            "n_consistent": n_consistent,
            "n_superseded": n_superseded,
            "n_missing_raw": n_missing_raw,
            "fraction_superseded": fraction_superseded,
            "n_quarantined_present": sum(1 for e in entries if e.get("quarantined")),
            "zero_kcal_with_carbs_keys": zero_kcal,
            "recommendation": recommendation,
            "recommendation_reason": (
                "Rebuild if >25% superseded under current mapper; otherwise patch "
                "inconsistent entries and drop quarantined wrong-food keys."
            ),
            "salmon_egg_yolk": focus,
        },
        "entries": entries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2)[:2500])
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
