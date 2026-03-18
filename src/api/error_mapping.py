from __future__ import annotations

from typing import Any, Dict, Tuple

from src.config.llm_settings import LLMSettingsError
from src.llm.client import (
    LLMClientError,
    LLMInternalError,
    LLMRateLimitError,
    LLMResponseFormatError,
    LLMTimeoutError,
)
from src.llm.ingredient_matcher import IngredientMatchingError
from src.llm.recipe_generator import RecipeGenerationError
from src.llm.recipe_validator import RecipeValidationError
from src.llm.usda_contract import USDAProviderRequiredError
from src.llm.constraint_parser import PlannerConfigParsingError
from src.data_layer.user_profile import PlannerConfigMappingError


API_ERROR = "error"


def _payload(code: str, message: str) -> Dict[str, Any]:
    return {API_ERROR: {"code": code, "message": message}}


def map_exception_to_api_error(exc: Exception) -> Tuple[int, Dict[str, Any]]:
    """Map internal exception to deterministic API error code.

    Invariant: always returns a payload of the form:
      {"error": {"code": <API_CODE>, "message": <string>}}
    """

    # Foundation/config errors
    if isinstance(exc, LLMSettingsError):
        return 500, _payload("LLM_SETTINGS_ERROR", str(exc))

    # LLM API/transport errors
    if isinstance(exc, LLMTimeoutError):
        return 504, _payload("LLM_TIMEOUT", str(exc))

    if isinstance(exc, (LLMRateLimitError,)):
        return 429, _payload("LLM_API_ERROR", str(exc))

    if isinstance(exc, LLMResponseFormatError):
        return 502, _payload("LLM_RESPONSE_FORMAT_ERROR", str(exc))

    if isinstance(exc, (LLMInternalError, LLMClientError)):
        # Covers remaining client-side transport/server errors.
        return 502, _payload("LLM_API_ERROR", str(exc))

    # Schema/contract errors surfaced as deterministic internal exceptions.
    if isinstance(
        exc,
        (
            RecipeGenerationError,
            RecipeValidationError,
            IngredientMatchingError,
            PlannerConfigParsingError,
            PlannerConfigMappingError,
        ),
    ):
        return 422, _payload("SCHEMA_VALIDATION_ERROR", str(exc))

    # Validation failures that are specifically about input/provider correctness.
    if isinstance(exc, USDAProviderRequiredError):
        return 422, _payload("INGREDIENT_VALIDATION_ERROR", str(exc))

    # Unknown/unexpected failures
    return 500, _payload("PIPELINE_EXECUTION_ERROR", str(exc))

