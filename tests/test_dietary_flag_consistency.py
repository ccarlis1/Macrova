"""Dietary-flag tags must be consistent with recipe ingredients (F9c)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.planning.allergens import (
    VEGAN_EXCLUDED_INGREDIENTS,
    VEGETARIAN_EXCLUDED_INGREDIENTS,
    dietary_flag_violations,
)

_REPO = Path(__file__).resolve().parents[1]
_FLAG_KEYS = {"gluten_free", "dairy_free", "vegetarian", "vegan"}


def _flags_from_tag_entry(entry: dict) -> set[str]:
    flags: set[str] = set()
    for f in entry.get("dietary_flags") or []:
        flags.add(str(f).strip().lower().replace("-", "_"))
    by_type = entry.get("tag_slugs_by_type") or {}
    for slug in by_type.get("constraint") or []:
        key = str(slug).strip().lower().replace("-", "_")
        if key in _FLAG_KEYS:
            flags.add(key)
    return flags


def _ingredient_names_from_recipe(recipe: dict) -> list[str]:
    names: list[str] = []
    for ing in recipe.get("ingredients") or []:
        if isinstance(ing, dict):
            names.append(str(ing.get("name") or ""))
        else:
            names.append(str(ing))
    return names


def test_dietary_flag_consistency_over_committed_and_benchmark_libraries():
    """Every gluten_free/dairy_free/vegetarian/vegan tag must match ingredients.

    MB-146's data-hazard recipe is an intentional counter-example and must appear
    in the violation list (lying gluten-free tag + sourdough bread).
    """
    tag_paths = [
        _REPO / "data" / "recipes" / "recipe_tags.json",
        _REPO / "evaluation" / "benchmark" / "recipe_tags.json",
    ]
    recipe_paths = [
        _REPO / "data" / "recipes" / "recipes.json",
        _REPO / "evaluation" / "benchmark" / "recipes.json",
    ]

    recipes_by_id: dict[str, dict] = {}
    for path in recipe_paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        items = payload.get("recipes", payload if isinstance(payload, list) else [])
        for recipe in items:
            recipes_by_id[str(recipe["id"])] = recipe

    violations: list[str] = []
    for path in tag_paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        tags_by_id = payload.get("tags_by_id") or {}
        for rid, entry in tags_by_id.items():
            recipe = recipes_by_id.get(str(rid))
            if recipe is None:
                continue
            names = _ingredient_names_from_recipe(recipe)
            for flag in sorted(_flags_from_tag_entry(entry)):
                hits = dietary_flag_violations(flag, names)
                if hits:
                    violations.append(f"{rid}:{flag}:{','.join(hits)}")

    assert any(
        v.startswith("dh_veggie_egg_scramble:gluten_free:") for v in violations
    ), f"Expected MB-146 hazard to be flagged; got {violations[:20]}"

    unexpected = [
        v
        for v in violations
        if not v.startswith("dh_veggie_egg_scramble:")
    ]
    assert not unexpected, "Unexpected dietary-flag inconsistencies:\n" + "\n".join(
        unexpected[:40]
    )


_MEAT_WORDS = re.compile(
    r"chicken|beef|pork|turkey|bacon|\bham\b|salami|sausage|lamb|steak|jerky|fish|salmon|tuna|"
    r"tilapia|\bcod\b|shrimp|prawn|crab|lobster|anchov|sardine|pepperoni|prosciutto|gelatin|"
    r"lunchmeat|veal|duck"
)
_ANIMAL_WORDS = re.compile(
    r"egg|milk|cheese|yogurt|whey|butter|cream|casein|honey|ghee|kefir|mayonnaise|parmesan|feta|"
    r"cheddar|mozzarella|ricotta"
)
# Names that match a keyword above but are not animal products (or are an open spec question).
_NOT_ANIMAL = {
    "almond butter unsalted": "plant nut butter",
    "peanut butter": "plant nut butter",
    "cream of rice dry": "rice cereal",
}


def _all_committed_ingredient_names() -> set[str]:
    names: set[str] = set()
    for path in (_REPO / "data/recipes/recipes.json", _REPO / "evaluation/benchmark/recipes.json"):
        payload = json.loads(path.read_text())
        for recipe in payload.get("recipes", payload if isinstance(payload, list) else []):
            names.update(n.strip().lower() for n in _ingredient_names_from_recipe(recipe))
    return names


def test_vegetarian_and_vegan_lists_cover_committed_animal_ingredients():
    """The animal-product lists are closed; a new meat/dairy/egg ingredient must be added to them.

    Without this, a recipe with e.g. 'chicken thigh skin removed' passes a vegetarian flag.
    """
    names = _all_committed_ingredient_names()
    missing_veg = sorted(n for n in names if _MEAT_WORDS.search(n) and n not in VEGETARIAN_EXCLUDED_INGREDIENTS)
    missing_vegan = sorted(
        n
        for n in names
        if (_MEAT_WORDS.search(n) or _ANIMAL_WORDS.search(n))
        and n not in VEGAN_EXCLUDED_INGREDIENTS
        and n not in _NOT_ANIMAL
    )
    assert not missing_veg, f"add to VEGETARIAN_EXCLUDED_INGREDIENTS: {missing_veg}"
    assert not missing_vegan, f"add to VEGAN_EXCLUDED_INGREDIENTS (or _NOT_ANIMAL with a reason): {missing_vegan}"
