import yaml
from fastapi.testclient import TestClient

from src.api.server import app


class _DummyRecipeDB:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def get_recipe_by_id(self, recipe_id: str):
        if recipe_id in {"known-recipe", "known-recipe-2"}:
            return object()
        return None


def _write_profile(path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "nutrition_goals": {
                    "daily_calories": 2200,
                    "daily_protein_g": 140,
                    "daily_fat_g": {"min": 60, "max": 90},
                },
                "preferences": {"liked_foods": [], "disliked_foods": [], "allergies": []},
            }
        ),
        encoding="utf-8",
    )


def test_profile_pins_crud_idempotent_and_clear(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr("src.api.server.RecipeDB", _DummyRecipeDB)

    client = TestClient(app)

    created = client.put("/api/v1/profile/pins/0/1", json={"recipe_id": "known-recipe"})
    assert created.status_code == 200
    assert created.json()["pin"] == {
        "day_index": 0,
        "slot_index": 1,
        "recipe_id": "known-recipe",
    }

    duplicate = client.put("/api/v1/profile/pins/0/1", json={"recipe_id": "known-recipe"})
    assert duplicate.status_code == 200
    assert duplicate.json() == created.json()

    updated = client.put("/api/v1/profile/pins/0/1", json={"recipe_id": "known-recipe-2"})
    assert updated.status_code == 200
    assert updated.json()["pin"]["recipe_id"] == "known-recipe-2"

    _ = client.put("/api/v1/profile/pins/1/0", json={"recipe_id": "known-recipe"})
    listed = client.get("/api/v1/profile/pins")
    assert listed.status_code == 200
    assert listed.json()["pins"] == [
        {"day_index": 0, "slot_index": 1, "recipe_id": "known-recipe-2"},
        {"day_index": 1, "slot_index": 0, "recipe_id": "known-recipe"},
    ]

    cleared_one = client.delete("/api/v1/profile/pins/0/1")
    assert cleared_one.status_code == 200
    assert cleared_one.json() == {
        "deleted": True,
        "pin": {"day_index": 0, "slot_index": 1, "recipe_id": "known-recipe-2"},
    }

    clear_absent = client.delete("/api/v1/profile/pins/0/1")
    assert clear_absent.status_code == 200
    assert clear_absent.json() == {"deleted": False, "pin": None}

    cleared_all = client.delete("/api/v1/profile/pins")
    assert cleared_all.status_code == 200
    assert cleared_all.json() == {"cleared_count": 1}
    assert client.get("/api/v1/profile/pins").json() == {"pins": []}

    saved = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    assert saved["pins"] == []


def test_profile_pins_unknown_recipe_id_returns_structured_not_found(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr("src.api.server.RecipeDB", _DummyRecipeDB)

    client = TestClient(app)
    response = client.put("/api/v1/profile/pins/0/0", json={"recipe_id": "missing-recipe"})
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "RECIPE_NOT_FOUND"
