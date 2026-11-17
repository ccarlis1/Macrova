from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.llm.client import LLMClient
from src.llm.recipe_generator import generate_recipe_drafts
from src.llm.schemas import RecipeDraft


def suggest_targeted_recipe_drafts(
    client: LLMClient,
    context: Dict[str, Any],
    count: int,
) -> List[RecipeDraft]:
    """Generate targeted recipe drafts given deterministic feedback context."""

    # The existing recipe generator already enforces strict JSON + RecipeDraft
    # schema validation; we only control the deterministic prompt context shape.
    return generate_recipe_drafts(client=client, context=context, count=count)

