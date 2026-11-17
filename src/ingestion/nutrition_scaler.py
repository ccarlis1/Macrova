"""Named serving weights for count-based units (e.g. "2 large eggs").

``BASE_SERVING_WEIGHTS`` is the only thing this module provides. It is read by
``src/nutrition/calculator.py`` when converting a count unit to grams. Units with
no entry stay unresolved -- there are no density guesses or silent fallbacks.
"""

from typing import Dict


# ============================================================================
# BASE SERVING WEIGHTS
# ============================================================================
#
# Common serving weights for count-based units.
# Format: unit -> {ingredient_context -> weight_in_grams}
#
# These are used when user specifies units like "2 large eggs"
# ============================================================================

BASE_SERVING_WEIGHTS: Dict[str, Dict[str, float]] = {
    "large": {
        "egg": 50.0,        # 1 large egg ≈ 50g
        "eggs": 50.0,       # Plural variant
        "banana": 118.0,    # 1 large banana ≈ 118g
        "apple": 182.0,     # 1 large apple ≈ 182g
        "orange": 184.0,    # 1 large orange ≈ 184g
        "potato": 299.0,    # 1 large potato ≈ 299g
        "tomato": 182.0,    # 1 large tomato ≈ 182g
        "avocado": 201.0,   # 1 large avocado ≈ 201g
        "onion": 150.0,     # 1 large onion ≈ 150g
    },
    "medium": {
        "egg": 44.0,        # 1 medium egg ≈ 44g
        "eggs": 44.0,
        "banana": 105.0,    # 1 medium banana ≈ 105g
        "apple": 138.0,     # 1 medium apple ≈ 138g
        "potato": 150.0,    # 1 medium potato ≈ 150g
    },
    "small": {
        "egg": 38.0,        # 1 small egg ≈ 38g
        "eggs": 38.0,
        "banana": 81.0,     # 1 small banana ≈ 81g
        "apple": 101.0,     # 1 small apple ≈ 101g
    },
    # Scoop and serving require explicit weight - no defaults
    "scoop": {},
    "serving": {},
}
