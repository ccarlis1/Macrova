#!/usr/bin/env python3
"""Load a list of FDC IDs into the ingredient cache.

Takes a hard-coded list of (fdc_id, canonical_name) pairs in this script,
fetches each from the USDA API, maps nutrients, and writes a cache entry
to .cache/ingredients/.

Requires: USDA_API_KEY in environment (or .env). Run from project root.

Usage:
    python scripts/load_missed_ingredients_cache.py
"""

import os
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


# List of (fdc_id, canonical_name) pairs to load.
# Edit this list as needed and re-run the script.
FDC_INGREDIENTS = [
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
    (2685581, "tomato"),
]


def main() -> None:
    pairs = FDC_INGREDIENTS
    print(f"Loading {len(pairs)} FDC ingredients from in-script list.")

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
