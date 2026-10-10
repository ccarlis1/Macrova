"""Tests for src/llm/types.py — validated-recipe persistence boundary types."""

import dataclasses

import pytest

from src.data_layer.models import Recipe
from src.llm.types import ValidatedRecipeForPersistence, from_validated_recipes


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


def test_from_validated_recipes_unwraps_in_order():
    recipes = [_recipe("a"), _recipe("b"), _recipe("c")]
    wrapped = [ValidatedRecipeForPersistence(recipe=r) for r in recipes]

    assert from_validated_recipes(wrapped) == recipes


def test_from_validated_recipes_empty_list():
    assert from_validated_recipes([]) == []
