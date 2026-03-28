from __future__ import annotations

from typing import Any


USDA_CAPABLE_ATTR = "usda_capable"


class USDAProviderRequiredError(RuntimeError):
    """Raised when USDA-capable validation is required but not provided."""

    def __init__(self, *, message: str, provider_type: str | None = None) -> None:
        super().__init__(message)
        self.error_code = "USDA_PROVIDER_REQUIRED"
        self.provider_type = provider_type


def is_usda_capable_provider(provider: Any) -> bool:
    """Contract marker: provider must expose `usda_capable=True`."""

    return bool(getattr(provider, USDA_CAPABLE_ATTR, False))


def assert_usda_capable_provider(provider: Any) -> None:
    """Enforce USDA capability at validation boundaries."""

    if not is_usda_capable_provider(provider):
        provider_type = type(provider).__name__
        raise USDAProviderRequiredError(
            message=(
                "USDA_PROVIDER_REQUIRED: provider is not USDA-capable; "
                "use APIIngredientProvider (USDA-backed) for recipe validation."
            ),
            provider_type=provider_type,
        )

