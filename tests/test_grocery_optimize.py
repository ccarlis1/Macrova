"""Grocery optimizer Phase 0: API contract and Node runner wiring."""

import json
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.services import grocery_optimizer as go


SAMPLE_REQUEST = {
    "schemaVersion": "1.0",
    "mealPlan": {
        "id": "plan-abc",
        "recipes": [
            {
                "id": "rec-1",
                "name": "Chicken bowl",
                "ingredients": [
                    {"name": "chicken breast", "quantity": 1.5, "unit": "lb"},
                    {"name": "olive oil", "quantity": 2, "unit": "tbsp"},
                ],
            }
        ],
        "recipeServings": {"rec-1": 4},
    },
    "preferences": {},
    "stores": [{"id": "walmart", "baseUrl": "https://www.walmart.com"}],
}


def test_grocery_optimize_happy_path(monkeypatch):
    def fake_run(payload: dict) -> dict:
        assert payload["schemaVersion"] == "1.0"
        assert "mealPlan" in payload
        return {
            "schemaVersion": "1.0",
            "ok": True,
            "result": {"message": "stub response"},
            "error": None,
        }

    monkeypatch.setattr("src.routes.grocery.run_grocery_optimizer", fake_run)
    client = TestClient(app)
    r = client.post("/api/grocery/optimize", json=SAMPLE_REQUEST)
    assert r.status_code == 200
    data = r.json()
    assert data["schemaVersion"] == "1.0"
    assert data["ok"] is True
    assert data["result"]["message"] == "stub response"
    assert data["error"] is None


def test_grocery_optimize_v1_path_parity(monkeypatch):
    monkeypatch.setattr(
        "src.routes.grocery.run_grocery_optimizer",
        lambda _p: {
            "schemaVersion": "1.0",
            "ok": True,
            "result": {},
            "error": None,
        },
    )
    client = TestClient(app)
    legacy = client.post("/api/grocery/optimize", json=SAMPLE_REQUEST)
    v1 = client.post("/api/v1/grocery/optimize", json=SAMPLE_REQUEST)
    assert legacy.status_code == v1.status_code == 200
    assert legacy.json() == v1.json()


def test_grocery_optimize_invalid_runner_payload(monkeypatch):
    monkeypatch.setattr(
        "src.routes.grocery.run_grocery_optimizer",
        lambda _p: {"not": "a valid envelope"},
    )
    client = TestClient(app)
    r = client.post("/api/grocery/optimize", json=SAMPLE_REQUEST)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert data["result"] is None
    assert "error" in data and data["error"]["message"]


def test_run_grocery_optimizer_success(tmp_path, monkeypatch):
    run_js = tmp_path / "run.js"
    run_js.write_text("", encoding="utf-8")
    monkeypatch.setattr(go, "_GROCERY_RUN_JS", run_js)

    out = {
        "schemaVersion": "1.0",
        "ok": True,
        "result": {"message": "from node"},
        "error": None,
    }

    def fake_run(*_a, **_k):
        return subprocess.CompletedProcess(
            args=["node", str(run_js)],
            returncode=0,
            stdout=json.dumps(out).encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    payload = {"schemaVersion": "1.0", "x": 1}
    got = go.run_grocery_optimizer(payload)
    assert got["ok"] is True
    assert got["result"]["message"] == "from node"


def test_run_grocery_optimizer_timeout(tmp_path, monkeypatch):
    run_js = tmp_path / "run.js"
    run_js.write_text("", encoding="utf-8")
    monkeypatch.setattr(go, "_GROCERY_RUN_JS", run_js)

    def fake_run(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="node", timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    got = go.run_grocery_optimizer({})
    assert got["ok"] is False
    assert "timed out" in got["error"]["message"].lower()


def test_run_grocery_optimizer_nonzero_exit(tmp_path, monkeypatch):
    run_js = tmp_path / "run.js"
    run_js.write_text("", encoding="utf-8")
    monkeypatch.setattr(go, "_GROCERY_RUN_JS", run_js)

    def fake_run(*_a, **_k):
        return subprocess.CompletedProcess(
            args=["node", str(run_js)],
            returncode=2,
            stdout=b"",
            stderr=b"node failed",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    got = go.run_grocery_optimizer({})
    assert got["ok"] is False
    assert "2" in got["error"]["message"]


def test_run_grocery_optimizer_bad_stdout_json(tmp_path, monkeypatch):
    run_js = tmp_path / "run.js"
    run_js.write_text("", encoding="utf-8")
    monkeypatch.setattr(go, "_GROCERY_RUN_JS", run_js)

    def fake_run(*_a, **_k):
        return subprocess.CompletedProcess(
            args=["node", str(run_js)],
            returncode=0,
            stdout=b"not-json",
            stderr=b"",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    got = go.run_grocery_optimizer({})
    assert got["ok"] is False
    assert "Invalid JSON" in got["error"]["message"]


@pytest.mark.skipif(
    not Path(go.grocery_run_js_path()).is_file(),
    reason="packages/grocery-optimizer/dist/run.js not built",
)
def test_grocery_optimize_e2e_with_real_node_cli(monkeypatch):
    """Runs dist/run.js via FastAPI; mock TinyFish so CI does not call the network."""
    monkeypatch.setenv("GROCERY_OPTIMIZER_USE_MOCK", "1")
    client = TestClient(app)
    r = client.post("/api/v1/grocery/optimize", json=SAMPLE_REQUEST)
    assert r.status_code == 200
    data = r.json()
    assert data["schemaVersion"] == "1.0"
    assert data["ok"] is True
    result = data["result"]
    assert isinstance(result, dict)
    assert "cartPlan" in result and "lines" in result["cartPlan"]
    assert "multiStoreOptimization" in result
    assert "metrics" in result
    assert "costGapVsGreedy" in result["metrics"]
    assert "pipelineTrace" in result
