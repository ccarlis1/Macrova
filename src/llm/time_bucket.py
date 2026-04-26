"""Helpers for mapping cooking time to canonical time tags."""
from __future__ import annotations

import os

from src.llm import tag_repository

_DEFAULT_TAG_REPO_PATH = "data/recipes/recipe_tags.json"


class TagRegistry:
    """Thin adapter that resolves canonical tags from the tag repository."""

    @staticmethod
    def resolve(slug: str) -> str:
        tag_repo_path = os.environ.get("NUTRITION_TAG_REPO_PATH", _DEFAULT_TAG_REPO_PATH)
        meta = tag_repository.resolve(slug, tag_repo_path)
        return meta.slug


def time_bucket(minutes: int) -> str:
    """Return canonical time-* slug for a cooking duration."""
    if minutes < 0:
        raise ValueError("minutes must be >= 0")
    if minutes == 0:
        slug = "time-0"
    elif minutes <= 5:
        slug = "time-1"
    elif minutes <= 15:
        slug = "time-2"
    elif minutes <= 30:
        slug = "time-3"
    else:
        slug = "time-4"
    return TagRegistry.resolve(slug)
