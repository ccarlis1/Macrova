"""Tests for src/llm/types.py — validated-recipe persistence boundary types."""

import dataclasses

import pytest

from src.data_layer.models import Recipe
from src.llm.types import ValidatedRecipeForPersistence


def _recipe(recipe_id: str) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=f"Recipe {recipe_id}",
        ingredients=[],
        cooking_time_minutes=10,
        instructions=["step"],
    )


def test_wrapper_is_frozen():
    wrapped = ValidatedRecipeForPersistence(recipe=_recipe("r1"))

    with pytest.raises(dataclasses.FrozenInstanceError):
        wrapped.recipe = _recipe("r2")
