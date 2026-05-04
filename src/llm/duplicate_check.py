from __future__ import annotations

import os
from typing import List, Optional

from rapidfuzz import fuzz

from src.data_layer.models import Recipe

DEFAULT_DUPLICATE_THRESHOLD = 0.85
THRESHOLD_ENV_VAR = "DUPLICATE_THRESHOLD"


def _duplicate_threshold() -> float:
    raw_value = os.environ.get(THRESHOLD_ENV_VAR)
    if raw_value is None:
        return DEFAULT_DUPLICATE_THRESHOLD

    try:
        return float(raw_value)
    except ValueError:
        return DEFAULT_DUPLICATE_THRESHOLD


def find_duplicate(name: str, recipes: List[Recipe]) -> Optional[Recipe]:
    threshold = _duplicate_threshold()
    candidate_name = name.lower()

    for recipe in recipes:
        similarity = fuzz.token_sort_ratio(candidate_name, recipe.name.lower()) / 100.0
        if similarity >= threshold:
            return recipe

    return None
