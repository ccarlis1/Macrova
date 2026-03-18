import pytest

from src.data_layer.user_profile import (
    PlannerConfigMappingError,
    user_profile_from_planner_config,
)
from src.llm.schemas import BudgetLevel, PlannerConfigJson, PlannerPreferences, PlannerTargets


def _cfg(*, days: int, meals_per_day: int, calories: int, protein: float, cuisine: list[str], budget: BudgetLevel):
    return PlannerConfigJson(
        days=days,
        meals_per_day=meals_per_day,
        targets=PlannerTargets(calories=calories, protein=protein),
        preferences=PlannerPreferences(cuisine=cuisine, budget=budget),
    )


def test_user_profile_from_planner_config_derives_schedule_and_macros():
    cfg = _cfg(
        days=3,
        meals_per_day=3,
        calories=2400,
        protein=150.0,
        cuisine=["chicken", "salad"],
        budget=BudgetLevel.cheap,
    )

    profile = user_profile_from_planner_config(cfg)

    assert profile.daily_calories == 2400
    assert profile.daily_protein_g == pytest.approx(150.0)
    assert profile.liked_foods == ["chicken", "salad"]
    assert profile.disliked_foods == []
    assert profile.allergies == []

    assert list(profile.schedule.keys()) == ["07:00", "12:00", "18:00"]
    assert all(v == 4 for v in profile.schedule.values())

    # carbs derived from deterministic fat ratio bounds for BudgetLevel.cheap
    remaining_after_protein_cal = 2400 - 150.0 * 4.0
    fat_ratio_min, fat_ratio_max = (0.25, 0.30)
    fat_g_min = (remaining_after_protein_cal * fat_ratio_min) / 9.0
    fat_g_max = (remaining_after_protein_cal * fat_ratio_max) / 9.0
    median_fat_g = (fat_g_min + fat_g_max) / 2.0
    expected_carbs = (
        2400 - 150.0 * 4.0 - median_fat_g * 9.0
    ) / 4.0

    assert profile.daily_fat_g[0] == pytest.approx(fat_g_min)
    assert profile.daily_fat_g[1] == pytest.approx(fat_g_max)
    assert profile.daily_carbs_g == pytest.approx(expected_carbs)
    assert profile.daily_carbs_g >= 0.0


def test_user_profile_from_planner_config_rejects_negative_derived_carbs():
    cfg = _cfg(
        days=1,
        meals_per_day=1,
        calories=1000,
        protein=300.0,
        cuisine=["anything"],
        budget=BudgetLevel.standard,
    )

    with pytest.raises(PlannerConfigMappingError) as exc:
        user_profile_from_planner_config(cfg)

    assert exc.value.error_code in (
        "NEGATIVE_REMAINING_AFTER_PROTEIN",
        "NEGATIVE_CARBS_DERIVED",
    )

