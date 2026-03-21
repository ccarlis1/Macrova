from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict

from src.llm.client import LLMClient
from src.llm.schemas import PlannerConfigJson, ValidationFailure, parse_llm_json

logger = logging.getLogger(__name__)

# Embedded so the model cannot invent alternate keys (e.g. numberOfMeals).
_PLANNER_CONFIG_JSON_SCHEMA_COMPACT = json.dumps(
    PlannerConfigJson.model_json_schema(),
    separators=(",", ":"),
    ensure_ascii=True,
)


@dataclass(frozen=True)
class PlannerConfigParsingError(Exception):
    """Raised when NL->JSON parsing or strict schema validation fails."""

    error_code: str
    message: str
    details: Dict[str, Any]

    def __str__(self) -> str:  # pragma: no cover (covered indirectly via API tests)
        return f"{self.error_code}: {self.message}"


def parse_nl_config(client: LLMClient, text: str) -> PlannerConfigJson:
    """Convert natural language into a strict PlannerConfigJson.

    Invariants:
    - LLM output is untrusted.
    - We validate via strict Pydantic schema parsing only.
    - We never return partially-valid configs: either valid PlannerConfigJson
      or a deterministic PlannerConfigParsingError.
    """
    if not isinstance(text, str) or not text.strip():
        raise PlannerConfigParsingError(
            error_code="INVALID_NL_INPUT",
            message="prompt text must be a non-empty string.",
            details={"text_type": str(type(text)), "text_empty": True},
        )

    system_prompt = (
        "You are a nutrition-agent planning assistant. "
        "Convert user natural language into a JSON object that matches the "
        "PlannerConfigJson schema below exactly. "
        "Return ONLY JSON (no markdown, no prose). "
        "Use ONLY the property names from the schema — for example map "
        "'N meals per day' to integer field meals_per_day (not numberOfMeals "
        "or total_meals). "
        "If the user does not specify days, calories, protein, cuisine, or "
        "budget, choose sensible defaults: days=1, targets suitable for a "
        "typical adult (e.g. 2000 calories, 120g protein), cuisine=[], "
        "budget=standard."
    )
    user_prompt = (
        "User request (natural language):\n"
        f"{text}\n\n"
        "PlannerConfigJson JSON Schema (additionalProperties false at each "
        f"object; obey exactly):\n{_PLANNER_CONFIG_JSON_SCHEMA_COMPACT}\n"
    )

    raw = client.generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="PlannerConfigJson",
        temperature=0.0,
    )

    parsed_or_failure = parse_llm_json(PlannerConfigJson, raw)
    if isinstance(parsed_or_failure, ValidationFailure):
        raw_text = getattr(client, "_last_model_content_text", None)
        logger.warning(
            "planner_config_json_validation_failed prompt_len=%d field_errors=%s "
            "parsed_object=%s raw_model_content=%s",
            len(text),
            parsed_or_failure.field_errors,
            json.dumps(raw, sort_keys=True, ensure_ascii=True),
            raw_text if raw_text is None else repr(raw_text),
        )
        raise PlannerConfigParsingError(
            error_code=parsed_or_failure.error_code,
            message=parsed_or_failure.message,
            details={"field_errors": parsed_or_failure.field_errors},
        )

    return parsed_or_failure

