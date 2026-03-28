from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from src.llm.schemas import (
    BudgetLevel,
    DietaryFlag,
    PrepTimeBucket,
    RecipeTagsJson,
)


def _normalize_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s.lower() if s else None
    return str(v).strip().lower() or None


def _normalize_str_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        out: List[str] = []
        for item in v:
            s = _normalize_str(item)
            if s:
                out.append(s)
        return out
    s = _normalize_str(v)
    return [s] if s else []


def _tag_as_set(values: Iterable[Any]) -> Set[str]:
    out: Set[str] = set()
    for v in values:
        if hasattr(v, "value"):
            out.add(str(v.value).lower())
        else:
            s = _normalize_str(v)
            if s:
                out.add(s)
    return out


def _get_required_constraints(preferences: Dict[str, Any]) -> Dict[str, Any]:
    # Only consider known constraint keys; ignore everything else.
    constraints: Dict[str, Any] = {}

    if "cuisine" in preferences:
        constraints["cuisine"] = _normalize_str(preferences.get("cuisine"))

    if "cost_level" in preferences:
        constraints["cost_level"] = _normalize_str(preferences.get("cost_level"))

    if "prep_time_bucket" in preferences:
        constraints["prep_time_bucket"] = _normalize_str(
            preferences.get("prep_time_bucket")
        )

    # Support either explicit `dietary_flags` or shorthand `diet`.
    diet_flags = None
    if "dietary_flags" in preferences:
        diet_flags = preferences.get("dietary_flags")
    elif "diet" in preferences:
        diet_flags = preferences.get("diet")

    required_flags = _normalize_str_list(diet_flags)
    if required_flags:
        constraints["dietary_flags"] = required_flags

    # Drop empty / None constraints.
    return {k: v for k, v in constraints.items() if v is not None}


def _matches_constraints(tags: RecipeTagsJson | None, constraints: Dict[str, Any]) -> bool:
    if tags is None:
        return False

    if "cuisine" in constraints:
        if _normalize_str(tags.cuisine) != constraints["cuisine"]:
            return False

    if "cost_level" in constraints:
        tag_cost = (
            tags.cost_level.value if isinstance(tags.cost_level, BudgetLevel) else tags.cost_level
        )
        if _normalize_str(tag_cost) != constraints["cost_level"]:
            return False

    if "prep_time_bucket" in constraints:
        tag_bucket = (
            tags.prep_time_bucket.value
            if isinstance(tags.prep_time_bucket, PrepTimeBucket)
            else tags.prep_time_bucket
        )
        if _normalize_str(tag_bucket) != constraints["prep_time_bucket"]:
            return False

    if "dietary_flags" in constraints:
        required_flags: List[str] = list(constraints["dietary_flags"])
        tag_flags = _tag_as_set(tags.dietary_flags or [])
        if not set(required_flags).issubset(tag_flags):
            return False

    return True


def filter_recipe_ids_by_preferences(
    tags_by_id: Dict[str, RecipeTagsJson | None],
    preferences: Dict[str, Any],
) -> List[str]:
    """Filter recipe ids deterministically based on strict tag metadata.

    Rules:
    - Output ordering preserves `tags_by_id` insertion order.
    - Unknown preference fields are ignored.
    - If all recipes have missing tags (values are None), fallback returns all ids.
    """

    recipe_ids = list(tags_by_id.keys())
    if not recipe_ids:
        return []

    constraints = _get_required_constraints(preferences or {})
    if not constraints:
        return recipe_ids

    any_tags_present = any(v is not None for v in tags_by_id.values())
    if not any_tags_present:
        return recipe_ids

    accepted: List[str] = []
    for recipe_id in recipe_ids:
        tags = tags_by_id.get(recipe_id)
        if _matches_constraints(tags, constraints):
            accepted.append(recipe_id)
    return accepted

