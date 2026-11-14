"""Sprint 2 BE-18: the committed list of ingredients allowed as `to taste`."""

import json

from src.nutrition.calculator import (
    DEFAULT_TO_TASTE_ALLOWED_PATH,
    TO_TASTE_CATEGORIES,
    is_to_taste_allowed,
    load_to_taste_allowed,
)


def test_every_entry_has_a_category_from_the_closed_set():
    data = json.load(open(DEFAULT_TO_TASTE_ALLOWED_PATH, encoding="utf-8"))
    assert set(data["categories"]) == set(TO_TASTE_CATEGORIES) == {"salt", "water", "spice", "herb"}
    for entry in data["ingredients"]:
        assert entry["category"] in TO_TASTE_CATEGORIES, entry
    assert load_to_taste_allowed()  # loads without raising


def test_covers_the_seasonings_in_committed_data():
    for name in ("salt", "pepper", "water", "cinnamon"):
        assert is_to_taste_allowed(name), name


def test_nutrient_bearing_ingredients_are_not_allowed():
    for name in ("rolled oats", "cherry tomatoes", "garlic"):
        assert not is_to_taste_allowed(name), name
