from __future__ import annotations

import json
from typing import Any, Dict, List

from src.llm.client import LLMClient
from src.llm.schemas import RecipeDraft, ValidationFailure, parse_llm_json


class RecipeGenerationError(Exception):
    """Deterministic error raised when recipe generation fails."""

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


def _estimate_context_snippet(context: Dict[str, Any]) -> str:
    # Deterministic prompt string for the LLM (stable key ordering).
    return json.dumps(context, sort_keys=True, ensure_ascii=True)


def generate_recipe_drafts(
    client: LLMClient,
    *,
    context: dict,
    count: int,
) -> List[RecipeDraft]:
    """Generate strict `RecipeDraft` objects from an LLM.

    Notes:
    - `LLMClient` guarantees the top-level return is a JSON object (dict), not a list.
    - We therefore expect an envelope: `{ "drafts": [ ... ] }`.
    - Ordering from the LLM is preserved to keep determinism across retries.
    """

    if count < 1:
        raise RecipeGenerationError(
            error_code="INVALID_COUNT",
            message="count must be >= 1.",
            details={"count": count},
        )

    system_prompt = (
        "You generate candidate meal recipes for nutrition agents. "
        "Return ONLY valid JSON. Do not include commentary. "
        "The JSON must be an object with exactly one key: `drafts`, "
        "whose value is an array of recipe draft objects."
    )

    user_prompt = (
        f"Request: generate exactly {count} recipe drafts.\n"
        f"Generation context (JSON): {_estimate_context_snippet(context)}\n"
        "Each draft must follow the RecipeDraft schema."
    )

    raw = client.generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="RecipeDraftEnvelope",
        temperature=0.0,
    )

    if not isinstance(raw, dict):
        raise RecipeGenerationError(
            error_code="LLM_RAW_NOT_DICT",
            message="LLM response was not a JSON object.",
        )

    allowed_keys = {"drafts"}
    raw_keys = set(raw.keys())
    if raw_keys != allowed_keys:
        raise RecipeGenerationError(
            error_code="LLM_ENVELOPE_INVALID_KEYS",
            message="LLM response envelope keys were not exactly ['drafts'].",
            details={"raw_keys": sorted(raw_keys)},
        )

    drafts_raw = raw.get("drafts")
    if not isinstance(drafts_raw, list):
        raise RecipeGenerationError(
            error_code="LLM_DRAFTS_NOT_LIST",
            message="LLM response field `drafts` was not a list.",
        )

    if len(drafts_raw) != count:
        raise RecipeGenerationError(
            error_code="LLM_WRONG_DRAFT_COUNT",
            message="LLM returned the wrong number of drafts.",
            details={"expected": count, "received": len(drafts_raw)},
        )

    parsed: List[RecipeDraft] = []
    for idx, draft_raw in enumerate(drafts_raw):
        parsed_or_failure = parse_llm_json(RecipeDraft, draft_raw)
        if isinstance(parsed_or_failure, ValidationFailure):
            raise RecipeGenerationError(
                error_code="LLM_DRAFT_SCHEMA_VALIDATION_FAILED",
                message="A generated draft failed strict schema validation.",
                details={
                    "draft_index": idx,
                    "validation_failure": parsed_or_failure.model_dump(),
                },
            )
        parsed.append(parsed_or_failure)

    return parsed

