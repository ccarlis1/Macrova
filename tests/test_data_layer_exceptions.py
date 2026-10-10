"""Tests for src/data_layer/exceptions.py."""

import pytest

from src.data_layer.exceptions import IngredientNotFoundError


def test_ingredient_not_found_error_carries_name_and_message():
    err = IngredientNotFoundError("cream of rice")

    assert err.ingredient_name == "cream of rice"
    assert "cream of rice" in str(err)
    assert "not found" in str(err)


def test_ingredient_not_found_error_is_raisable_and_catchable_as_exception():
    with pytest.raises(IngredientNotFoundError) as exc_info:
        raise IngredientNotFoundError("dragonfruit")

    assert isinstance(exc_info.value, Exception)
    assert exc_info.value.ingredient_name == "dragonfruit"
