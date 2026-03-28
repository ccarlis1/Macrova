"""v1 route parity, OpenAPI contract paths, recipe_ids, deterministic ingredients."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.api.server import PlanRequest, _filter_recipes_by_ids, app
from src.ingestion.usda_client import FoodDetailsResult, USDAClient
from src.planning.phase0_models import Assignment, DailyTracker
from src.planning.phase10_reporting import MealPlanResult


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
        "/api/v1/recipes/sync",
        "/api/v1/recipes/{recipe_id}",
        "/api/v1/recipes/generate-validated",
        "/api/v1/recipes/tags/generate",
        "/api/v1/ingredients/match",
        "/api/v1/ingredients/search",
        "/api/v1/ingredients/resolve",
        "/api/v1/nutrition/summary",
        "/api/v1/llm/status",
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


def test_recipe_detail_returns_404_for_unknown_id():
    client = TestClient(app)
    resp = client.get("/api/v1/recipes/__no_such_recipe__")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_nutrition_summary_totals_match_local_db():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/nutrition/summary",
        json={
            "servings": 2,
            "ingredients": [
                {"name": "cream of rice", "quantity": 100, "unit": "g"},
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["calories"] == 370.0
    assert body["per_serving_calories"] == 185.0
    assert body["servings"] == 2
    assert body["protein_g"] == 7.5


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


def test_recipe_sync_writes_json_and_plan_sees_recipe(tmp_path, monkeypatch):
    recipes_file = tmp_path / "recipes.json"
    recipes_file.write_text('{"recipes": []}', encoding="utf-8")
    monkeypatch.setattr("src.api.server.recipes_path", str(recipes_file))

    client = TestClient(app)
    rid = "00000000-0000-4000-8000-000000000001"
    sync_body = {
        "recipes": [
            {
                "id": rid,
                "name": "Sync Test Bowl",
                "ingredients": [
                    {"name": "cream of rice", "quantity": 100, "unit": "g"},
                ],
            }
        ]
    }
    sync_res = client.post("/api/v1/recipes/sync", json=sync_body)
    assert sync_res.status_code == 200
    assert sync_res.json()["synced_ids"] == [rid]

    data = recipes_file.read_text(encoding="utf-8")
    assert rid in data
    assert "Sync Test Bowl" in data
    assert "cream of rice" in data

    def _stub_plan_meals(planning_profile, recipe_pool, days):
        assert any(r.id == rid for r in recipe_pool), "synced recipe missing from planner pool"
        tracker = DailyTracker(
            calories_consumed=350.0,
            protein_consumed=7.5,
            fat_consumed=0.5,
            carbs_consumed=75.0,
            slots_assigned=1,
            slots_total=1,
        )
        return MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[Assignment(0, 0, rid)],
            daily_trackers={0: tracker},
            stats={"attempts": 1, "backtracks": 0},
        )

    monkeypatch.setattr("src.api.server.plan_meals", _stub_plan_meals)

    plan_res = client.post(
        "/api/v1/plan",
        json={
            "daily_calories": 2000,
            "daily_protein_g": 150.0,
            "daily_fat_g_min": 50.0,
            "daily_fat_g_max": 90.0,
            "schedule": {"08:00": 3, "12:00": 3, "18:00": 3},
            "days": 1,
            "ingredient_source": "local",
            "recipe_ids": [rid],
        },
    )
    assert plan_res.status_code == 200
    body = plan_res.json()
    assert body.get("success") is True
    day0 = body["daily_plans"][0]
    names = {m.get("name") for m in day0.get("meals", [])}
    assert "Sync Test Bowl" in names


def test_llm_status_endpoint_reports_enabled(monkeypatch):
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = TestClient(app)
    res = client.get("/api/v1/llm/status")
    assert res.status_code == 200
    assert res.json() == {"enabled": False}

    monkeypatch.setenv("LLM_API_KEY", "sk-test-key-for-status-endpoint")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    res_on = client.get("/api/v1/llm/status")
    assert res_on.status_code == 200
    assert res_on.json() == {"enabled": True}
