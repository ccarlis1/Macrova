import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.providers.ingredient_provider import IngredientDataProvider
from src.llm.schemas import IngredientMatchResult


def test_ingredient_match_endpoint_happy_path(monkeypatch):
    # Realistic integration test: run matcher + validation using fake boundaries.
    class DummyLLMClient:
        def generate_json(self, *, system_prompt, user_prompt, schema_name, temperature=0.0):
            assert schema_name == "IngredientMatchResult[]"
            assert temperature == 0.0
            return {
                "matches": [
                    {
                        "query": "ignored",
                        "normalized_name": "chicken breast",
                        "confidence": 0.9,
                    },
                    {
                        "query": "ignored",
                        "normalized_name": "rice",
                        "confidence": 0.6,
                    },
                ]
            }

    class FakeUSDAProvider(IngredientDataProvider):
        usda_capable = True

        def get_ingredient_info(self, name: str):
            key = str(name).lower().strip()
            if key == "chicken breast":
                return {"name": "chicken breast", "per_100g": {}}
            return None

        def resolve_all(self, ingredient_names):
            return None

    monkeypatch.setattr("src.api.server.build_llm_client", lambda: DummyLLMClient())
    monkeypatch.setattr("src.api.server.build_usda_provider", lambda: FakeUSDAProvider())

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
                "message": "Low confidence match: confidence=0.6. Threshold=0.7.",
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

