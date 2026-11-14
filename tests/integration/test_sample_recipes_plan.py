"""Sprint 2 DATA-1: plan over the 18 bundled sample recipes with the Flutter new-user macros.

Every sample resolves, so none may appear in ``warnings.nutrition``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.server import app

SAMPLES = "data/recipes/recipes.json.example"
SAMPLE_IDS = [f"recipe_{n:03d}" for n in range(1, 19)]


def test_three_day_plan_over_sample_recipes_has_no_nutrition_warnings(monkeypatch):
    monkeypatch.setattr("src.api.server.recipes_path", SAMPLES)
    meals = [{"index": i, "busyness_level": 4} for i in (1, 2, 3)]
    res = TestClient(app).post(
        "/api/v1/plan",
        json={
            # Flutter UserProfile defaults (frontend/lib/models/user_profile.dart).
            "daily_calories": 2000,
            "daily_protein_g": 150.0,
            "daily_fat_g_min": 60.0,
            "daily_fat_g_max": 74.0,
            "days": 3,
            "schedule_days": [{"day_index": d, "meals": meals} for d in (1, 2, 3)],
            "recipe_ids": SAMPLE_IDS,
            "planning_mode": "deterministic",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["plan_status"] == "success"
    warned = {rid for rid in SAMPLE_IDS for line in res.json()["warnings"].get("nutrition", []) if f"'{rid}'" in line}
    assert warned == set()
