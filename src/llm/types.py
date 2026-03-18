from __future__ import annotations

from dataclasses import dataclass
from typing import List

from src.data_layer.models import Recipe


@dataclass(frozen=True)
class ValidatedRecipeForPersistence:
    """Validated recipe wrapper.

    Invariant: only recipes produced by the LLM validation pipeline may be wrapped
    and persisted. The persistence boundary accepts this type only.
    """

    recipe: Recipe


def from_validated_recipes(wrapped: List[ValidatedRecipeForPersistence]) -> List[Recipe]:
    """Adapter for legacy/internal code that expects raw `Recipe` objects."""
    return [w.recipe for w in wrapped]

