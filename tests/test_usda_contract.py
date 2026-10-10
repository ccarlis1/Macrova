"""Tests for src/llm/usda_contract.py — USDA-capable provider contract marker."""

import pytest

from src.llm.usda_contract import (
    USDAProviderRequiredError,
    assert_usda_capable_provider,
    is_usda_capable_provider,
)


class _PlainProvider:
    pass


class _CapableProvider:
    usda_capable = True


class _ExplicitlyIncapableProvider:
    usda_capable = False


def test_plain_object_is_not_usda_capable():
    assert is_usda_capable_provider(_PlainProvider()) is False
    assert is_usda_capable_provider(object()) is False


def test_marker_attribute_grants_capability():
    assert is_usda_capable_provider(_CapableProvider()) is True
    assert is_usda_capable_provider(_ExplicitlyIncapableProvider()) is False


def test_assert_raises_structured_error_for_incapable_provider():
    with pytest.raises(USDAProviderRequiredError) as exc_info:
        assert_usda_capable_provider(_PlainProvider())

    err = exc_info.value
    assert err.error_code == "USDA_PROVIDER_REQUIRED"
    assert err.provider_type == "_PlainProvider"
    assert "USDA_PROVIDER_REQUIRED" in str(err)


def test_assert_passes_for_capable_provider():
    assert_usda_capable_provider(_CapableProvider())


def test_api_ingredient_provider_carries_the_marker():
    from src.providers.api_provider import APIIngredientProvider

    assert APIIngredientProvider.usda_capable is True
