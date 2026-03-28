from __future__ import annotations

import json
from typing import Any, Dict, List

from src.data_layer.models import Recipe
from src.llm.client import LLMClient
from src.llm.schemas import RecipeTagsJson, ValidationFailure, parse_llm_json


class RecipeTaggingError(Exception):
    """Deterministic error raised when recipe tagging fails."""

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        details: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


def _recipe_for_prompt(recipe: Recipe) -> Dict[str, Any]:
    # Keep prompting deterministic and compact; we don't include recipe `id`
    # because it would bias the model toward echoing it.
    return {
        "name": recipe.name,
        "ingredients": [
            {
                "name": ing.name,
                "quantity": float(ing.quantity),
                "unit": ing.unit,
                "is_to_taste": bool(ing.is_to_taste),
            }
            for ing in recipe.ingredients
        ],
        "instructions": list(recipe.instructions),
        "cooking_time_minutes": int(recipe.cooking_time_minutes),
    }


def tag_recipes(
    client: LLMClient, recipes: List[Recipe]
) -> Dict[str, RecipeTagsJson]:
    """Generate deterministic, strict recipe tags for a set of recipes.

    Notes:
    - LLM output is untrusted; we validate using the strict `RecipeTagsJson` schema.
    - If a recipe's tags fail strict schema validation, that recipe is omitted.
      (We never return unvalidated tag data.)
    - Output dict insertion order matches input recipe order for successful tags.
    """

    system_prompt = (
        "You are a strict recipe tagging engine. "
        "Return ONLY valid JSON. "
        "The JSON must match the RecipeTagsJson schema. "
        "Do not include commentary."
    )

    out: Dict[str, RecipeTagsJson] = {}
    for recipe in recipes:
        user_prompt = json.dumps(
            {"recipe": _recipe_for_prompt(recipe)},
            sort_keys=True,
            ensure_ascii=True,
        )

        raw = client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="RecipeTagsJson",
            temperature=0.0,
        )

        parsed = parse_llm_json(RecipeTagsJson, raw)
        if isinstance(parsed, ValidationFailure):
            # Reject invalid tag generation for this recipe.
            continue

        out[recipe.id] = parsed

    return out

