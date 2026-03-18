import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.config.llm_settings import LLMSettings


def test_generate_validated_recipes_happy_path(monkeypatch):
    # Patch LLM settings loader (no real env needed).
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

    # Patch USDA/provider creation to keep test offline.
    class DummyUSDAClient:
        pass

    monkeypatch.setattr(
        "src.api.server.USDAClient.from_env",
        classmethod(lambda cls: DummyUSDAClient()),
    )

    class DummyCachedIngredientLookup:
        def __init__(self, *, usda_client):
            self.usda_client = usda_client

    monkeypatch.setattr(
        "src.api.server.CachedIngredientLookup",
        DummyCachedIngredientLookup,
    )

    class DummyProvider:
        pass

    monkeypatch.setattr(
        "src.api.server.APIIngredientProvider",
        lambda cached_lookup: DummyProvider(),
    )

    # Patch pipeline so we don't depend on schema generation/USDA.
    def fake_pipeline(*, context, count, recipes_path, provider, client):
        return {
            "requested": count,
            "generated": count,
            "accepted": 1,
            "rejected": [
                {
                    "ok": False,
                    "error_code": "INGREDIENT_NOT_FOUND",
                    "message": "Ingredient not found",
                    "field_errors": ["ingredient_index=0"],
                }
            ],
            "persisted_ids": ["llm_abc123"],
        }

    monkeypatch.setattr(
        "src.api.server.generate_validate_persist_recipes",
        fake_pipeline,
    )

    client = TestClient(app)
    resp = client.post(
        "/api/recipes/generate-validated",
        json={"context": {"x": 1}, "count": 1},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["accepted_count"] == 1
    assert data["rejected_count"] == 1
    assert data["recipe_ids"] == ["llm_abc123"]
    assert data["failures"] == [
        {"code": "INGREDIENT_NOT_FOUND", "message": "Ingredient not found"}
    ]


def test_generate_validated_recipes_rejects_invalid_count(monkeypatch):
    # Avoid real env/USDA calls by patching the pipeline; it shouldn't be reached.
    monkeypatch.setattr(
        "src.api.server.generate_validate_persist_recipes",
        lambda *args, **kwargs: {},
    )
    client = TestClient(app)

    resp = client.post(
        "/api/recipes/generate-validated",
        json={"context": {}, "count": 0},
    )
    assert resp.status_code == 400
    assert resp.json() == {
        "error": {"code": "INVALID_REQUEST", "message": "Invalid request schema."}
    }


def test_generate_validated_recipes_rejects_missing_context(monkeypatch):
    monkeypatch.setattr(
        "src.api.server.generate_validate_persist_recipes",
        lambda *args, **kwargs: {},
    )
    client = TestClient(app)

    resp = client.post(
        "/api/recipes/generate-validated",
        json={"count": 1},
    )
    assert resp.status_code == 400
    assert resp.json() == {
        "error": {"code": "INVALID_REQUEST", "message": "Invalid request schema."}
    }

