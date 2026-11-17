"""Helpers for mapping cooking time to canonical time tags."""
from __future__ import annotations

import os

from src.llm import tag_repository
from src.data_layer import user_data



class TagRegistry:
    """Thin adapter that resolves canonical tags from the tag repository."""

    @staticmethod
    def resolve(slug: str) -> str:
        tag_repo_path = os.environ.get("NUTRITION_TAG_REPO_PATH") or user_data.recipe_tags_path()
        meta = tag_repository.resolve(slug, tag_repo_path)
        return meta.slug


def time_bucket_slug(minutes: int) -> str:
    """Raw ``time-*`` slug for a cooking duration (the one mapping; not resolved)."""
    if minutes < 0:
        raise ValueError("minutes must be >= 0")
    if minutes == 0:
        return "time-0"
    if minutes <= 5:
        return "time-1"
    if minutes <= 15:
        return "time-2"
    if minutes <= 30:
        return "time-3"
    return "time-4"


def time_bucket(minutes: int) -> str:
    """Return canonical time-* slug for a cooking duration."""
    return TagRegistry.resolve(time_bucket_slug(minutes))


def deterministic_prep_time_bucket(cooking_time_minutes: int) -> str:
    """Effort bucket derived from the known cook time (mirrors planner busyness caps)."""
    m = int(cooking_time_minutes)
    if m <= 5:
        return "snack"
    if m <= 15:
        return "quick_meal"
    if m <= 30:
        return "weeknight_meal"
    return "meal_prep"
