import yaml
from fastapi.testclient import TestClient

from src.api.server import app


class _ResolvedTag:
    def __init__(self, slug: str) -> None:
        self.slug = slug


def _payload() -> dict:
    return {
        "schedule_days": [
            {
                "day_index": 1,
                "meals": [
                    {
                        "index": 1,
                        "busyness_level": 2,
                        "preferred_time": "07:30",
                        "required_tag_slugs": ["high-protein"],
                        "preferred_tag_slugs": ["quick-meal"],
                    },
                    {"index": 2, "busyness_level": 3},
                ],
                "workouts": [{"after_meal_index": 1, "type": "PM", "intensity": "moderate"}],
            }
        ]
    }


def test_put_profile_schedule_round_trip_preserves_fields(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    profile_path.write_text(
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
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr(
        "src.llm.tag_repository.resolve",
        lambda slug, path: _ResolvedTag(str(slug)),
    )

    client = TestClient(app)
    response = client.put("/api/v1/profile/schedule", json=_payload())
    assert response.status_code == 200
    body = response.json()
    meal_1 = body["schedule_days"][0]["meals"][0]
    assert meal_1["required_tag_slugs"] == ["high-protein"]
    assert meal_1["preferred_tag_slugs"] == ["quick-meal"]
    assert meal_1["preferred_time"] == "07:30"
    assert body["schedule_days"][0]["workouts"] == [
        {"after_meal_index": 1, "type": "PM", "intensity": "moderate"}
    ]

    saved = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    assert saved["schedule_days"] == body["schedule_days"]
    assert "schedule" not in saved


def test_put_profile_schedule_duplicate_index_validation(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    profile_path.write_text(yaml.safe_dump({"preferences": {}, "nutrition_goals": {}}), encoding="utf-8")
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr(
        "src.llm.tag_repository.resolve",
        lambda slug, path: _ResolvedTag(str(slug)),
    )

    payload = _payload()
    payload["schedule_days"][0]["meals"][1]["index"] = 1

    client = TestClient(app)
    response = client.put("/api/v1/profile/schedule", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "PROFILE_SCHEDULE_INVALID"
    assert body["error"]["details"]["field_errors"]
    assert any(
        "Meal indices must be contiguous" in item["message"]
        for item in body["error"]["details"]["field_errors"]
    )


def test_put_profile_schedule_rejects_workout_busyness_encoding(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    profile_path.write_text(yaml.safe_dump({"preferences": {}, "nutrition_goals": {}}), encoding="utf-8")
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr(
        "src.llm.tag_repository.resolve",
        lambda slug, path: _ResolvedTag(str(slug)),
    )

    payload = _payload()
    payload["schedule_days"][0]["meals"][0]["busyness_level"] = 0

    client = TestClient(app)
    response = client.put("/api/v1/profile/schedule", json=payload)
    assert response.status_code == 400
    errors = response.json()["error"]["details"]["field_errors"]
    assert any(item["field_path"].endswith("busyness_level") for item in errors)


def test_put_profile_schedule_is_idempotent(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    profile_path.write_text(yaml.safe_dump({"preferences": {}, "nutrition_goals": {}}), encoding="utf-8")
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr(
        "src.llm.tag_repository.resolve",
        lambda slug, path: _ResolvedTag(str(slug)),
    )

    client = TestClient(app)
    first = client.put("/api/v1/profile/schedule", json=_payload())
    second = client.put("/api/v1/profile/schedule", json=_payload())
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_put_profile_schedule_rejects_unknown_fields(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    profile_path.write_text(yaml.safe_dump({"preferences": {}, "nutrition_goals": {}}), encoding="utf-8")
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr(
        "src.llm.tag_repository.resolve",
        lambda slug, path: _ResolvedTag(str(slug)),
    )

    payload = _payload()
    payload["schedule_days"][0]["meals"][0]["unexpected"] = "x"

    client = TestClient(app)
    response = client.put("/api/v1/profile/schedule", json=payload)
    assert response.status_code == 400
    errors = response.json()["error"]["details"]["field_errors"]
    assert any(item["field_path"].endswith("unexpected") for item in errors)
