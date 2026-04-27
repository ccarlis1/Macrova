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
from src.llm.feedback_cache import DeterministicCacheMissError
from src.planning.orchestrator import LLMFeedbackOrchestratorError, LLMPlanningModeError
from src.llm.tag_repository import TagRepositoryError


API_ERROR = "error"
TAG_NOT_FOUND = "TAG_NOT_FOUND"
TAG_CONFLICT = "TAG_CONFLICT"
TAG_INVALID = "TAG_INVALID"
RECIPE_NOT_FOUND = "RECIPE_NOT_FOUND"
RECIPE_NOT_BATCHABLE = "RECIPE_NOT_BATCHABLE"
BATCH_CONFLICT = "BATCH_CONFLICT"
BATCH_INVALID = "BATCH_INVALID"
FM_TAG_EMPTY = "FM-TAG-EMPTY"
FM_BATCH_CONFLICT = "FM-BATCH-CONFLICT"
FM_MACRO_INFEASIBLE = "FM-MACRO-INFEASIBLE"


class ApiContractError(Exception):
    """Typed API-layer contract error with deterministic code mapping."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


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

    # NL planner: include structured details so clients can show field-level errors.
    if isinstance(exc, PlannerConfigParsingError):
        err: Dict[str, Any] = {
            "code": "SCHEMA_VALIDATION_ERROR",
            "message": str(exc),
        }
        if exc.details:
            err["details"] = exc.details
        return 422, {API_ERROR: err}

    # Schema/contract errors surfaced as deterministic internal exceptions.
    if isinstance(
        exc,
        (
            RecipeGenerationError,
            RecipeValidationError,
            IngredientMatchingError,
            PlannerConfigMappingError,
        ),
    ):
        return 422, _payload("SCHEMA_VALIDATION_ERROR", str(exc))

    # Typed orchestrator failures should map deterministically.
    if isinstance(exc, DeterministicCacheMissError):
        return 500, _payload("DETERMINISTIC_CACHE_MISS", str(exc))

    if isinstance(exc, LLMFeedbackOrchestratorError):
        # Preserve the internal orchestrator error_code for stable API mapping.
        return 500, _payload(exc.error_code, str(exc))

    if isinstance(exc, LLMPlanningModeError):
        return 422, _payload(exc.error_code, str(exc))

    # Validation failures that are specifically about input/provider correctness.
    if isinstance(exc, USDAProviderRequiredError):
        return 422, _payload("INGREDIENT_VALIDATION_ERROR", str(exc))

    if isinstance(exc, TagRepositoryError):
        if exc.code == TAG_NOT_FOUND:
            return 404, _payload(TAG_NOT_FOUND, str(exc))
        if exc.code == TAG_CONFLICT:
            return 409, _payload(TAG_CONFLICT, str(exc))
        if exc.code == TAG_INVALID:
            return 400, _payload(TAG_INVALID, str(exc))
        return 400, _payload(exc.code, str(exc))

    if isinstance(exc, ApiContractError):
        if exc.code in {FM_TAG_EMPTY, FM_BATCH_CONFLICT, FM_MACRO_INFEASIBLE}:
            return 422, _payload(exc.code, str(exc))
        if exc.code == RECIPE_NOT_FOUND:
            return 404, _payload(RECIPE_NOT_FOUND, str(exc))
        if exc.code == RECIPE_NOT_BATCHABLE:
            return 422, _payload(RECIPE_NOT_BATCHABLE, str(exc))
        if exc.code == BATCH_CONFLICT:
            return 409, _payload(BATCH_CONFLICT, str(exc))
        if exc.code == BATCH_INVALID:
            return 400, _payload(BATCH_INVALID, str(exc))
        return 400, _payload(exc.code, str(exc))

    # Unknown/unexpected failures
    return 500, _payload("PIPELINE_EXECUTION_ERROR", str(exc))

