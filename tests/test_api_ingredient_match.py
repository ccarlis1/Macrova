import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.llm.schemas import IngredientMatchResult, ValidationFailure


def test_ingredient_match_endpoint_happy_path(monkeypatch):
    # Avoid real env / USDA / LLM calls.
    monkeypatch.setattr("src.api.server.load_llm_settings", lambda: type("S", (), {"api_key": "x", "model": "m", "timeout_seconds": 1.0, "max_retries": 0, "rate_limit_qps": 1.0, "enabled": True})())
    monkeypatch.setattr("src.api.server.USDAClient.from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr("src.api.server.CachedIngredientLookup", lambda usda_client: object())
    monkeypatch.setattr("src.api.server.APIIngredientProvider", lambda cached_lookup: object())

    accepted_match = IngredientMatchResult(
        query="chicken",
        normalized_name="chicken breast",
        confidence=0.9,
    )
    failures = [
        ValidationFailure(
            error_code="LOW_CONFIDENCE_MATCH",
            message="Low confidence",
            field_errors=["original_query=rice"],
        )
    ]

    monkeypatch.setattr(
        "src.api.server.match_ingredient_queries",
        lambda client, queries: [accepted_match],
    )
    monkeypatch.setattr(
        "src.api.server.validate_matches",
        lambda matches, provider: ([accepted_match], failures),
    )

    client = TestClient(app)
    resp = client.post("/api/ingredients/match", json={"queries": ["chicken", "rice"]})
    assert resp.status_code == 200

    assert resp.json() == {
        "accepted": [
            {
                "original_query": "chicken",
                "normalized_name": "chicken breast",
                "confidence": 0.9,
            }
        ],
        "rejected": [
            {
                "code": "LOW_CONFIDENCE_MATCH",
                "message": "Low confidence",
                "original_query": "rice",
            }
        ],
    }


def test_ingredient_match_endpoint_rejects_invalid_request(monkeypatch):
    client = TestClient(app)
    resp = client.post("/api/ingredients/match", json={"queries": []})
    assert resp.status_code == 400
    assert resp.json() == {
        "error": {"code": "INVALID_REQUEST", "message": "Invalid request schema."}
    }

