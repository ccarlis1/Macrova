from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from src.llm.client import LLMClient
from src.llm.schemas import parse_llm_json, ValidationFailure


class IngredientFdcDisambiguationError(Exception):
    """Deterministic error for constrained USDA FDC disambiguation."""

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details or {}


class IngredientFdcSelectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    chosen_fdc_id: int
    confidence: float = Field(ge=0.0, le=1.0)


class ConstrainedIngredientFdcDisambiguator:
    """LLM tie-breaker that can only choose from provided USDA candidate IDs."""

    schema_name = "IngredientFdcSelectionResult"

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def choose_fdc_id(
        self,
        *,
        query: str,
        candidates: Sequence[Dict[str, Any]],
    ) -> int:
        q = str(query).strip()
        if not q:
            raise IngredientFdcDisambiguationError(
                error_code="INVALID_QUERY",
                message="Query must be non-empty.",
            )
        if not isinstance(candidates, (list, tuple)) or len(candidates) < 1:
            raise IngredientFdcDisambiguationError(
                error_code="NO_CANDIDATES",
                message="Must provide at least 1 candidate.",
            )

        allowed_ids: List[int] = []
        normalized_candidates: List[Dict[str, Any]] = []
        for idx, c in enumerate(candidates):
            if not isinstance(c, dict):
                continue
            fdc_id = c.get("fdc_id")
            if isinstance(fdc_id, int):
                allowed_ids.append(fdc_id)
                normalized_candidates.append(
                    {
                        "fdc_id": fdc_id,
                        "description": str(c.get("description") or ""),
                        "data_type": str(c.get("data_type") or ""),
                        "candidate_index": idx,
                    }
                )

        allowed_ids = sorted(set(allowed_ids))
        if not allowed_ids:
            raise IngredientFdcDisambiguationError(
                error_code="NO_VALID_FDC_IDS",
                message="Candidates did not include any valid integer fdc_id values.",
            )

        system_prompt = (
            "You are a strict USDA ingredient disambiguator. "
            "Your task is to pick the single best USDA FoodData Central (FDC) ID "
            "for the given ingredient query from the provided candidates ONLY. "
            "Return ONLY valid JSON with the exact schema. "
            "Hard rule: chosen_fdc_id MUST be one of the provided candidate fdc_id values. "
            "Do not include commentary."
        )

        user_prompt = {
            "query": q,
            "candidates": [
                {"fdc_id": c["fdc_id"], "description": c["description"], "data_type": c["data_type"]}
                for c in normalized_candidates
            ],
            "instructions": [
                "Select exactly one chosen_fdc_id from candidates.",
                "Set confidence between 0 and 1.",
                "Never choose an ID not present in candidates.",
            ],
        }

        raw = self._client.generate_json(
            system_prompt=system_prompt,
            user_prompt=json.dumps(user_prompt, ensure_ascii=True),
            schema_name=self.schema_name,
            temperature=0.0,
        )

        parsed_or_failure = parse_llm_json(IngredientFdcSelectionResult, raw)
        if isinstance(parsed_or_failure, ValidationFailure):
            raise IngredientFdcDisambiguationError(
                error_code=parsed_or_failure.error_code,
                message="LLM output failed strict schema validation.",
                details={"field_errors": parsed_or_failure.field_errors},
            )

        chosen = parsed_or_failure.chosen_fdc_id
        if chosen not in allowed_ids:
            raise IngredientFdcDisambiguationError(
                error_code="LLM_CHOSEN_FDC_NOT_ALLOWED",
                message="LLM chose an FDC ID not present in the provided candidate set.",
                details={
                    "chosen_fdc_id": chosen,
                    "allowed_fdc_ids": allowed_ids,
                },
            )

        return chosen

