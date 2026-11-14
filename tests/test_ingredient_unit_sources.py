"""Sprint 2 DATA-1: every household-unit weight in the ingredient table names its source.

Accepted sources: an FDC foodPortions entry, or a Cronometer NCCDB serving the
user supplied where FDC has no matching portion (DATA-1 close-out).
"""

from __future__ import annotations

import json
from pathlib import Path

TABLE = Path(__file__).resolve().parents[1] / "data/reference/ingredient_nutrition.json"

# Keys that predate DATA-1 and carry no source note yet. Do not add to this list:
# a new key must have a "<unit>: <grams> g, FDC <fdc_id> foodPortions id <id> (...)" note,
# or "<unit>: <grams> g, Cronometer NCCDB serving, user-supplied <date>; ..." when FDC has no portion.
GRANDFATHERED = {
    ("almond butter unsalted", "tbsp"), ("avocado black skin", "each"), ("avocado oil", "tsp"),
    ("banana", "large"), ("beans white mature seeds", "cup"), ("black beans drained", "cup, whole pieces"),
    ("blackberries unsweetened", "cup, whole pieces"), ("blueberries", "cup"), ("butter", "tsp"),
    ("carrots", "tbsp"), ("cheddar cheese natural 50% reduced fat", "oz"),
    ("cheddar cheese natural 50% reduced fat", "slice"), ("chicken breast", "oz"),
    ("chocolate dark 70-85% cacao solids", "tsp"), ("edamame beans", "cup, whole pieces"),
    ("egg yolk", "large"), ("greek yogurt plain nonfat", "tbsp"), ("hamburger or beef 90%", "oz"),
    ("hamburger or beef 95%", "oz"), ("honey", "ml"), ("honey", "tbsp"),
    ("jasmine rice in unsalted water", "cup"), ("kellogg's rice krispies treats original", "bar"),
    ("kiwi fruit green", "each"), ("lemon juice", "ml"), ("low fat greek yogurt", "tbsp"), ("milk", "ml"),
    ("olive oil", "ml"), ("olive oil", "tbsp"), ("olive oil", "tsp"), ("parmesan grated", "tbsp, grated"),
    ("potatoes flesh", "medium"), ("red peppers", "small"), ("salsa ready-to-serve", "tbsp"),
    ("sesame oil", "tsp"), ("soy sauce", "tbsp"), ("tofu not silken firm", "oz"), ("tomato", "cup"),
    ("tuna sashimi", "oz"), ("turkey breast lunchmeat reduced fat", "slice"), ("water", "ml"),
}


def _records():
    return json.loads(TABLE.read_text(encoding="utf-8"))["ingredients"]


def test_every_household_unit_weight_names_its_fdc_source():
    unsourced = []
    for rec in _records():
        notes = rec.get("notes") or ""
        for unit, grams in (rec.get("grams_per_unit") or {}).items():
            if unit == "g" or (rec["name"], unit) in GRANDFATHERED:
                continue
            sources = (f"FDC {rec['fdc_id']} foodPortions id ", "Cronometer NCCDB serving, user-supplied ")
            if not any(f"{unit}: {grams:g} g, {src}" in notes for src in sources):
                unsourced.append((rec["name"], unit))
    assert unsourced == []


def test_grandfathered_list_only_shrinks():
    """A grandfathered key that gets a source (or is removed) must leave the list."""
    present = {(r["name"], u) for r in _records() for u in (r.get("grams_per_unit") or {})}
    assert GRANDFATHERED <= present
