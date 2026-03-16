#!/usr/bin/env python3
"""Load missed-ingredient FDC IDs into the ingredient cache.

Reads (fdc_id, canonical_name) pairs from docs/RECIPE_CORPUS_PIPELINE_REPORT.md
(Missed Ingredients section), fetches each from the USDA API, maps nutrients,
and writes a cache entry to .cache/ingredients/.

Requires: USDA_API_KEY in environment (or .env). Run from project root.

Usage:
    python scripts/load_missed_ingredients_cache.py
"""

import os
import re
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env if present (no extra dependency)
_env_file = ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from src.ingestion.ingredient_cache import IngredientCache, CacheEntry
from src.ingestion.usda_client import USDAClient
from src.ingestion.nutrient_mapper import NutrientMapper


# Fallback: if report parsing fails, use this list (from Missed Ingredients tab)
MISSED_INGREDIENTS = [
    (2346404, "sweet potato"),
    (2727579, "spaghetti squash"),
    (169279, "sauerkraut"),
    (174278, "soy sauce"),
    (168462, "spinach"),
    (173573, "avocado oil"),
    (169736, "pasta"),
    (171711, "blueberries"),
    (172184, "egg yolk"),
    (170567, "almonds"),
    (175174, "salmon canned"),
    (171247, "parmesan grated"),
]


def parse_missed_ingredients_from_report() -> list[tuple[int, str]]:
    """Parse (fdc_id, canonical_name) from RECIPE_CORPUS_PIPELINE_REPORT.md."""
    report_path = ROOT / "docs" / "RECIPE_CORPUS_PIPELINE_REPORT.md"
    if not report_path.exists():
        return []
    text = report_path.read_text()
    # Section: "### Missed Ingredients" then lines like "- 2346404 sweet potato"
    in_section = False
    pairs = []
    for line in text.splitlines():
        if line.strip() == "### Missed Ingredients":
            in_section = True
            continue
        if in_section:
            if line.strip().startswith("## ") or (line.strip().startswith("### ") and "Missed" not in line):
                break
            m = re.match(r"^-\s*(\d+)\s+(.+)$", line.strip())
            if m:
                fdc_id = int(m.group(1))
                canonical_name = m.group(2).strip().lower()
                pairs.append((fdc_id, canonical_name))
    return pairs if pairs else []


def main() -> None:
    pairs = parse_missed_ingredients_from_report()
    if not pairs:
        pairs = MISSED_INGREDIENTS
        print("Using embedded missed-ingredients list.")
    else:
        print(f"Parsed {len(pairs)} missed ingredients from report.")

    try:
        client = USDAClient.from_env()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    cache = IngredientCache()
    mapper = NutrientMapper()

    for fdc_id, canonical_name in pairs:
        if cache.has(canonical_name):
            print(f"Skip (cached): {canonical_name} (FDC {fdc_id})")
            continue
        result = client.get_food_details(fdc_id)
        if not result.success:
            print(f"Fail: {canonical_name} (FDC {fdc_id}) — {result.error_code}: {result.error_message}")
            continue
        raw = result.raw_payload
        nutrition = mapper.map_nutrients(raw)
        description = raw.get("description", "")
        data_type = raw.get("dataType", "") or raw.get("foodType", "")
        entry = CacheEntry(
            canonical_name=canonical_name,
            fdc_id=fdc_id,
            description=description,
            data_type=data_type,
            nutrition=nutrition,
        )
        cache.write(entry)
        print(f"Cached: {canonical_name} (FDC {fdc_id})")

    print("Done.")


if __name__ == "__main__":
    main()
