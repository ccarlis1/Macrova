"""Sprint 2 BE-16: ``build_plan_request_from_profile`` keeps workout slots.

The builder used to emit the legacy ``schedule`` dict, which has no room for
workouts, so the HTTP payload planned a different day than the CLI.
"""

from __future__ import annotations

import pytest

from src.api.server import PlanRequest
from src.data_layer.models import UserProfile
from src.models.schedule import DaySchedule, MealSlot, WorkoutSlot
from src.planning.orchestrator import build_plan_request_from_profile


def _profile(**overrides) -> UserProfile:
    base = dict(
        daily_calories=2000,
        daily_protein_g=150.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=200.0,
        schedule={"07:00": 4, "12:00": 4, "18:00": 4},
        liked_foods=[],
        disliked_foods=[],
        allergies=[],
        schedule_days=[
            DaySchedule(
                day_index=1,
                meals=[
                    MealSlot(index=1, busyness_level=4),
                    MealSlot(index=2, busyness_level=4),
                    MealSlot(index=3, busyness_level=4),
                ],
                workouts=[WorkoutSlot(after_meal_index=1, type="AM")],
            )
        ],
    )
    base.update(overrides)
    return UserProfile(**base)


def test_builder_emits_schedule_days_with_workouts_not_legacy_schedule():
    payload = build_plan_request_from_profile(_profile(), [], [], None)

    assert "schedule" not in payload
    assert payload["days"] == 1
    assert payload["schedule_days"][0]["workouts"] == [{"after_meal_index": 1, "type": "AM"}]
    assert [m["busyness_level"] for m in payload["schedule_days"][0]["meals"]] == [4, 4, 4]


@pytest.mark.parametrize("days", [1, 3])
def test_builder_payload_is_a_valid_plan_request(days):
    payload = build_plan_request_from_profile(_profile(), [], [], None, days=days)

    req = PlanRequest.model_validate(payload)

    assert req.days == days
    assert len(req.schedule_days) == days
    # Mirrors convert_profile: a one-day template is replicated with 1-based day_index.
    assert [d.day_index for d in req.schedule_days] == list(range(1, days + 1))
    assert all(len(d.workouts) == 1 for d in req.schedule_days)


def test_builder_converts_legacy_only_profile():
    """A profile with no ``schedule_days`` (e.g. NL config) still yields ``schedule_days``."""
    payload = build_plan_request_from_profile(
        _profile(schedule_days=None, schedule={"08:00": 2, "13:00": 3}), [], [], None, days=2
    )

    assert "schedule" not in payload
    req = PlanRequest.model_validate(payload)
    assert [len(d.meals) for d in req.schedule_days] == [2, 2]
    assert [m.busyness_level for m in req.schedule_days[0].meals] == [2, 3]
