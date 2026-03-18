from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.llm.client import LLMClient
from src.llm.recipe_generator import generate_recipe_drafts
from src.llm.recipe_validator import validate_recipe_drafts
from src.llm.repository import append_validated_recipes
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
    drafts = generate_recipe_drafts(client, context=context, count=count)

    accepted, rejected = validate_recipe_drafts(drafts, provider)

    persisted_ids: List[str] = []
    if accepted:
        persisted_ids = append_validated_recipes(
            path=recipes_path,
            recipes=accepted,
        )

    return {
        "requested": count,
        "generated": len(drafts),
        "accepted": len(accepted),
        "rejected": [r.model_dump() for r in rejected],
        "persisted_ids": persisted_ids,
    }

