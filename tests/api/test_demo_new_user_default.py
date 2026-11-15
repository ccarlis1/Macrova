"""Sprint 2 demo step 2b (DATA-2): a new user imports all 18 starter recipes and plans
7 days with the Flutter new-user default request.

Pins today's outcome so a change is noticed (README → Close-out results, row 2b):
- without micronutrient goals, `demographic: adult_male` (daily ULs on) → success. Before
  DATA-2 corrected vitamin D (~40x too high) this was partial / FM-MACRO-INFEASIBLE: six
  starter recipes were over the 4,000 IU UL on their own.
- with the default goals from GET /api/v1/micronutrient_defaults → partial / FM-5 (search
  budget). The 600 IU/day vitamin D floor binds: with it removed the plan succeeds, and with
  only that floor it still hits FM-5. Not tuned away here: it is an owner decision.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer import user_data

STARTERS = [f"recipe_{n:03d}" for n in range(1, 19)]
MEALS = [
    {"index": i + 1, "busyness_level": b, "tags": [t]}
    for i, (b, t) in enumerate(zip((2, 3, 4), ("breakfast", "lunch", "dinner")))
]
# Flutter UserProfile defaults (frontend/lib/models/user_profile.dart) and the 2/3/4 schedule.
REQUEST = {
    "daily_calories": 2000,
    "daily_protein_g": 150.0,
    "daily_fat_g_min": 60.0,
    "daily_fat_g_max": 74.0,
    "days": 7,
    "schedule_days": [{"day_index": d, "meals": MEALS} for d in range(1, 8)],
    "planning_mode": "deterministic",
    "demographic": "adult_male",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    folder = tmp_path / "ud"
    assert user_data.setup_user_data(folder)
    monkeypatch.setattr("src.api.server.recipes_path", str(folder / "recipes.json"))
    monkeypatch.setattr("src.api.server.DEFAULT_TAG_PATH", str(folder / "recipe_tags.json"))
    c = TestClient(app)
    res = c.post("/api/v1/starter_recipes/import", json={"recipe_ids": STARTERS})
    assert res.status_code == 200, res.text
    assert res.json()["imported"] == STARTERS
    return c


def _codes(body: dict) -> list:
    return [f["code"] for f in body["report"].get("failures", [])]


def test_all_starters_adult_male_without_goals_succeeds(client):
    body = client.post("/api/v1/plan", json=REQUEST).json()
    assert (body["plan_status"], body["termination_code"], _codes(body)) == ("success", "TC-1", [])


def test_all_starters_adult_male_with_default_goals_hits_the_search_budget(client):
    defaults = client.get("/api/v1/micronutrient_defaults", params={"demographic": "adult_male"}).json()
    body = client.post(
        "/api/v1/plan",
        json={
            **REQUEST,
            "micronutrient_goals": defaults["micronutrient_goals"],
            "micronutrient_weekly_min_fraction": defaults["micronutrient_weekly_min_fraction"],
        },
    ).json()
    assert (body["plan_status"], body["termination_code"], _codes(body)) == ("partial", "TC-3", ["FM-5"])
    assert body["report"]["failure_cause"]["cause"] == "SEARCH_BUDGET"
