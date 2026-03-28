from __future__ import annotations

from typing import Any, Dict, List

from src.data_layer.models import Recipe
from src.llm.schemas import RecipeTagsJson
from src.llm.tag_filter import filter_recipe_ids_by_preferences


def apply_tag_filtering(
    *,
    recipes: List[Recipe],
    tags_by_id: Dict[str, RecipeTagsJson | None],
    preferences: Dict[str, Any],
) -> List[Recipe]:
    """Apply deterministic tag-based recipe filtering.

    Requirements enforced:
    - Deterministic behavior.
    - Stable output ordering preserves `recipes` input order.
    - Fallback to full pool when:
      - no preferences are provided
      - tag metadata is missing (treated as "no tags present")
      - filtering results in an empty set
    - Supports OR-union across multiple cuisine preferences.
    """

    if not recipes:
        return recipes

    if not preferences:
        return list(recipes)

    cuisine_pref = preferences.get("cuisine")

    if isinstance(cuisine_pref, list) and cuisine_pref:
        accepted_ids: List[str] = []
        for single_cuisine in cuisine_pref:
            single_prefs = dict(preferences)
            single_prefs["cuisine"] = single_cuisine
            accepted_ids_for_cuisine = filter_recipe_ids_by_preferences(
                tags_by_id,
                preferences=single_prefs,
            )
            accepted_ids.extend(accepted_ids_for_cuisine)
        accepted_ids_set = set(accepted_ids)
    else:
        filtered_ids = filter_recipe_ids_by_preferences(
            tags_by_id,
            preferences=preferences,
        )
        accepted_ids_set = set(filtered_ids)

    if not accepted_ids_set:
        # REQUIRED fallback: if filtering returns empty, use full pool.
        return list(recipes)

    filtered_recipes = [
        r for r in recipes if getattr(r, "id", None) in accepted_ids_set
    ]
    return filtered_recipes

