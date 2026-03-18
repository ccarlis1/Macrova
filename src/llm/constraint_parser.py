from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.llm.client import LLMClient
from src.llm.schemas import PlannerConfigJson, ValidationFailure, parse_llm_json


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
        "Convert user natural language into a STRICT JSON object that matches "
        "the PlannerConfigJson schema exactly. "
        "Return ONLY JSON. Do not include commentary. "
        "No extra keys are allowed."
    )
    user_prompt = (
        "User request (natural language):\n"
        f"{text}\n\n"
        "Return a JSON object matching PlannerConfigJson."
    )

    raw = client.generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="PlannerConfigJson",
        temperature=0.0,
    )

    parsed_or_failure = parse_llm_json(PlannerConfigJson, raw)
    if isinstance(parsed_or_failure, ValidationFailure):
        raise PlannerConfigParsingError(
            error_code=parsed_or_failure.error_code,
            message=parsed_or_failure.message,
            details={"field_errors": parsed_or_failure.field_errors},
        )

    return parsed_or_failure

