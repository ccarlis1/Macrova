#!/usr/bin/env python3
"""Draft ``panel.json`` from the on-disk cache plus hand-chosen correct FDC IDs.

For non-quarantined ingredients, ``correct_fdc_id`` defaults to the cached ID
(still marked ``review_status: draft``). Quarantined / known-bad entries get
explicit SR Legacy / Foundation overrides. After ``fetch_raw.py``, run
``fill_panel_nutrition.py`` (or ``decompose.py --fill-panel``) to populate
``per_100g`` from remapped raw records.

``grams_per_unit`` covers units other than ``g`` / ``to taste`` that appear in
the two recipe libraries.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evaluation.data_track.common import (  # noqa: E402
    BENCH_RECIPES_PATH,
    DATA_RECIPES_PATH,
    DATA_TRACK,
    DEFAULT_CACHE_DIR,
    cache_key_for_name,
    collect_unique_ingredient_names,
    load_cache_entry,
)

# Hand-chosen correct FDC IDs for quarantined / known-wrong resolutions.
# Prefer SR Legacy or Foundation. Reviewer should confirm each match.
CORRECT_FDC_OVERRIDES: dict[str, dict] = {
    "oats": {
        "correct_fdc_id": 173904,
        "notes": "SR Legacy 'Oats'; not Oil, oat (173576).",
    },
    "eggs": {
        "correct_fdc_id": 171287,
        "notes": "SR Legacy 'Egg, whole, raw, fresh'; not Bread, egg.",
    },
    "bell pepper": {
        "correct_fdc_id": 170427,
        "notes": "SR Legacy 'Peppers, sweet, red, raw'; not TACO BELL Nachos.",
    },
    "red peppers": {
        "correct_fdc_id": 170427,
        "notes": "Same food as bell pepper (sweet red pepper).",
    },
    "chicken breast": {
        "correct_fdc_id": 171077,
        "notes": "SR Legacy raw breast meat only; not deli roll 174608.",
    },
    "cherry tomatoes": {
        "correct_fdc_id": 170457,
        "notes": "SR Legacy tomatoes raw (year-round avg); not cherries.",
    },
    "milk 1% fat lowfat": {
        "correct_fdc_id": 170872,
        "notes": "SR Legacy Milk, lowfat, fluid, 1% milkfat, with vitamins; not cottage cheese.",
    },
    "banana": {
        "correct_fdc_id": 173944,
        "notes": "SR Legacy bananas raw; not banana powder.",
    },
    "bananas": {
        "correct_fdc_id": 173944,
        "notes": "Plural alias of banana.",
    },
    "tortillas corn": {
        "correct_fdc_id": 175036,
        "notes": "SR Legacy Tortillas, ready-to-bake or -fry, corn; not flour tortillas (167535).",
    },
    "kiwi fruit green": {
        "correct_fdc_id": 168153,
        "notes": "SR Legacy green kiwifruit (has energy); replace Foundation 0-kcal entry.",
    },
    "mushrooms": {
        "correct_fdc_id": 169251,
        "notes": "SR Legacy white mushrooms; replace 0-kcal Foundation shiitake.",
    },
    "spaghetti squash": {
        "correct_fdc_id": 168454,
        "notes": "SR Legacy spaghetti squash raw; replace 0-kcal Foundation.",
    },
    "sweet potato": {
        "correct_fdc_id": 168482,
        "notes": "SR Legacy sweet potato raw; replace 0-kcal Foundation.",
    },
    "tomato": {
        "correct_fdc_id": 170457,
        "notes": "SR Legacy tomatoes raw; replace 0-kcal crushed canned Foundation.",
    },
    "acai berry": {
        "correct_fdc_id": 173175,
        "notes": (
            "No SR Legacy/Foundation acai fruit puree in FDC; only fortified "
            "beverages. Fruit ground-truth unavailable — resolution still "
            "flagged as beverage-not-fruit when reviewing by hand."
        ),
        "ground_truth_unavailable": True,
    },
    # Mapping disagreements flagged in reconciliation (salmon / egg yolk).
    "salmon canned": {
        "correct_fdc_id": 175174,
        "notes": "SR Legacy sockeye canned (matches cache fdc); mapping channel compares remap vs cache values.",
    },
    "egg yolk": {
        "correct_fdc_id": 172184,
        "notes": "SR Legacy egg yolk raw (matches cache fdc); mapping channel compares remap vs cache values.",
    },
}

# Approximate edible grams for volume/count units used in recipes.
# Densities: olive oil ≈ 0.91 g/ml; lemon juice ≈ 1.03; honey ≈ 1.42;
# yogurt ≈ 1.03 g/ml; tbsp yogurt ≈ 15 g; tbsp grated carrot ≈ 7 g;
# tsp chocolate ≈ 5 g; cup tomato (chopped) ≈ 180 g.
GRAMS_PER_UNIT: dict[tuple[str, str], float] = {
    ("olive oil", "ml"): 0.91,
    ("lemon juice", "ml"): 1.03,
    ("honey", "ml"): 1.42,
    ("avocado oil", "ml"): 0.91,
    ("sesame oil", "ml"): 0.92,
    ("soy sauce", "ml"): 1.15,
    ("milk", "ml"): 1.03,
    ("milk 1% fat lowfat", "ml"): 1.03,
    ("low fat greek yogurt", "tbsp"): 15.0,
    ("greek yogurt plain nonfat", "tbsp"): 15.0,
    ("carrots", "tbsp"): 7.0,
    ("chocolate dark 70-85% cacao solids", "tsp"): 5.0,
    ("tomato", "cup"): 180.0,
    ("banana", "large"): 118.0,
    ("bananas", "large"): 118.0,
    ("eggs", "large"): 50.0,
}


def _units_used() -> dict[str, set[str]]:
    units: dict[str, set[str]] = defaultdict(set)
    for path in (BENCH_RECIPES_PATH, DATA_RECIPES_PATH):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for recipe in data.get("recipes", []):
            for ing in recipe.get("ingredients", []):
                unit = ing.get("unit", "")
                if unit and unit != "to taste":
                    units[ing["name"]].add(unit)
    return units


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=DATA_TRACK / "panel.json"
    )
    args = parser.parse_args()

    names = collect_unique_ingredient_names()
    units_by_name = _units_used()
    quarantine = {}
    bench = json.loads(BENCH_RECIPES_PATH.read_text(encoding="utf-8"))
    quarantine = dict(bench.get("quarantined_cache_entries") or {})

    ingredients = []
    for name in names:
        key = cache_key_for_name(name)
        cached = load_cache_entry(name, DEFAULT_CACHE_DIR)
        override = CORRECT_FDC_OVERRIDES.get(name, {})
        cached_fdc = cached.get("fdc_id") if cached else None
        correct_fdc = override.get("correct_fdc_id", cached_fdc)
        grams_per_unit = {}
        for unit in sorted(units_by_name.get(name, [])):
            if unit == "g":
                grams_per_unit["g"] = 1.0
                continue
            if unit == "oz":
                grams_per_unit["oz"] = 28.35
                continue
            gp = GRAMS_PER_UNIT.get((name, unit))
            if gp is not None:
                grams_per_unit[unit] = gp

        entry = {
            "name": name,
            "cache_key": key,
            "cached_fdc_id": cached_fdc,
            "cached_description": cached.get("description") if cached else None,
            "correct_fdc_id": correct_fdc,
            "description": None,  # filled after fetch from correct raw
            "per_100g": None,  # filled after fetch
            "grams_per_unit": grams_per_unit,
            "quarantined": key in quarantine or name.replace(" ", "_") in quarantine,
            "quarantine_note": quarantine.get(key) or quarantine.get(name.replace(" ", "_")),
            "override_applied": name in CORRECT_FDC_OVERRIDES,
            "ground_truth_unavailable": bool(override.get("ground_truth_unavailable")),
            "notes": override.get("notes", ""),
            "review_status": "draft",
            "reviewed_by": None,
        }
        ingredients.append(entry)

    payload = {
        "schema_version": 1,
        "experiment": "E1",
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "review_status": "draft",
        "notes": (
            "Draft panel. correct_fdc_id overrides are hand-chosen candidates; "
            "per_100g is filled from remapped raw USDA after fetch_raw.py. "
            "Human review required before treating as ground truth."
        ),
        "n_ingredients": len(ingredients),
        "ingredients": ingredients,
    }
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    n_override = sum(1 for i in ingredients if i["override_applied"])
    print(f"Wrote {args.out} with {len(ingredients)} ingredients ({n_override} overrides)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
