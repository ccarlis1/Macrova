"""Async optimize-cart job API: enqueue, poll, and job contract."""

import time

import pytest
from fastapi.testclient import TestClient

from src.api.server import app


SAMPLE_REQUEST = {
    "schemaVersion": "1.0",
    "mealPlan": {
        "id": "plan-async-1",
        "recipes": [
            {
                "id": "rec-1",
                "name": "Chicken bowl",
                "ingredients": [
                    {"name": "chicken breast", "quantity": 1.5, "unit": "lb"},
                ],
            }
        ],
        "recipeServings": {"rec-1": 4},
    },
    "preferences": {},
    "stores": [{"id": "target", "baseUrl": "https://www.target.com"}],
}


def _minimal_ok_result() -> dict:
    return {
        "schemaVersion": "1.0",
        "ok": True,
        "result": {
            "runId": "job-test",
            "multiStoreOptimization": {
                "perIngredient": [{"partial": False, "ingredientKey": "k"}],
                "errors": [],
            },
            "metrics": {"optimizationLatencyMs": 12},
            "pipelineTrace": [
                {
                    "stage": "search",
                    "startedAtMs": 100,
                    "endedAtMs": 150,
                }
            ],
            "cartPlan": {"lines": []},
        },
        "error": None,
    }


def test_optimize_cart_404_without_snapshot():
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/grocery/optimize-cart",
            json={
                "mealPlanId": "missing-plan",
                "preferences": {"mode": "balanced", "maxStores": 2},
            },
        )
        assert r.status_code == 404


def test_optimize_cart_enqueue_and_complete(monkeypatch):
    def _fake_run(_payload: dict, timeout_sec: int = 90) -> dict:
        return _minimal_ok_result()

    monkeypatch.setattr("src.routes.grocery.run_grocery_optimizer", _fake_run)
    monkeypatch.setattr("src.pipeline.run_optimization_job.run_grocery_optimizer", _fake_run)

    with TestClient(app) as client:
        reg = client.post("/api/v1/grocery/optimize", json=SAMPLE_REQUEST)
        assert reg.status_code == 200

        r = client.post(
            "/api/v1/grocery/optimize-cart",
            headers={"X-User-Id": "test-user"},
            json={
                "mealPlanId": "plan-async-1",
                "preferences": {"mode": "min_cost", "maxStores": 2},
            },
        )
        assert r.status_code == 202
        body = r.json()
        assert "jobId" in body
        job_id = body["jobId"]

        terminal = None
        for _ in range(100):
            s = client.get(
                f"/api/v1/grocery/optimize-cart/{job_id}",
                headers={"X-User-Id": "test-user"},
            )
            assert s.status_code == 200
            data = s.json()
            assert data["status"] in ("queued", "running", "completed", "failed")
            assert 0 <= data["progress"] <= 100
            assert isinstance(data["stage"], str)
            if data["status"] in ("completed", "failed"):
                terminal = data
                break
            time.sleep(0.02)

        assert terminal is not None
        assert terminal["status"] == "completed"
        assert terminal["result"] is not None
        assert terminal["stats"] is not None
        assert terminal["stats"]["runId"]
        assert terminal["stats"]["totalLatency"] == 12
        assert terminal["stats"]["searchLatency"] == 50
