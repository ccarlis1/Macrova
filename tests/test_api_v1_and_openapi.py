"""v1 route parity, OpenAPI contract paths, recipe_ids, deterministic ingredients."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.api.server import PlanRequest, _filter_recipes_by_ids, app
from src.ingestion.usda_client import FoodDetailsResult, USDAClient


class _Recipe:
    def __init__(self, rid: str) -> None:
        self.id = rid
        self.name = rid


def test_filter_recipes_by_ids_preserves_order_and_subset():
    r1, r2, r3 = _Recipe("a"), _Recipe("b"), _Recipe("c")
    out = _filter_recipes_by_ids([r1, r2, r3], ["c", "a"])
    assert [x.id for x in out] == ["c", "a"]
    assert _filter_recipes_by_ids([r1, r2], None) == [r1, r2]


def test_openapi_includes_v1_contract_paths():
    schema = app.openapi()
    paths = schema["paths"]
    required = [
        "/api/v1/plan",
        "/api/v1/plan-from-text",
        "/api/v1/recipes",
        "/api/v1/recipes/generate-validated",
        "/api/v1/recipes/tags/generate",
        "/api/v1/ingredients/match",
        "/api/v1/ingredients/search",
        "/api/v1/ingredients/resolve",
    ]
    missing = [p for p in required if p not in paths]
    assert not missing, f"missing paths: {missing}"


def test_openapi_plan_request_has_recipe_ids():
    schema = app.openapi()
    body = schema["paths"]["/api/v1/plan"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    # FastAPI 0.115+ may use $ref to components
    if "$ref" in body:
        ref_name = body["$ref"].split("/")[-1]
        plan_schema = schema["components"]["schemas"][ref_name]
    else:
        plan_schema = body
    props = plan_schema.get("properties", {})
    assert "recipe_ids" in props


def test_api_v1_recipes_lists_same_as_legacy(monkeypatch):
    monkeypatch.setattr(
        "src.api.server.RecipeDB",
        lambda *_a, **_k: MagicMock(
            get_all_recipes=lambda: [_Recipe("r1"), _Recipe("r2")]
        ),
    )
    client = TestClient(app)
    legacy = client.get("/api/recipes")
    v1 = client.get("/api/v1/recipes")
    assert legacy.status_code == v1.status_code == 200
    assert legacy.json() == v1.json()


def test_ingredient_search_uses_usda_client(monkeypatch):
    mock_client = MagicMock(spec=USDAClient)
    mock_client.search_candidates.return_value = [
        {"fdcId": 123, "description": "Test food", "dataType": "SR Legacy"},
    ]
    monkeypatch.setattr("src.api.server.USDAClient.from_env", lambda **_k: mock_client)

    client = TestClient(app)
    resp = client.get("/api/v1/ingredients/search", params={"q": "egg"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"][0]["fdc_id"] == "123"
    mock_client.search_candidates.assert_called_once()
    call_kw = mock_client.search_candidates.call_args
    assert call_kw[0][0] == "egg"
    assert call_kw[1]["page_number"] == 1
    assert call_kw[1]["data_types"] == "all"


def test_ingredient_search_sr_legacy_only_query_param(monkeypatch):
    mock_client = MagicMock(spec=USDAClient)
    mock_client.search_candidates.return_value = []
    monkeypatch.setattr("src.api.server.USDAClient.from_env", lambda **_k: mock_client)

    client = TestClient(app)
    resp = client.get(
        "/api/v1/ingredients/search",
        params={"q": "chicken", "data_types": "sr_legacy_only"},
    )
    assert resp.status_code == 200
    assert mock_client.search_candidates.call_args[1]["data_types"] == "sr_legacy_only"


def test_ingredient_resolve_fdc_id(monkeypatch):
    raw = {"description": "Oats", "foodNutrients": []}

    mock_client = MagicMock(spec=USDAClient)
    mock_client.get_food_details.return_value = FoodDetailsResult(
        success=True,
        fdc_id=999,
        raw_payload=raw,
    )
    monkeypatch.setattr("src.api.server.USDAClient.from_env", lambda **_k: mock_client)

    client = TestClient(app)
    resp = client.post("/api/v1/ingredients/resolve", json={"fdc_id": 999})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "usda"
    assert body["fdc_id"] == "999"
    assert body["name"] == "Oats"


def test_ingredient_resolve_local_missing_is_404():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/ingredients/resolve",
        json={"name": "___not_an_ingredient___", "ingredient_source": "local"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_plan_request_model_accepts_recipe_ids():
    r = PlanRequest(
        daily_calories=2000,
        daily_protein_g=150.0,
        daily_fat_g_min=50.0,
        daily_fat_g_max=90.0,
        schedule={"07:00": 1},
        recipe_ids=["r1", "r2"],
    )
    assert r.recipe_ids == ["r1", "r2"]
