import pytest
from fastapi.testclient import TestClient

from src.api.error_mapping import map_exception_to_api_error
from src.api.server import app
from src.config.llm_settings import LLMSettingsError
from src.llm.client import (
    LLMInternalError,
    LLMRateLimitError,
    LLMResponseFormatError,
    LLMTimeoutError,
)
from src.llm.recipe_generator import RecipeGenerationError
from src.llm.usda_contract import USDAProviderRequiredError
from src.llm.feedback_cache import DeterministicCacheMissError
from src.planning.orchestrator import LLMFeedbackOrchestratorError


def test_map_exception_to_api_error_unit_mapping():
    class DummySchemaError(Exception):
        pass

    # LLM settings
    status, payload = map_exception_to_api_error(LLMSettingsError("bad config"))
    assert status == 500
    assert payload["error"]["code"] == "LLM_SETTINGS_ERROR"

    # LLM timeout
    status, payload = map_exception_to_api_error(
        LLMTimeoutError(
            error_code="X_TIMEOUT",
            message="timeout",
        )
    )
    assert status == 504
    assert payload["error"]["code"] == "LLM_TIMEOUT"

    # LLM rate limit (API error)
    status, payload = map_exception_to_api_error(
        LLMRateLimitError(
            error_code="X_429",
            message="rate limit",
        )
    )
    assert status == 429
    assert payload["error"]["code"] == "LLM_API_ERROR"

    # LLM response format error
    status, payload = map_exception_to_api_error(
        LLMResponseFormatError(
            error_code="X_BAD_JSON",
            message="bad format",
        )
    )
    assert status == 502
    assert payload["error"]["code"] == "LLM_RESPONSE_FORMAT_ERROR"

    # Schema validation error
    status, payload = map_exception_to_api_error(
        RecipeGenerationError(error_code="X_SCHEMA", message="schema mismatch")
    )
    assert status == 422
    assert payload["error"]["code"] == "SCHEMA_VALIDATION_ERROR"

    # Ingredient validation error
    status, payload = map_exception_to_api_error(
        USDAProviderRequiredError(message="usda required", provider_type="Fake")
    )
    assert status == 422
    assert payload["error"]["code"] == "INGREDIENT_VALIDATION_ERROR"

    # Unknown => pipeline execution
    status, payload = map_exception_to_api_error(DummySchemaError("boom"))
    assert status == 500
    assert payload["error"]["code"] == "PIPELINE_EXECUTION_ERROR"

    # Deterministic strict cache miss
    status, payload = map_exception_to_api_error(
        DeterministicCacheMissError("cache miss")
    )
    assert status == 500
    assert payload["error"]["code"] == "DETERMINISTIC_CACHE_MISS"

    # Related orchestrator failures
    status, payload = map_exception_to_api_error(
        LLMFeedbackOrchestratorError(
            error_code="VALIDATION_EXCEPTION",
            message="validation raised",
        )
    )
    assert status == 500
    assert payload["error"]["code"] == "VALIDATION_EXCEPTION"


@pytest.mark.parametrize(
    "exc,expected_code",
    [
        (LLMTimeoutError(error_code="X_TIMEOUT", message="timeout"), "LLM_TIMEOUT"),
        (
            LLMRateLimitError(error_code="X_429", message="rate limit"),
            "LLM_API_ERROR",
        ),
        (
            LLMResponseFormatError(error_code="X_BAD_JSON", message="bad format"),
            "LLM_RESPONSE_FORMAT_ERROR",
        ),
        (
            RecipeGenerationError(error_code="X_SCHEMA", message="schema mismatch"),
            "SCHEMA_VALIDATION_ERROR",
        ),
        (
            USDAProviderRequiredError(message="usda required", provider_type="Fake"),
            "INGREDIENT_VALIDATION_ERROR",
        ),
        (RuntimeError("boom"), "PIPELINE_EXECUTION_ERROR"),
    ],
)
def test_generate_validated_recipes_api_error_codes(monkeypatch, exc, expected_code):
    # Ensure endpoint reaches pipeline: valid settings + valid provider wiring stubs.
    from src.config.llm_settings import LLMSettings

    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=True,
        ),
    )

    # Keep these deterministic (endpoint wiring only).
    monkeypatch.setattr("src.api.server.USDAClient.from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr("src.api.server.CachedIngredientLookup", lambda usda_client: object())
    monkeypatch.setattr("src.api.server.APIIngredientProvider", lambda cached_lookup: object())

    def fake_pipeline(*args, **kwargs):
        raise exc

    monkeypatch.setattr("src.api.server.generate_validate_persist_recipes", fake_pipeline)

    client = TestClient(app)
    resp = client.post(
        "/api/recipes/generate-validated",
        json={"context": {}, "count": 1},
    )
    assert resp.status_code in (500, 502, 504, 422, 429)
    assert resp.json()["error"]["code"] == expected_code


def test_generate_validated_recipes_api_llm_settings_error(monkeypatch):
    monkeypatch.setattr("src.api.server.load_llm_settings", lambda: (_ for _ in ()).throw(LLMSettingsError("bad config")))

    client = TestClient(app)
    resp = client.post(
        "/api/recipes/generate-validated",
        json={"context": {}, "count": 1},
    )
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "LLM_SETTINGS_ERROR"


def test_api_recipes_maps_exceptions_to_api_error(monkeypatch):
    class DummyRecipeDB:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("db init failed")

    monkeypatch.setattr("src.api.server.RecipeDB", DummyRecipeDB)

    client = TestClient(app)
    resp = client.get("/api/recipes")
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "PIPELINE_EXECUTION_ERROR"

