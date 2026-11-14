"""Sprint 2 DATA-1: plan over the 18 bundled sample recipes with the Flutter new-user macros.

Only the sample recipes DATA-1 could not fix from FDC portions (see the stub's
close-out) may appear in ``warnings.nutrition``; every other sample is planned.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.server import app

SAMPLES = "data/recipes/recipes.json.example"
SAMPLE_IDS = [f"recipe_{n:03d}" for n in range(1, 19)]
# No close FDC portion for a unit these recipes use (DATA-1 close-out lists each one).
NOT_READY = {
    "recipe_007", "recipe_008", "recipe_009", "recipe_010", "recipe_011",
    "recipe_014", "recipe_018",
}


def test_three_day_plan_over_sample_recipes_warns_only_about_known_gaps(monkeypatch):
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
    warned = {rid for rid in SAMPLE_IDS for line in res.json()["warnings"]["nutrition"] if f"'{rid}'" in line}
    assert warned == NOT_READY
