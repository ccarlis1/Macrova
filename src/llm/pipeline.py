from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.llm.client import LLMClient
from src.llm.duplicate_check import find_duplicate
from src.llm.recipe_generator import generate_recipe_drafts
from src.llm.recipe_validator import validate_recipe_drafts
from src.llm.repository import append_validated_recipes
from src.llm.usda_contract import assert_usda_capable_provider
from src.data_layer.recipe_db import RecipeDB
from src.providers.ingredient_provider import IngredientDataProvider


def generate_validate_persist_recipes(
    *,
    context: dict,
    count: int,
    recipes_path: str,
    provider: IngredientDataProvider,
    client: LLMClient,
) -> Dict[str, Any]:
    """Generate -> validate -> persist Phase 1 pipeline (Steps 4-7)."""
    # System invariant: USDA-backed validation is mandatory everywhere.
    assert_usda_capable_provider(provider)

    drafts = generate_recipe_drafts(client, context=context, count=count)

    accepted, rejected = validate_recipe_drafts(drafts, provider)

    existing_recipes = []
    if Path(recipes_path).exists():
        existing_recipes = RecipeDB(recipes_path).get_all_recipes()

    recipes_to_persist = []
    duplicate_ids: List[str] = []
    warnings: List[str] = []
    for wrapped in accepted:
        duplicate = find_duplicate(wrapped.recipe.name, existing_recipes)
        if duplicate is not None:
            duplicate_ids.append(duplicate.id)
            warnings.append(f"duplicate_of: {duplicate.id}")
            continue
        recipes_to_persist.append(wrapped)

    persisted_ids: List[str] = []
    if recipes_to_persist:
        persisted_ids = append_validated_recipes(
            path=recipes_path,
            recipes=recipes_to_persist,
        )

    return {
        "requested": count,
        "generated": len(drafts),
        "accepted": len(accepted),
        "rejected": [r.model_dump() for r in rejected],
        "persisted_ids": persisted_ids,
        "duplicate_ids": duplicate_ids,
        "recipe_ids": [*persisted_ids, *duplicate_ids],
        "warnings": warnings,
    }
